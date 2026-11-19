"""Deploy admin-only Telegram main menu image uploader to Timeweb.

Only handlers/main_menu.py is modified; DB, payments and tokens are untouched.
"""
import base64
import hashlib
import os
from pathlib import Path
import subprocess
import time

import paramiko

HOST = "5.129.247.209"
HOST_KEY = "IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"
LIVE = "/opt/basefrom50-stage/handlers/main_menu.py"
OLD_BLOB = "b572beec3a830c6d331dfddb190e122f90f56f67"
NEW_BLOB = "b85ea39fda5ff6c74c51991ad30119495bcffc73"
BACKUP = "/root/basefrom50-backups/menu-image-uploader-20261119"


def blob_sha(data):
    return hashlib.sha1(("blob " + str(len(data)) + "\0").encode() + data).hexdigest()


def remote(t, command, timeout=40):
    ch = t.open_session(timeout=10)
    ch.settimeout(timeout)
    ch.exec_command(command)
    output = ch.makefile("rb").read(2500).decode(errors="replace")
    if ch.recv_exit_status():
        raise RuntimeError("Remote command failed: " + command.split()[0])
    return output.strip()


def upload(sftp, path, content, mode):
    tmp = path + ".menu-new"
    with sftp.open(tmp, "wb") as f:
        f.write(content)
    sftp.chmod(tmp, mode)
    sftp.posix_rename(tmp, path)


def main():
    password = os.environ.get("TIMEWEB_SSH_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("TIMEWEB_SSH_PASSWORD missing")
    desired = Path("handlers/main_menu.py").read_bytes()
    if blob_sha(desired) != NEW_BLOB:
        raise RuntimeError("Unexpected source: refuse release")
    subprocess.run(["python", "-m", "py_compile", "handlers/main_menu.py"], check=True)
    t = paramiko.Transport((HOST, 22))
    try:
        t.start_client(timeout=12)
        fingerprint = base64.b64encode(
            hashlib.sha256(t.get_remote_server_key().asbytes()).digest()
        ).decode().rstrip("=")
        if fingerprint != HOST_KEY:
            raise RuntimeError("Host fingerprint mismatch")
        t.auth_password("root", password, fallback=False)
        if not t.is_authenticated():
            raise RuntimeError("SSH authentication failed")
        remote(t, "systemctl is-active --quiet basefrom50bot.service")
        sftp = paramiko.SFTPClient.from_transport(t)
        try:
            with sftp.open(LIVE, "rb") as f:
                original = f.read(300000)
            actual = blob_sha(original)
            if actual == NEW_BLOB:
                print("Admin image upload feature already deployed.")
                return
            if actual != OLD_BLOB:
                raise RuntimeError("Live main_menu.py differs from expected baseline")
            mode = sftp.stat(LIVE).st_mode & 0o777
            try:
                sftp.mkdir(BACKUP, mode=0o700)
            except IOError:
                sftp.stat(BACKUP)
            with sftp.open(BACKUP + "/main_menu.py.before", "wb") as f:
                f.write(original)
            sftp.chmod(BACKUP + "/main_menu.py.before", 0o600)
            upload(sftp, LIVE, desired, mode)
            try:
                remote(t, "systemctl restart basefrom50bot.service", timeout=35)
                time.sleep(8)
                remote(t, "systemctl is-active --quiet basefrom50bot.service && curl -fsS --max-time 8 http://127.0.0.1:8080/health", timeout=20)
                with sftp.open(LIVE, "rb") as f:
                    installed = f.read(300000)
                if blob_sha(installed) != NEW_BLOB:
                    raise RuntimeError("Installed source differs from expected")
            except Exception:
                upload(sftp, LIVE, original, mode)
                remote(t, "systemctl restart basefrom50bot.service", timeout=35)
                raise
            print("Timeweb healthy. Admin-only /setmenu upload is ready.")
            print("DB, existing banner, YooMoney and bot token unchanged.")
        finally:
            sftp.close()
    finally:
        t.close()


if __name__ == "__main__":
    main()
