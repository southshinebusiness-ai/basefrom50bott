"""Read-only SSH probe of the owner's Timeweb server.

Rerun after the owner configured the protected SSH password secret.

The password, if available from Timeweb API, is kept only in process memory.
No credentials, .env contents, payment records, or application logs are printed.
This never changes the remote server. The first SSH host key is trust-on-first-use;
future probes should pin the reported fingerprint.
"""
import base64
import hashlib
import ipaddress
import json
import os
import shlex
import sys
from urllib.request import Request, urlopen

import paramiko

API = "https://api.timeweb.cloud"
EXPECTED_SERVER_NAME = "Honest Plover"
EXPECTED_IP = "5.129.247.209"
# First-seen host key from owner-verified server IP, 2026-10-29.
PINNED_HOSTKEY_SHA256 = "IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"


def api_get(path, token):
    req = Request(API + path, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
    })
    with urlopen(req, timeout=12) as resp:
        return json.load(resp)


def safe_command(transport, command, timeout=8):
    chan = transport.open_session(timeout=timeout)
    chan.settimeout(timeout)
    chan.exec_command(command)
    data = bytearray()
    while True:
        chunk = chan.recv(2048)
        if chunk:
            data.extend(chunk)
            if len(data) > 8192:
                raise RuntimeError("remote command output too large")
        elif chan.exit_status_ready():
            break
    code = chan.recv_exit_status()
    return code, data.decode("utf-8", errors="replace").strip()


