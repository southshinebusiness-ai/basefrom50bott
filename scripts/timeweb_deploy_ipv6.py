"""Deploy only the IPv6 Telegram transport fix to the existing Timeweb stage.

Preserves SQLite, .env, Nginx and all credentials. Keeps a server-side rollback copy.
"""
import base64
import hashlib
import os
from pathlib import Path
import time

import paramiko

HOST = "5.129.247.209"
FINGERPRINT = "IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"
TARGET = "/opt/basefrom50-stage/main.py"


def remote(transport, command, timeout=25):
    ch = transport.open_session(timeout=10)
    ch.settimeout(timeout)
    ch.exec_command(command)
    output = ch.makefile("rb").read(2500).decode(errors="replace").strip()
    return ch.recv_exit_status(), output


def main():
    password = os.environ.get("TIMEWEB_SSH_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("Missing SSH secret")
    replacement = Path("main.py").read_bytes()
    if b"socket.AF_INET6" not in replacement or b"make_ipv6_session" not in replacement:
        raise RuntimeError("IPv6 code is not present in release")
    t = paramiko.Transport((HOST, 22))
    try:
        t.start_client(timeout=12)
        fingerprint = base64.b64encode(hashlib.sha256(t.get_remote_server_key().asbytes()).digest()).decode().rstrip("=")
        if fingerprint != FINGERPRINT:
            raise RuntimeError("SSH host key mismatch")
        t.auth_password("root", password, fallback=False)
        if not t.is_authenticated():
            raise RuntimeError("SSH authentication failed")
        status, out = remote(t, "systemctl is-active basefrom50bot.service && test -f /opt/basefrom50-stage/.env && test -f /opt/bot/data/bot.db && curl -6 -sS -o /dev/null -w '%{http_code}' --max-time 8 https://api.telegram.org")
        if status != 0 or "active" not in out or "302" not in out:
            raise RuntimeError("Preflight failed; no changes made")
        sftp = paramiko.SFTPClient.from_transport(t)
        backup = TARGET + ".before-ipv6"
        try:
            with sftp.open(TARGET, "rb") as file:
                previous = file.read(150000)
            if b"socket.AF_INET" not in previous:
                raise RuntimeError("Unexpected production code; no changes made")
            with sftp.open(backup, "wb") as file:
                file.write(previous)
            sftp.chmod(backup, 0o600)
            with sftp.open(TARGET + ".tmp", "wb") as file:
                file.write(replacement)
            sftp.chmod(TARGET + ".tmp", 0o644)
            sftp.posix_rename(TARGET + ".tmp", TARGET)
        finally:
            sftp.close()
        status, out = remote(t, "systemctl restart basefrom50bot.service", timeout=30)
        if status != 0:
            raise RuntimeError("Service restart failed; rollback copy available")
        time.sleep(20)
        status, out = remote(t, "systemctl is-active basefrom50bot.service && curl -fsS --max-time 5 http://127.0.0.1:8080/health && journalctl -u basefrom50bot.service --since '-60 seconds' --no-pager | grep -E 'Polling started|Бот @basefrom50bot запущен' | tail -n 2", timeout=20)
        if status != 0 or "active" not in out or "ok" not in out:
            raise RuntimeError("Post-deploy health/polling verification failed; rollback copy available")
        print("Timeweb bot active with Telegram IPv6 transport; local HTTP healthy.")
        print("Polling confirmed in systemd journal.")
        print("YooMoney checkout remains disabled pending real payment verification.")
    finally:
        t.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("IPv6 deployment failed:", type(error).__name__)
        raise SystemExit(1)
