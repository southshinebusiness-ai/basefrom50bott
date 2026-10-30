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
        "Bot HTTP": "curl -fsS --max-time 3 http://127.0.0.1:8080/health || true",
        "Caddy installed": "command -v caddy || echo not-installed",
        "Caddy unit": "systemctl is-active caddy.service || true",
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
