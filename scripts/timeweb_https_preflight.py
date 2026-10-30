"""Read-only preflight for Timeweb HTTPS reverse proxy."""
import base64
import hashlib
import os
import socket
import paramiko

HOST = "5.129.247.209"
DNS_NAME = "5-129-247-209.sslip.io"
EXPECTED = "IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"

addresses = sorted({a[4][0] for a in socket.getaddrinfo(DNS_NAME, 443, family=socket.AF_INET)})
print("Public hostname DNS points to expected server:", addresses == [HOST])
if addresses != [HOST]:
    raise SystemExit("DNS hostname is not pointing to the Timeweb server")

t = paramiko.Transport((HOST, 22))
try:
    t.start_client(timeout=12)
    fingerprint = base64.b64encode(hashlib.sha256(t.get_remote_server_key().asbytes()).digest()).decode().rstrip("=")
    if fingerprint != EXPECTED:
        raise SystemExit("SSH host key mismatch")
    t.auth_password("root", os.environ["TIMEWEB_SSH_PASSWORD"], fallback=False)
    if not t.is_authenticated():
        raise SystemExit("SSH authentication failed")
    checks = {
        "Bot service": "systemctl is-active basefrom50bot.service || true",
        "Bot restart count": "systemctl show basefrom50bot.service -p NRestarts -p ExecMainStatus -p ActiveState -p SubState -p ActiveEnterTimestamp --no-pager",
        "Telegram network errors": "journalctl -u basefrom50bot.service --no-pager -n 200 2>/dev/null | grep 'TelegramNetworkError:' | sed -E 's#https?://[^ ]+#URL_REDACTED#g' | tail -n 4 || true",
        "Telegram egress": "curl -4 -sS --max-time 5 -o /dev/null -w 'status=%{http_code}' https://api.telegram.org || true",
        "Bot recent error categories": "journalctl -u basefrom50bot.service --no-pager -n 150 2>/dev/null | grep -Eo '(Telegram[A-Za-z]+Error|OperationalError|ConnectionError|ImportError|RuntimeError|FileNotFoundError|PermissionError|TimeoutError|Error|Exception):' | sort | uniq -c | head -n 10 || true",
        "Nginx recent error categories": "tail -n 100 /var/log/nginx/error.log 2>/dev/null | grep -Eo 'connect\\(\\) failed|upstream timed out|SSL_do_handshake\\(\\) failed' | sort | uniq -c || true",
        "Bot HTTP": "curl -fsS --max-time 3 http://127.0.0.1:8080/health || true",
        "Caddy installed": "command -v caddy || echo not-installed",
        "Caddy unit": "systemctl is-active caddy.service || true",
        "Nginx unit": "systemctl is-active nginx.service || true",
        "Apache unit": "systemctl is-active apache2.service || true",
        "Port owners": "ss -ltnp '( sport = :80 or sport = :443 )' | tail -n +2 | cut -c1-170",
        "Nginx site names": "grep -RhE 'server_name|ssl_certificate ' /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null | head -n 12 || true",
        "Nginx route configuration": "grep -RhE 'location |proxy_pass|return 30|listen ' /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null | head -n 25 || true",
        "Certificate SAN and validity": "openssl x509 -in /etc/letsencrypt/live/basefrom50-ip/fullchain.pem -noout -dates -ext subjectAltName 2>/dev/null || true",
        "Certificate renewal": "systemctl list-timers --all --no-pager | grep -E 'certbot|letsencrypt' | head -n 2 || true",
        "Port 80/443 listeners": "ss -ltn '( sport = :80 or sport = :443 )' | tail -n +2",
        "Available disk": "df -h / | tail -n 1 | awk '{print $4}'",
        "DNS from server": "getent ahostsv4 5-129-247-209.sslip.io | head -n 1 | awk '{print $1}'",
        "APT package candidate": "apt-cache policy caddy | grep -m 1 Candidate || true",
    }
    for label, command in checks.items():
        ch = t.open_session(timeout=12)
        ch.settimeout(20)
        ch.exec_command(command)
        out = ch.makefile("rb").read(1024).decode(errors="replace").strip()
        ch.recv_exit_status()
        print(label + ":", out[:250] or "(none)")
finally:
    t.close()

from urllib.request import urlopen
from urllib.error import HTTPError
for endpoint in ("https://" + DNS_NAME + "/health", "http://" + DNS_NAME + "/health"):
    try:
        with urlopen(endpoint, timeout=8) as response:
            print("Public endpoint:", endpoint.split("://")[0], response.status, response.read(100).decode(errors="replace"))
    except HTTPError as error:
        print("Public endpoint:", endpoint.split("://")[0], "HTTP", error.code)
    except Exception as error:
        print("Public endpoint:", endpoint.split("://")[0], type(error).__name__)

try:
    with urlopen("https://" + HOST + "/health", timeout=10) as response:
        print("HTTPS IP certificate and health:", response.status, response.read(100).decode(errors="replace"))
except Exception as error:
    print("HTTPS IP certificate and health:", type(error).__name__)
