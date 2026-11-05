"""Deploy the isolated /stats free-guide event-count fix to Timeweb safely.

Only handlers/admin.py is changed. No .env, bot token, payment settings,
or database rows are modified. SQLite is backed up before the restart.
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
LIVE = "/opt/basefrom50-stage/handlers/admin.py"
OLD_BLOB = "9aff0c1ccfb00e16bcedee1ae9e5187fa46bf084"
NEW_BLOB = "85fe8ebb27b5f9efda19337a0b4090e76620f318"
BACKUP = "/root/basefrom50-backups/stats-free-guide-20261105"


def blob_sha(data):
    header = ("blob " + str(len(data)) + "\0").encode()
    return hashlib.sha1(header + data).hexdigest()


def remote(transport, command, timeout=40):
    ch = transport.open_session(timeout=10)
    ch.settimeout(timeout)
    ch.exec_command(command)
    data = ch.makefile("rb").read(3000).decode(errors="replace")
    if ch.recv_exit_status():
        raise RuntimeError("Remote check or service command failed")
    return data.strip()


def upload(sftp, path, content, mode):
    tmp = path + ".stats-new"
    with sftp.open(tmp, "wb") as f:
        f.write(content)
    sftp.chmod(tmp, mode)
    sftp.posix_rename(tmp, path)


def main():
    password = os.environ.get("TIMEWEB_SSH_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("TIMEWEB_SSH_PASSWORD is not configured")
    desired = Path("handlers/admin.py").read_bytes()
    if blob_sha(desired) != NEW_BLOB:
        raise RuntimeError("Release source does not match reviewed /stats change")
    subprocess.run(["python", "-m", "py_compile", "handlers/admin.py"], check=True)

    t = paramiko.Transport((HOST, 22))
    try:
        t.start_client(timeout=12)
        fp = base64.b64encode(
            hashlib.sha256(t.get_remote_server_key().asbytes()).digest()
        ).decode().rstrip("=")
        if fp != HOST_KEY:
            raise RuntimeError("SSH host key mismatch; production untouched")
        t.auth_password("root", password, fallback=False)
        if not t.is_authenticated():
            raise RuntimeError("SSH authentication failed; production untouched")
        remote(t, "systemctl is-active --quiet basefrom50bot.service && test -f /opt/bot/data/bot.db")

        sftp = paramiko.SFTPClient.from_transport(t)
        try:
            with sftp.open(LIVE, "rb") as f:
                original = f.read(300000)
            current_sha = blob_sha(original)
            if current_sha == NEW_BLOB:
                print("The reviewed /stats update is already installed; no changes.")
                return
            if current_sha != OLD_BLOB:
                raise RuntimeError(
                    "Live admin.py differs from reviewed original; refusing to overwrite it"
                )
            mode = sftp.stat(LIVE).st_mode & 0o777

            # Keep a copy of original source and a consistent SQLite backup.
            try:
                sftp.mkdir(BACKUP, mode=0o700)
            except IOError:
                if not sftp.stat(BACKUP).st_mode:
                    raise
            with sftp.open(BACKUP + "/admin.py.before", "wb") as f:
                f.write(original)
            sftp.chmod(BACKUP + "/admin.py.before", 0o600)
            remote(t, "python3 -c 'import sqlite3; a=sqlite3.connect(\"/opt/bot/data/bot.db\"); b=sqlite3.connect(\"/root/basefrom50-backups/stats-free-guide-20261105/bot.db\"); a.backup(b); b.close(); a.close()'")
            sftp.chmod(BACKUP + "/bot.db", 0o600)
            print("Original source and live SQLite backed up on Timeweb.")

            upload(sftp, LIVE, desired, mode)
            try:
                remote(t, "systemctl restart basefrom50bot.service", timeout=35)
                time.sleep(8)
                remote(t, "systemctl is-active --quiet basefrom50bot.service && curl -fsS --max-time 8 http://127.0.0.1:8080/health", timeout=20)
                with sftp.open(LIVE, "rb") as f:
                    installed = f.read(300000)
                if blob_sha(installed) != NEW_BLOB:
                    raise RuntimeError("Post-release source verification failed")
            except Exception:
                print("Post-release check failed; restoring previous source.")
                upload(sftp, LIVE, original, mode)
                remote(t, "systemctl restart basefrom50bot.service", timeout=35)
                raise

            print("Timeweb bot active; local health OK.")
            print("/stats free-guide event counts fixed; live DB and payment configuration unchanged.")
        finally:
            sftp.close()
    finally:
        t.close()


if __name__ == "__main__":
    main()
