"""Check public HTTPS YooMoney webhook without making a payment."""
import urllib.request
import urllib.error
import time

base = "https://5.129.247.209"
for attempt in range(5):
    try:
        with urllib.request.urlopen(base + "/health", timeout=10) as response:
            assert response.status == 200
            assert response.read(100).decode().strip() == "ok"
        print("Public HTTPS health: 200 OK")
        break
    except urllib.error.HTTPError as error:
        print("HTTPS health attempt", attempt + 1, "returned HTTP", error.code)
    except Exception as error:
        print("HTTPS health attempt", attempt + 1, type(error).__name__)
    time.sleep(3)
else:
    raise SystemExit("Public HTTPS health not reliably available")

def post(payload):
    req = urllib.request.Request(
        base + "/yoomoney/notify",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, response.read(100).decode(errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read(100).decode(errors="replace")

code, body = post(b"")
assert code == 200 and "test ok" in body, (code, body)
print("YooMoney empty test notification: 200 test ok")

code, body = post(b"notification_type=p2p-incoming&label=smoke-test-invalid&sign=invalid")
assert code == 403, (code, body)
print("YooMoney forged notification: 403 rejected")
