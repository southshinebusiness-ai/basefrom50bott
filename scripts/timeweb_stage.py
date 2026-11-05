"""Stage a new bot release on Timeweb without touching the running application.

Uses GitHub encrypted Actions secrets, never prints credentials. The current
/opt/bot tree, .env, SQLite and systemd remain untouched. Checkout disabled.
"""
import base64
import hashlib
import io
import os
from pathlib import Path
import subprocess
import tarfile

import paramiko

HOST = "5.129.247.209"
FINGERPRINT = "IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"
STAGE = "/opt/basefrom50-stage"
ARCHIVE = "/root/basefrom50-stage-code.tar.gz"


def ssh_command(transport, command, timeout=50):
    channel = transport.open_session(timeout=10)
    channel.settimeout(timeout)
    channel.exec_command(command)
    data = bytearray()
    while not channel.exit_status_ready() or channel.recv_ready():
        if channel.recv_ready():
            data.extend(channel.recv(4096))
            if len(data) > 10000:
                raise RuntimeError("excessive command output")
    code = channel.recv_exit_status()
    return code, data.decode(errors="replace").strip()


def create_archive():
    paths = subprocess.check_output(["git", "ls-files", "-z"]).split(b"\0")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as archive:
        for raw in paths:
            if not raw:
                continue
            path = Path(os.fsdecode(raw))
            if not path.is_file() or path.is_symlink():
                continue
            if path.parts[0] in {".github", "docs", "tests", "scripts"}:
                continue
            archive.add(str(path), arcname=str(path), recursive=False)
    buf.seek(0)
    return buf


def modify_env(raw, secret):
    if not secret or "\n" in secret or "\r" in secret:
        raise ValueError("invalid YooMoney secret")
    # Existing values remain unchanged; no original secrets are printed.
    lines = [x for x in raw.splitlines() if not x.startswith(("YOOMONEY_SECRET=", "PAYMENTS_READY="))]
    lines += ["YOOMONEY_SECRET=" + secret, "PAYMENTS_READY=0"]
    return "\n".join(lines).rstrip() + "\n"


def main():
    password = os.environ.get("TIMEWEB_SSH_PASSWORD", "").strip()
    secret = os.environ.get("YOOMONEY_SECRET", "").strip()
    if not password or not secret:
        raise RuntimeError("Required protected GitHub Actions secrets missing")
    transport = paramiko.Transport((HOST, 22))
    try:
        transport.start_client(timeout=12)
        fp = base64.b64encode(hashlib.sha256(transport.get_remote_server_key().asbytes()).digest()).decode().rstrip("=")
        if fp != FINGERPRINT:
            raise RuntimeError("Server SSH host key mismatch")
        transport.auth_password("root", password, fallback=False)
        if not transport.is_authenticated():
            raise RuntimeError("SSH auth failed")

        status, output = ssh_command(transport, "test ! -e /opt/basefrom50-stage && test -f /opt/bot/.env && test -d /opt/bot/data && echo ready")
        if status != 0 or output != "ready":
            raise RuntimeError("Stage already exists or current deployment files unavailable")
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            with sftp.open("/opt/bot/.env", "rb") as f:
                env_bytes = f.read(65536)
            if len(env_bytes) > 65000:
                raise RuntimeError("Existing env file unexpectedly large")
            env = modify_env(env_bytes.decode("utf-8"), secret)
            code_archive = create_archive()
            with sftp.open(ARCHIVE, "wb") as remote:
                remote.write(code_archive.read())
            sftp.chmod(ARCHIVE, 0o600)
            code = r'''import os, pathlib, tarfile
root = pathlib.Path("/opt/basefrom50-stage")
root.mkdir(mode=0o700)
with tarfile.open("/root/basefrom50-stage-code.tar.gz", "r:gz") as tar:
    for item in tar:
        path = pathlib.PurePosixPath(item.name)
        if path.is_absolute() or ".." in path.parts or not item.isfile():
            raise RuntimeError("unsafe archive entry")
        dest = root.joinpath(*path.parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tar.extractfile(item) as source, dest.open("wb") as out:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
(root / "data").symlink_to("/opt/bot/data", target_is_directory=True)
os.remove("/root/basefrom50-stage-code.tar.gz")
print("Staged source files without modifying live bot")
'''
            cmd = "python3 -c 'import base64; exec(base64.b64decode(\"" + base64.b64encode(code.encode()).decode() + "\"))'"
            status, output = ssh_command(transport, cmd, timeout=70)
            if status != 0:
                raise RuntimeError("Remote staging failed")
            print(output)
            with sftp.open(STAGE + "/.env", "wb") as f:
                f.write(env.encode("utf-8"))
            sftp.chmod(STAGE + "/.env", 0o600)
            check = (
                "cd /opt/basefrom50-stage && "
                "/opt/bot/venv/bin/python3 -m compileall -q "
                "main.py config.py handlers utils db content && "
                "/opt/bot/venv/bin/python3 -c "
                "'import config, main; print(\"Imports successful; payments ready:\", config.config.PAYMENTS_READY, \"; webhook secret configured:\", bool(config.config.YOOMONEY_SECRET))'"
            )
            status, output = ssh_command(transport, check, timeout=40)
            if status != 0:
                raise RuntimeError("Staged import/compile validation failed")
            print(output)
            print("Stage ready. Production service, database, and original .env untouched.")
        finally:
            sftp.close()
    finally:
        transport.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("Staging failed:", type(exc).__name__, str(exc) if str(exc) in {"Required protected GitHub Actions secrets missing", "Server SSH host key mismatch", "SSH auth failed", "Stage already exists or current deployment files unavailable", "Existing env file unexpectedly large", "Remote staging failed", "Staged import/compile validation failed"} else "")
        raise SystemExit(1)
