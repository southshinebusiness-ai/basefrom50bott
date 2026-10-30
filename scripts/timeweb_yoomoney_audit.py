# Check receipt of repeated YooMoney provider test after callback logging enabled.
"""Read-only status of YooMoney notifications received by Nginx on Timeweb."""
import base64
import hashlib
import os
import paramiko

HOST="5.129.247.209"
FINGERPRINT="IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI"
t=paramiko.Transport((HOST,22))
try:
    t.start_client(timeout=12)
    fp=base64.b64encode(hashlib.sha256(t.get_remote_server_key().asbytes()).digest()).decode().rstrip("=")
    if fp != FINGERPRINT:
        raise SystemExit("SSH host mismatch")
    t.auth_password("root",os.environ["TIMEWEB_SSH_PASSWORD"],fallback=False)
    if not t.is_authenticated():
        raise SystemExit("SSH auth failed")
    checks={
        "Service status":"systemctl is-active basefrom50bot.service || true",
        "Recent service restarts":"systemctl show basefrom50bot.service -p NRestarts -p ActiveEnterTimestamp",
        "YooMoney notification requests last 30m":"journalctl -u nginx --since '-30 min' --no-pager -q 2>/dev/null | grep -c '/yoomoney/notify' || true",
        "All nginx log filenames": "find /var/log/nginx -maxdepth 1 -type f -printf '%f %s bytes\\n' | head -n 15 || true",
        "Nginx access_log config": "grep -RhE '^[[:space:]]*access_log' /etc/nginx/nginx.conf /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null | head -n 15 || true",
        "Nginx notification route config": "grep -Rh -A 9 -B 2 'location = /yoomoney/notify' /etc/nginx/sites-enabled /etc/nginx/conf.d 2>/dev/null | sed -E 's/(proxy_set_header [^ ]+ ).*/\\1[REDACTED];/' | head -n 18 || true",
        "Nginx log files": "find /var/log/nginx -maxdepth 1 -name 'access.log*' -type f -printf '%f %s bytes\\n' | head -n 8 || true",
        "Nginx callback status counts":"find /var/log/nginx -maxdepth 1 -name 'access.log*' -mmin -180 -type f -print0 | xargs -0 -r grep -h '/yoomoney/notify' | tail -n 100 | awk '{print $9}' | sort | uniq -c || true",
        "Recent callback status codes":"find /var/log/nginx -maxdepth 1 -name 'access.log*' -mmin -180 -type f -print0 | xargs -0 -r grep -h '/yoomoney/notify' | tail -n 12 | awk '{print $4,$5,$6,$7,$9}' || true",
        "Nginx recent request status summary": "find /var/log/nginx -maxdepth 1 -name 'access.log*' -mmin -180 -type f -print0 | xargs -0 -r grep -hE '(/health|/yoomoney/notify)' | tail -n 25 | awk '{print $4,$5,$7,$9}' || true",
        "All nginx callback counts": "find /var/log/nginx -maxdepth 1 -type f -name '*.log' -print0 | xargs -0 -r grep -h '/yoomoney/notify' | tail -n 25 | awk '{print $4,$5,$7,$9}' || true",
        "YooMoney integration variables": "awk -F= '/^(YOOMONEY_SECRET|YOOMONEY_TOKEN|YOOMONEY_WALLET|PRICE_ULTIMATE_GUIDE|BOT_TOKEN|PRIVATE_CHANNEL_ID)=/ {key=$1; val=substr($0,length(key)+2); if(key ~ /SECRET|TOKEN|WALLET|CHANNEL/) {print key, (length(val)>0 ? \"configured\" : \"missing\")} else print key,val}' /opt/basefrom50-stage/.env | sort",
        "YooMoney payment flag":"grep '^PAYMENTS_READY=' /opt/basefrom50-stage/.env || true",
        "Public webhook route":"grep -Rh 'location = /yoomoney/notify' /etc/nginx/sites-enabled 2>/dev/null | head -n 1 || true",
    }
    for label,cmd in checks.items():
        ch=t.open_session(timeout=10)
        ch.settimeout(15)
        ch.exec_command(cmd)
        out=ch.makefile("rb").read(2500).decode(errors="replace").strip()
        ch.recv_exit_status()
        print(label+":",out or "(none)")
finally:
    t.close()
