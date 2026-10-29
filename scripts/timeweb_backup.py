"""Create a root-only on-server backup before changing production.

Credentials come from GitHub encrypted Actions secrets, never from code.
Backup stays on the Timeweb server; no customer data is uploaded to GitHub.
"""
import base64
import hashlib
import json
import os
import sys
from urllib.request import Request, urlopen

import paramiko

HOST = "5.129.247.209"
HOST_KEY = "IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"
REMOTE_SCRIPT = r'''
import datetime
import os
import pathlib
import sqlite3
import subprocess
import tarfile

os.umask(0o077)
root = pathlib.Path("/opt/bot")
assert root.is_dir()
database = root / "data" / "bot.db"
assert database.is_file()
target = pathlib.Path("/root/basefrom50-backups") / datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
target.mkdir(mode=0o700, parents=True, exist_ok=False)

source = sqlite3.connect("file:/opt/bot/data/bot.db?mode=ro", uri=True)
dest = sqlite3.connect(str(target / "bot.db"))
source.backup(dest)
source.close()
assert dest.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
dest.close()

with tarfile.open(target / "bot-files.tar.gz", "w:gz") as tar:
    for path, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in (".git", "venv", ".venv", "__pycache__", "backups")]
        for name in files:
            file = pathlib.Path(path) / name
            if name in ("bot.db", "bot.db-wal", "bot.db-shm", "bot.log") or not file.is_file():
                continue
            tar.add(file, arcname=str(file.relative_to(root)), recursive=False)

with (target / "local-changes.patch").open("wb") as out:
    subprocess.run(["git", "-C", str(root), "diff", "--binary"], stdout=out, stderr=subprocess.DEVNULL, check=True, timeout=20)

for file in target.iterdir():
    file.chmod(0o600)
print("Backup created on Timeweb server; folder:", target.name)
print("SQLite backup integrity: ok")
print("App archive bytes:", (target / "bot-files.tar.gz").stat().st_size)
'''


def main():
    token = os.environ.get("TIMEWEB_API_TOKEN", "").strip()
    password = os.environ.get("TIMEWEB_SSH_PASSWORD", "").strip()
    if not token or not password:
        print("Backup not attempted: missing GitHub Actions secret")
        return 1

    req = Request("https://api.timeweb.cloud/api/v1/servers", headers={
        "Authorization": "Bearer " + token, "Accept": "application/json"
    })
    with urlopen(req, timeout=12) as response:
        servers = json.load(response).get("servers", [])
    if len([s for s in servers if s.get("name") == "Honest Plover" and s.get("status") == "on"]) != 1:
        print("Backup not attempted: target server not uniquely identified and running")
        return 1

    transport = paramiko.Transport((HOST, 22))
    try:
        transport.banner_timeout = 10
        transport.auth_timeout = 10
        transport.start_client(timeout=12)
        fingerprint = base64.b64encode(
            hashlib.sha256(transport.get_remote_server_key().asbytes()).digest()
        ).decode("ascii").rstrip("=")
        if fingerprint != HOST_KEY:
            print("Backup not attempted: SSH host key mismatch")
            return 1
        transport.auth_password("root", password, fallback=False)
        if not transport.is_authenticated():
            print("Backup not attempted: SSH authentication failed")
            return 1
        script = base64.b64encode(REMOTE_SCRIPT.encode("utf-8")).decode("ascii")
        command = "python3 -c 'import base64; exec(base64.b64decode(\"" + script + "\"))'"
        channel = transport.open_session(timeout=15)
        channel.settimeout(90)
        channel.exec_command(command)
        output = bytearray()
        while not channel.exit_status_ready() or channel.recv_ready():
            if channel.recv_ready():
                output.extend(channel.recv(4096))
                if len(output) > 4096:
                    raise RuntimeError("unexpectedly long backup output")
        code = channel.recv_exit_status()
        if code != 0:
            print("Backup failed on server (nonzero exit status); do not deploy")
            return 1
        print(output.decode("utf-8", errors="replace").strip())
        return 0
    except Exception as exc:
        print("Backup not completed:", type(exc).__name__)
        return 1
    finally:
        transport.close()


if __name__ == "__main__":
    sys.exit(main())
