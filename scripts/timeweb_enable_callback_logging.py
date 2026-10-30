"""Enable request-status logging only for YooMoney callback on Timeweb.

No tokens or payment payloads are logged by this script. Backs up nginx site,
tests nginx configuration before reload, and restores on failed config check.
"""
import base64
import hashlib
import os
import shlex
import time

import paramiko

HOST="5.129.247.209"
FINGERPRINT="IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"

def command(t,cmd):
    ch=t.open_session(timeout=10)
    ch.settimeout(20)
    ch.exec_command(cmd)
    out=ch.makefile("rb").read(2500).decode(errors="replace").strip()
    err=ch.makefile_stderr("rb").read(1000).decode(errors="replace").strip()
    return ch.recv_exit_status(),out,err

t=paramiko.Transport((HOST,22))
try:
    t.start_client(timeout=12)
    fp=base64.b64encode(hashlib.sha256(t.get_remote_server_key().asbytes()).digest()).decode().rstrip("=")
    if fp != FINGERPRINT:
        raise SystemExit("SSH fingerprint mismatch")
    t.auth_password("root",os.environ["TIMEWEB_SSH_PASSWORD"],fallback=False)
    if not t.is_authenticated():
        raise SystemExit("SSH authentication failed")
    status,out,err=command(t,"grep -Rl 'location = /yoomoney/notify' /etc/nginx/sites-enabled 2>/dev/null")
    files=[p for p in out.splitlines() if p.startswith("/etc/nginx/sites-enabled/")]
    if status or len(files)!=1:
        raise SystemExit("Expected exactly one active webhook site")
    sftp=paramiko.SFTPClient.from_transport(t)
    try:
        site=files[0]
        with sftp.open(site,"rb") as f:
            current=f.read(200000)
        marker=b"location = /yoomoney/notify {"
        if current.count(marker)!=1:
            raise SystemExit("Unexpected Nginx site config")
        # Enable normal Nginx access logging in webhook location. Server-level
        # access_log off remains in effect for unrelated endpoints.
        location=current.split(marker,1)[1].split(b"}",1)[0]
        if b"access_log /var/log/nginx/access.log;" in location:
            print("Webhook access logging already enabled.")
        else:
            if b"access_log" in location:
                raise SystemExit("Unexpected existing access log directive")
            updated=current.replace(marker,marker+b"\n        access_log /var/log/nginx/access.log;",1)
            # Work with resolved path so an enabled-site symlink is preserved.
            status,resolved,err=command(t,"readlink -f "+shlex.quote(site))
            if status or not resolved.startswith("/etc/nginx/"):
                raise SystemExit("Unexpected config path")
            backup=resolved+".before-webhook-logging"
            with sftp.open(backup,"wb") as f:
                f.write(current)
            sftp.chmod(backup,0o600)
            tmp=resolved+".tmp-webhook-logging"
            with sftp.open(tmp,"wb") as f:
                f.write(updated)
            sftp.chmod(tmp,0o644)
            status,_,err=command(t,"mv "+shlex.quote(tmp)+" "+shlex.quote(resolved)+" && nginx -t")
            if status:
                command(t,"cp "+shlex.quote(backup)+" "+shlex.quote(resolved)+" && nginx -t")
                raise SystemExit("Nginx config invalid; original restored")
            status,_,err=command(t,"systemctl reload nginx")
            if status:
                command(t,"cp "+shlex.quote(backup)+" "+shlex.quote(resolved)+" && systemctl reload nginx")
                raise SystemExit("Nginx reload failed; original restored")
            print("Enabled callback-only Nginx request logging; nginx reload succeeded.")
    finally:
        sftp.close()
    status,out,err=command(t,"curl -ksS --max-time 6 -o /dev/null -w '%{http_code}' -X POST https://127.0.0.1/yoomoney/notify")
    if status or out!="200":
        raise SystemExit("Webhook self-test failed")
    time.sleep(1)
    status,out,err=command(t,"grep '/yoomoney/notify' /var/log/nginx/access.log | tail -n 1 | awk '{print $4,$5,$7,$9}'")
    if status or "200" not in out:
        raise SystemExit("Webhook test did not appear in access log")
    print("Webhook self-test logged:",out)
    status,out,err=command(t,"systemctl is-active basefrom50bot.service")
    if status or out!="active":
        raise SystemExit("Bot service is not active")
    print("Bot service remains active. Payment checkout unchanged.")
finally:
    t.close()
