"""Safely rotate the Telegram bot token on Timeweb.

The new token is read only from a GitHub Actions secret. Never print it.
The bot's SQLite database, YooMoney settings and public price are untouched.
"""
import base64
import hashlib
import json
import os
import re
import time
import urllib.request

import paramiko

HOST = "5.129.247.209"
HOST_KEY = "IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"
ENV_PATH = "/opt/basefrom50-stage/.env"


def remote(transport, command, timeout=30):
    channel = transport.open_session(timeout=10)
    channel.settimeout(timeout)
    channel.exec_command(command)
    output = channel.makefile("rb").read(2000).decode(errors="replace")
    code = channel.recv_exit_status()
    if code:
        raise RuntimeError("Timeweb service command failed; exit code " + str(code))
    return output.strip()


def main():
    token = os.environ.get("BASEFROM50_NEW_BOT_TOKEN", "").strip()
    password = os.environ.get("TIMEWEB_SSH_PASSWORD", "").strip()
    if not token:
        raise RuntimeError("Missing BASEFROM50_NEW_BOT_TOKEN GitHub Actions secret; server unchanged")
    if not password:
        raise RuntimeError("Missing TIMEWEB_SSH_PASSWORD; server unchanged")
    if not re.fullmatch(r"[0-9]{5,}:[A-Za-z0-9_-]{30,}", token):
        raise RuntimeError("New Telegram token has unexpected format; server unchanged")

    # Validate before touching production. Do not print the URL or exceptions.
    try:
        request = urllib.request.Request(
            "https://api.telegram.org/bot" + token + "/getMe",
            headers={"User-Agent": "BASEFROM50-token-rotation"},
        )
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.load(response)
        if not result.get("ok") or result.get("result", {}).get("username", "").lower() != "basefrom50bot":
            raise ValueError("Token belongs to a different bot")
    except Exception:
        raise RuntimeError("Telegram rejected new token or bot username; server unchanged") from None
    print("BotFather token validated for @basefrom50bot.")

    transport = paramiko.Transport((HOST, 22))
    try:
        transport.start_client(timeout=12)
        fingerprint = base64.b64encode(hashlib.sha256(
            transport.get_remote_server_key().asbytes()
        ).digest()).decode().rstrip("=")
        if fingerprint != HOST_KEY:
            raise RuntimeError("SSH server fingerprint mismatch; server unchanged")
        transport.auth_password("root", password, fallback=False)
        if not transport.is_authenticated():
            raise RuntimeError("SSH authentication failed; server unchanged")

        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            with sftp.open(ENV_PATH, "rb") as f:
                original = f.read(30000)
            text = original.decode("utf-8")
            if len(re.findall(r"(?m)^BOT_TOKEN=", text)) != 1:
                raise RuntimeError("Expected exactly one BOT_TOKEN in Timeweb .env; unchanged")
            if not re.search(r"(?m)^PAYMENTS_READY=1\s*$", text):
                raise RuntimeError("Unexpected payment configuration; server unchanged")
            replacement = re.sub(
                r"(?m)^BOT_TOKEN=[^\r\n]*",
                lambda _: "BOT_TOKEN=" + token,
                text,
                count=1,
            ).encode("utf-8")
            backup = "/root/.basefrom50-env-before-bot-token-rotation"
            with sftp.open(backup, "wb") as f:
                f.write(original)
            sftp.chmod(backup, 0o600)
            temp = ENV_PATH + ".rotation-tmp"
            with sftp.open(temp, "wb") as f:
                f.write(replacement)
            sftp.chmod(temp, 0o600)
            sftp.posix_rename(temp, ENV_PATH)
        finally:
            sftp.close()

        remote(transport, "systemctl restart basefrom50bot.service", timeout=30)
        time.sleep(10)
        status = remote(
            transport,
            "systemctl is-active basefrom50bot.service && "
            "curl -fsS --max-time 8 http://127.0.0.1:8080/health",
            timeout=25,
        )
        if "active" not in status or "ok" not in status:
            raise RuntimeError("Bot restart health check failed; investigate Timeweb service")
        print("Timeweb bot restarted with new token; local health OK.")
        print("Existing user database, payment configuration and public price preserved.")
    finally:
        transport.close()


if __name__ == "__main__":
    main()
