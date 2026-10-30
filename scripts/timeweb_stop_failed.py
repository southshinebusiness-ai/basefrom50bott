"""Stop a failed bot service restart loop after Telegram rejects its token."""
import os
import base64
import hashlib
import paramiko

host="5.129.247.209"
fingerprint="IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"
password=os.environ.get("TIMEWEB_SSH_PASSWORD","").strip()
if not password: raise SystemExit("SSH password secret unavailable")
t=paramiko.Transport((host,22))
try:
    t.start_client(timeout=12)
    got=base64.b64encode(hashlib.sha256(t.get_remote_server_key().asbytes()).digest()).decode().rstrip("=")
    if got!=fingerprint: raise SystemExit("Host key mismatch")
    t.auth_password("root",password,fallback=False)
    if not t.is_authenticated(): raise SystemExit("SSH auth failed")
    ch=t.open_session(timeout=10)
    ch.settimeout(25)
    ch.exec_command("systemctl disable --now basefrom50bot.service >/dev/null 2>&1 && systemctl is-active basefrom50bot.service || true")
    data=bytearray()
    while not ch.exit_status_ready() or ch.recv_ready():
        if ch.recv_ready():data.extend(ch.recv(1024))
    ch.recv_exit_status()
    print("Bot service state after stopping failed restarts:",data.decode(errors="replace").strip())
    print("Existing database, staged code and YooMoney secret preserved.")
finally:
    t.close()