def main():
    token = os.environ.get("TIMEWEB_API_TOKEN", "").strip()
    if not token:
        print("SSH probe skipped: Timeweb token secret not configured.")
        return 0

    try:
        servers = api_get("/api/v1/servers", token).get("servers", [])
        matches = [s for s in servers if s.get("name") == EXPECTED_SERVER_NAME]
        if len(matches) != 1:
            print("SSH probe skipped: target server not uniquely identified.")
            return 0
        server = matches[0]
        server_id = server.get("id")
        ips = api_get(f"/api/v1/servers/{server_id}/ips", token).get("server_ips", [])
        addresses = [
            entry.get("ip") for entry in ips
            if isinstance(entry, dict) and entry.get("type") == "ipv4"
        ]
        # Timeweb may use different type spelling; use exact expected IP only.
        if EXPECTED_IP not in addresses:
            addresses = [
                entry.get("ip") for entry in ips if isinstance(entry, dict)
            ]
        if EXPECTED_IP not in addresses:
            print("SSH probe skipped: public IP does not match owner-verified address.")
            return 0
        ipaddress.ip_address(EXPECTED_IP)
        if server.get("is_allow_root_ssh_pass") is not True:
            print("SSH probe skipped: root password login disabled.")
            return 0
        password = os.environ.get("TIMEWEB_SSH_PASSWORD", "").strip() or server.get("root_pass")
        if not isinstance(password, str) or not password or set(password) == {"*"}:
            print("SSH probe skipped: no usable password in Timeweb API.")
            return 0

        transport = paramiko.Transport((EXPECTED_IP, 22))
        try:
            transport.banner_timeout = 8
            transport.auth_timeout = 8
            transport.start_client(timeout=10)
            host_key = transport.get_remote_server_key()
            fingerprint = base64.b64encode(
                hashlib.sha256(host_key.asbytes()).digest()
            ).decode("ascii").rstrip("=")
            print("SSH server host-key fingerprint (SHA256): " + fingerprint)
            pinned = os.environ.get("TIMEWEB_SSH_HOSTKEY_SHA256", "").strip() or PINNED_HOSTKEY_SHA256
            if pinned and pinned != fingerprint:
                print("SSH probe aborted: host key fingerprint mismatch.")
                return 1
            if not pinned:
                print("First connection: SSH host key not yet pinned (TOFU).")

            try:
                transport.auth_password("root", password, fallback=False)
            except paramiko.AuthenticationException:
                print("SSH password authentication failed. No server changes made.")
                return 0
            if not transport.is_authenticated():
                print("SSH authentication unavailable. No server changes made.")
                return 0
            print("SSH authenticated successfully; running read-only checks.")

            checks = {
                "bot service state": "systemctl show basefrom50bot.service -p ActiveState -p SubState --no-pager",
                "bot source present": "test -f /opt/bot/main.py && echo yes || echo no",
                "bot environment file present": "test -f /opt/bot/.env && echo yes || echo no",
                "bot SQLite file present": "test -f /opt/bot/data/bot.db && echo yes || echo no",
                "local HTTP health": "curl -fsS --max-time 3 http://127.0.0.1:8080/health >/dev/null && echo healthy || echo unavailable",
                "listeners on ports 80/443/8080": "ss -ltn '( sport = :80 or sport = :443 or sport = :8080 )' | tail -n +2 | awk '{print $4}' | head -n 12",
                "nginx installed": "command -v nginx >/dev/null && echo yes || echo no",
                "caddy installed": "command -v caddy >/dev/null && echo yes || echo no",
                "git checkout at /opt/bot": "test -d /opt/bot/.git && echo yes || echo no",
                "systemd unit details": "systemctl show basefrom50bot.service -p LoadState -p UnitFileState -p ActiveState -p SubState -p Result -p ExecMainCode -p ExecMainStatus -p ActiveEnterTimestamp -p InactiveEnterTimestamp --no-pager",
                "systemd unit enabled": "systemctl is-enabled basefrom50bot.service || true",
                "Python virtualenv present": "test -x /opt/bot/venv/bin/python3 && echo yes || echo no",
                "repo branch": "git -C /opt/bot branch --show-current 2>/dev/null || true",
                "repo commit": "git -C /opt/bot rev-parse --short HEAD 2>/dev/null || true",
                "SQLite read-only integrity": "python3 -c 'import sqlite3; c=sqlite3.connect(\"file:/opt/bot/data/bot.db?mode=ro\",uri=True); print(c.execute(\"PRAGMA integrity_check\").fetchone()[0]); c.close()' 2>/dev/null || echo check-unavailable",
                "important env keys configured": "python3 -c 'from pathlib import Path; p=Path(\"/opt/bot/.env\"); d={k.strip():v.strip() for l in p.read_text().splitlines() if \"=\" in l and not l.lstrip().startswith(\"#\") for k,v in [l.split(\"=\",1)]}; print(\" \".join(k+\"=\"+(\"set\" if d.get(k) else \"empty\") for k in (\"BOT_TOKEN\",\"ADMIN_ID\",\"YOOMONEY_SECRET\",\"YOOMONEY_TOKEN\",\"DB_PATH\",\"PORT\")))' 2>/dev/null || echo check-unavailable",
                "bot log file present": "test -f /opt/bot/data/bot.log && echo yes || echo no",
                "disk free space": "df -h /opt/bot | tail -n 1 | awk '{print $4 \" free; \" $5 \" used\"}'",
                "recent bot log error count": "if test -f /opt/bot/data/bot.log; then tail -n 300 /opt/bot/data/bot.log | grep -Eic 'ERROR|Traceback|Exception|CRITICAL' || true; else echo log-not-found; fi",
                "recent systemd journal error count": "journalctl -u basefrom50bot.service --no-pager -n 300 2>/dev/null | grep -Eic 'ERROR|Traceback|Exception|CRITICAL|Failed' || true",
                "firewall rules": "ufw status 2>/dev/null | head -n 20 || true",
                "bot-related processes": "ps -eo comm= | grep -E 'python|caddy|nginx' | sort | uniq -c | head -n 15 || true",
                "repo tracked modifications count": "git -C /opt/bot status --porcelain --untracked-files=no | wc -l",
                "repo tracked modification paths": "git -C /opt/bot diff --name-only | head -n 12",
                "repo tracked modification summary": "git -C /opt/bot diff --stat | tail -n 8",
                "repo untracked file count": "git -C /opt/bot ls-files --others --exclude-standard | wc -l",
                "requirements present": "test -f /opt/bot/requirements.txt && echo yes || echo no",
                "local main.py checksum": "sha256sum /opt/bot/main.py | cut -c 1-20",
                "sqlite database size": "stat -c '%s bytes' /opt/bot/data/bot.db",
                "log error categories": "python3 -c 'from pathlib import Path; import re; p=Path(\"/opt/bot/data/bot.log\"); a=p.read_text(errors=\"replace\").splitlines()[-600:] if p.exists() else []; tags=(\"ModuleNotFoundError\",\"ImportError\",\"ConnectionError\",\"ClientConnectorError\",\"Unauthorized\",\"Conflict\",\"Traceback\",\"ERROR\",\"PermissionError\",\"YOOMONEY\"); print(\" \".join(t+\"=\"+str(sum(t.lower() in s.lower() for s in a)) for t in tags))' 2>/dev/null || echo check-unavailable",
                "SQLite tables count": "python3 -c 'import sqlite3; c=sqlite3.connect(\"file:/opt/bot/data/bot.db?mode=ro\",uri=True); print(len(c.execute(\"SELECT name FROM sqlite_master WHERE type=\\\'table\\\'\").fetchall())); c.close()' 2>/dev/null || echo check-unavailable",
            }
            for title, command in checks.items():
                try:
                    status, output = safe_command(transport, command)
                    print(f"{title}: {output[:400] if output else '(none)'} (exit {status})")
                except Exception as exc:
                    print(f"{title}: check unavailable ({type(exc).__name__})")
            print("Read-only SSH diagnostics completed. No changes made.")
        finally:
            transport.close()
    except Exception as exc:
        print(f"SSH probe unavailable: {type(exc).__name__}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
