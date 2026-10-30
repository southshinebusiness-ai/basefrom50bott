"""Read-only confirmation of a unique second-account test deep link."""
import base64,hashlib,os,shlex,paramiko
HOST="5.129.247.209"
FINGERPRINT="IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"
remote_code = """
import sqlite3
con=sqlite3.connect("/opt/bot/data/bot.db")
con.row_factory=sqlite3.Row
rows=con.execute("SELECT DISTINCT user_id FROM events WHERE event_type='start' AND json_extract(data,'$.payload')=? AND created_at>=datetime('now','-24 hours')",("paytest_7e4c92a1f6b8",)).fetchall()
print("Matched Telegram profiles:",len(rows))
if len(rows)==1:
    user=con.execute("SELECT purchased_guide FROM users WHERE user_id=?",(rows[0]["user_id"],)).fetchone()
    print("Profile registered:",bool(user))
    print("Already purchased:",bool(user and user["purchased_guide"]))
"""
t=paramiko.Transport((HOST,22))
try:
    t.start_client(timeout=12)
    fp=base64.b64encode(hashlib.sha256(t.get_remote_server_key().asbytes()).digest()).decode().rstrip("=")
    if fp!=FINGERPRINT: raise RuntimeError("Host mismatch")
    t.auth_password("root",os.environ["TIMEWEB_SSH_PASSWORD"],fallback=False)
    if not t.is_authenticated(): raise RuntimeError("Authentication failed")
    ch=t.open_session(timeout=10)
    ch.settimeout(20)
    ch.exec_command("python3 -c "+shlex.quote(remote_code))
    out=ch.makefile("rb").read(2000).decode(errors="replace")
    err=ch.makefile_stderr("rb").read(1000).decode(errors="replace")
    status=ch.recv_exit_status()
    print(out.strip())
    if status: raise RuntimeError("Read-only check failed: "+err[:250])
finally:
    t.close()
