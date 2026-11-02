"""Read-only investigation of mismatched /stats responses. No user identifiers or secrets."""
import base64
import hashlib
import os
import shlex
import paramiko

HOST = "5.129.247.209"
HOST_KEY = "IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"
REMOTE = r"""
import os
import pathlib
import sqlite3
import subprocess
from datetime import datetime

print("UTC now:", datetime.utcnow().isoformat())
print("== Python bot processes ==")
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    try:
        args = (proc/"cmdline").read_bytes().replace(bytes([0]),b" ").decode(errors="replace")
        if "main.py" not in args or ("basefrom50" not in args and "/opt/bot" not in args):
            continue
        cwd = os.readlink(proc/"cwd")
        env = dict(x.split("=",1) for x in (proc/"environ").read_bytes().decode(errors="replace").split(chr(0)) if "=" in x)
        print("pid:",proc.name,"cwd:",cwd,"command main.py:",args[:220])
        print("db env override:",env.get("DB_PATH","(none)"),"volume:",bool(env.get("RAILWAY_VOLUME_MOUNT_PATH")))
    except (OSError,PermissionError):
        pass

print("== Database snapshots (aggregates only) ==")
paths = [
    "/opt/bot/data/bot.db",
    "/opt/basefrom50-stage/data/bot.db",
    "/opt/bot/bot.db",
    "/opt/basefrom50-stage/bot.db",
    "/opt/bot/data/data/bot.db",
    "/opt/basefrom50-stage/data/data/bot.db",
]
seen = set()
for name in paths:
    path=pathlib.Path(name)
    if not path.exists():
        continue
    real=str(path.resolve())
    if real in seen:
        print(name, "same file as",real)
        continue
    seen.add(real)
    try:
        db=sqlite3.connect("file:"+real+"?mode=ro",uri=True,timeout=5)
        user_count=db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        bought=db.execute("SELECT COUNT(*) FROM users WHERE purchased_guide=1").fetchone()[0]
        events=db.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        opened=db.execute("SELECT COUNT(DISTINCT user_id) FROM events WHERE event_type='view_guide'").fetchone()[0]
        initiated=db.execute("SELECT COUNT(DISTINCT user_id) FROM events WHERE event_type='payment_initiated'").fetchone()[0]
        rev=db.execute("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status IN ('completed','success')").fetchone()[0]
        latest=db.execute("SELECT MAX(created_at) FROM events").fetchone()[0]
        print("file:",real,"users:",user_count,"buyers:",bought,"events:",events,"guide views:",opened,"initiated:",initiated,"revenue:",rev,"latest event:",latest)
        db.close()
    except Exception as exc:
        print("Database read failed:",type(exc).__name__)

print("== systemd service states ==")
for service in ["basefrom50bot.service","bot.service","telegram-bot.service"]:
    result=subprocess.run(["systemctl","show",service,"-p","ActiveState","-p","MainPID","-p","FragmentPath"],capture_output=True,text=True,timeout=8)
    print(service,result.stdout.strip().replace(chr(10),"; "))

print("== All likely Telegram processes on this host ==")
for proc in pathlib.Path("/proc").iterdir():
    if not proc.name.isdigit():
        continue
    try:
        args=(proc/"cmdline").read_bytes().replace(bytes([0]),b" ").decode(errors="replace")
        if not args or proc.name == str(os.getpid()):
            continue
        if any(token in args.lower() for token in ("python","node","bot","telegram","polling","gunicorn","uvicorn")):
            print("pid:",proc.name,"command:",args[:180].replace(chr(10)," "))
    except (OSError,PermissionError):
        pass

print("== Additional runtime inventory ==")
checks = [
    ["systemctl","list-units","--type=service","--state=running","--no-legend","--plain"],
    ["docker","ps","--format","{{.Names}} {{.Image}} {{.Status}}"],
    ["pm2","list","--no-color"],
    ["supervisorctl","status"],
]
for command in checks:
    try:
        p=subprocess.run(command,capture_output=True,text=True,timeout=10)
        lines=[x for x in p.stdout.splitlines() if any(w in x.lower() for w in ("bot","python","node","docker","container","railway","telegram","pm2","supervisor"))]
        print(command[0],":",lines[:15] if lines else "(no relevant entries)")
    except (OSError,subprocess.TimeoutExpired):
        print(command[0],": unavailable")

print("== Polling conflicts (past 72 hours) ==")
r=subprocess.run(["journalctl","-u","basefrom50bot.service","--since","-72 hours","--no-pager","-q"],capture_output=True,text=True,timeout=15)
lines=r.stdout.splitlines()
conflicts=[line for line in lines if "Conflict:" in line or "terminated by other getUpdates" in line]
print("conflict count:",len(conflicts))
print("last conflict:",conflicts[-1][:200] if conflicts else "(none)")
print("recent polling starts:",sum("Polling started" in line for line in lines))
"""
t = paramiko.Transport((HOST,22))
try:
    t.start_client(timeout=12)
    fp=base64.b64encode(hashlib.sha256(t.get_remote_server_key().asbytes()).digest()).decode().rstrip("=")
    if fp!=HOST_KEY: raise RuntimeError("SSH host mismatch")
    t.auth_password("root",os.environ["TIMEWEB_SSH_PASSWORD"],fallback=False)
    if not t.is_authenticated(): raise RuntimeError("SSH authentication failed")
    ch=t.open_session(timeout=10)
    ch.settimeout(55)
    ch.exec_command("python3 -c "+shlex.quote(REMOTE))
    out=ch.makefile("rb").read(10000).decode(errors="replace")
    err=ch.makefile_stderr("rb").read(1500).decode(errors="replace")
    code=ch.recv_exit_status()
    print(out.strip())
    if code: raise RuntimeError("Remote diagnostics failed: "+err[:350])
finally:
    t.close()
