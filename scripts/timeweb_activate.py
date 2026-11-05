"""Start the previously missing systemd service from the isolated Timeweb stage.

Payments remain disabled. Local HTTP is bound to 127.0.0.1 only.
"""
import base64
import hashlib
import os
from pathlib import Path
import sys

import paramiko

HOST = "5.129.247.209"
FINGERPRINT = "IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"
ROOT = "/opt/basefrom50-stage"
UNIT = """[Unit]
Description=BASEFROM50 Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/basefrom50-stage
ExecStart=/opt/bot/venv/bin/python3 /opt/basefrom50-stage/main.py
Restart=on-failure
RestartSec=10
TimeoutStopSec=30
Environment=PYTHONUNBUFFERED=1
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
"""


def command(transport, cmd, timeout=30):
    ch = transport.open_session(timeout=12)
    ch.settimeout(timeout)
    ch.exec_command(cmd)
    out = bytearray()
    while not ch.exit_status_ready() or ch.recv_ready():
        if ch.recv_ready():
            out.extend(ch.recv(2048))
            if len(out) > 10000:
                raise RuntimeError("unexpectedly long command output")
    return ch.recv_exit_status(), out.decode(errors="replace").strip()


def main():
    password = os.environ.get("TIMEWEB_SSH_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("SSH secret missing")
    t = paramiko.Transport((HOST, 22))
    try:
        t.start_client(timeout=12)
        fp = base64.b64encode(hashlib.sha256(t.get_remote_server_key().asbytes()).digest()).decode().rstrip("=")
        if fp != FINGERPRINT:
            raise RuntimeError("SSH host key mismatch")
        t.auth_password("root", password, fallback=False)
        if not t.is_authenticated():
            raise RuntimeError("SSH authentication failed")

        preflight = (
            "test -f /opt/basefrom50-stage/.env && "
            "test -L /opt/basefrom50-stage/data && "
            "test -f /opt/bot/data/bot.db && "
            "test ! -e /etc/systemd/system/basefrom50bot.service && "
            "cd /opt/basefrom50-stage && "
            "/opt/bot/venv/bin/python3 -c "
            "'import config; assert not config.config.PAYMENTS_READY; "
            "assert config.config.YOOMONEY_SECRET; "
            "assert config.config.WEB_BIND_HOST == \"127.0.0.1\"; "
            "print(\"Safe activation preflight passed\")'"
        )
        # Deploy only updated source files; existing staged .env and assets stay.
        sftp = paramiko.SFTPClient.from_transport(t)
        try:
            for filename in ("main.py", "config.py"):
                with sftp.open(ROOT + "/" + filename + ".tmp", "wb") as f:
                    f.write(Path(filename).read_bytes())
                sftp.posix_rename(ROOT + "/" + filename + ".tmp", ROOT + "/" + filename)
            status, output = command(t, preflight, timeout=25)
            if status != 0:
                raise RuntimeError("Preflight failed, service not installed")
            print(output)
            with sftp.open("/etc/systemd/system/basefrom50bot.service.tmp", "wb") as f:
                f.write(UNIT.encode("utf-8"))
            sftp.chmod("/etc/systemd/system/basefrom50bot.service.tmp", 0o644)
            sftp.rename("/etc/systemd/system/basefrom50bot.service.tmp", "/etc/systemd/system/basefrom50bot.service")
        finally:
            sftp.close()

        status, output = command(t, "systemctl daemon-reload && systemctl enable --now basefrom50bot.service", timeout=35)
        if status != 0:
            raise RuntimeError("Service failed to start")
        print("Systemd unit installed and enabled.")
        status, output = command(
            t,
            "sleep 8; systemctl is-active basefrom50bot.service; "
            "curl -fsS --max-time 4 http://127.0.0.1:8080/health",
            timeout=25,
        )
        if status != 0 or "active" not in output or "ok" not in output:
            print("Service/health check did not pass; service status requires inspection.")
            raise RuntimeError("Bot health verification failed")
        print("Bot service active; local HTTP health: ok")
        print("New payment checkout: disabled pending HTTPS/webhook verification.")
    finally:
        t.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Activation failed:", type(exc).__name__)
        sys.exit(1)
