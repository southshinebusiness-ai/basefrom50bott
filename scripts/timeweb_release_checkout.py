"""Enable the already tested production checkout on Timeweb with rollback.

Requires a verified on-server backup. Does not change the public price or
database, and never prints credentials.
"""
import base64
import hashlib
import os
import time

import paramiko

HOST = "5.129.247.209"
HOST_KEY = "IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"


def run(transport, command, timeout=35):
    channel = transport.open_session(timeout=10)
    channel.settimeout(timeout)
    channel.exec_command(command)
    output = channel.makefile("rb").read(3000).decode(errors="replace").strip()
    status = channel.recv_exit_status()
    if status:
        raise RuntimeError("Remote command failed: " + output[-350:])
    return output


def main():
    transport = paramiko.Transport((HOST, 22))
    try:
        transport.start_client(timeout=12)
        fp = base64.b64encode(hashlib.sha256(
            transport.get_remote_server_key().asbytes()
        ).digest()).decode().rstrip("=")
        if fp != HOST_KEY:
            raise RuntimeError("SSH host fingerprint mismatch")
        transport.auth_password("root", os.environ["TIMEWEB_SSH_PASSWORD"], fallback=False)
        if not transport.is_authenticated():
            raise RuntimeError("SSH authentication failed")

        preflight = (
            "test -f /opt/basefrom50-stage/.env && "
            "test -f /opt/bot/data/bot.db && "
            "test -d /root/basefrom50-backups/20261030T094202Z && "
            "systemctl is-active --quiet basefrom50bot.service && "
            "curl -fsS --max-time 8 https://5.129.247.209/health && "
            "cd /opt/basefrom50-stage && "
            "/opt/bot/venv/bin/python3 -c "
            "'import config; c=config.config; "
            "assert c.PRICE_ULTIMATE_GUIDE == 1990; "
            "assert c.YOOMONEY_SECRET and c.YOOMONEY_WALLET and c.BOT_TOKEN; "
            "assert c.PRIVATE_CHANNEL_ID; "
            "print(\"Release prerequisites OK\")'"
        )
        print(run(transport, preflight))

        # Keep original .env on the server for immediate rollback.
        patch = (
            "python3 -c 'from pathlib import Path; import os; "
            "p=Path(\"/opt/basefrom50-stage/.env\"); "
            "raw=p.read_text(); "
            "assert \"PAYMENTS_READY=0\" in raw or \"PAYMENTS_READY=1\" in raw; "
            "new=raw.replace(\"PAYMENTS_READY=0\", \"PAYMENTS_READY=1\"); "
            "backup=Path(\"/root/basefrom50-backups/20261030T094202Z/.env.before-release\"); "
            "backup.write_text(raw) if not backup.exists() else None; "
            "backup.chmod(0o600); "
            "tmp=p.with_suffix(\".env.new\"); tmp.write_text(new); "
            "tmp.chmod(0o600); os.replace(tmp,p); "
            "print(\"Checkout configuration activated\")'"
        )
        print(run(transport, patch))
        try:
            print(run(transport, "systemctl restart basefrom50bot.service && sleep 12 && systemctl is-active basefrom50bot.service && curl -fsS --max-time 8 https://5.129.247.209/health", timeout=40))
            print(run(transport, "cd /opt/basefrom50-stage && /opt/bot/venv/bin/python3 -c 'import config; assert config.config.PAYMENTS_READY; assert config.config.PRICE_ULTIMATE_GUIDE==1990; print(\"Public checkout ready: 1990 RUB\")'"))
        except Exception:
            run(transport, "cp /root/basefrom50-backups/20261030T094202Z/.env.before-release /opt/basefrom50-stage/.env && chmod 600 /opt/basefrom50-stage/.env && systemctl restart basefrom50bot.service")
            raise
    finally:
        transport.close()


if __name__ == "__main__":
    main()
