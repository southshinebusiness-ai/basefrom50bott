"""Install BOT_TOKEN on the existing Timeweb stage without logging credentials."""
import base64
import hashlib
import os
import sys
import time
import uuid

import paramiko

HOST = '5.129.247.209'
FINGERPRINT = 'IvZC5ONQ0G6HtVH3efNl7B7VLEjpDujQEYn2iBrNJKI'
REMOTE_SCRIPT = r'''
import json, os, re, subprocess, sys, tempfile, time
import urllib.request, urllib.error
from pathlib import Path
from dotenv import dotenv_values

def main():
    token = sys.stdin.read().strip()
    if not re.fullmatch(r'[0-9]+:[A-Za-z0-9_-]+', token):
        raise RuntimeError('BOT_TOKEN is missing or malformed')
    try:
        with urllib.request.urlopen('https://api.telegram.org/bot' + token + '/getMe', timeout=20) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        print('Telegram rejected the repository token; HTTP', error.code)
        return 1
    except Exception:
        print('Telegram token validation could not connect')
        return 1
    if not result.get('ok'):
        return 1
    print('Telegram identity verified: @' + result['result']['username'], flush=True)
    env_path = Path('/opt/basefrom50-stage/.env')
    text = env_path.read_text()
    values = dotenv_values(env_path)
    if values.get('PAYMENTS_READY') != '0':
        raise RuntimeError('Expected payments to be disabled')
    for key, value in [('BOT_TOKEN', token), ('PAYMENTS_READY', '0')]:
        pattern = r'(?m)^[ \t]*(?:export[ \t]+)?' + key + r'[ \t]*=.*$'
        text, count = re.subn(pattern, lambda match: key + '=' + value, text)
        if count == 0:
            text = text.rstrip('\n') + '\n' + key + '=' + value + '\n'
    backup = env_path.with_name('.env.before-token-' + str(time.time_ns()))
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(env_path.read_bytes())
    fd, temporary = tempfile.mkstemp(prefix='.env.', dir=env_path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, env_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    subprocess.run(['systemctl', 'enable', '--now', 'basefrom50bot.service'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for attempt in range(15):
        time.sleep(2)
        state = subprocess.run(['systemctl', 'is-active', '--quiet', 'basefrom50bot.service']).returncode
        try:
            with urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3) as response:
                healthy = response.status == 200 and 'ok' in response.read(1024).decode().lower()
        except Exception:
            healthy = False
        if state == 0 and healthy:
            print('Bot service active; local HTTP health OK; PAYMENTS_READY=0')
            return 0
    print('Token installed, but service health check failed; inspect server separately')
    return 1

try:
    sys.exit(main())
except Exception as error:
    print('Token installation failed:', type(error).__name__)
    sys.exit(1)
'''


def main():
    password = os.environ.get('TIMEWEB_SSH_PASSWORD', '').strip()
    token = os.environ.get('BOT_TOKEN', '').strip()
    if not password or not token:
        raise RuntimeError('Required repository secrets are missing')
    transport = paramiko.Transport((HOST, 22))
    remote_path = '/root/.basefrom50-refresh-' + uuid.uuid4().hex + '.py'
    sftp = None
    try:
        transport.start_client(timeout=15)
        fingerprint = base64.b64encode(hashlib.sha256(transport.get_remote_server_key().asbytes()).digest()).decode().rstrip('=')
        if fingerprint != FINGERPRINT:
            raise RuntimeError('SSH host key mismatch')
        transport.auth_password('root', password, fallback=False)
        sftp = paramiko.SFTPClient.from_transport(transport)
        with sftp.open(remote_path, 'wx') as out:
            out.write(REMOTE_SCRIPT)
        sftp.chmod(remote_path, 0o600)
        channel = transport.open_session(timeout=15)
        channel.settimeout(150)
        channel.exec_command('/opt/bot/venv/bin/python3 ' + remote_path)
        channel.sendall(token.encode())
        channel.shutdown_write()
        # The remote helper emits only fixed messages and the public bot username.
        output = bytearray()
        deadline = time.monotonic() + 150
        while not channel.exit_status_ready() or channel.recv_ready():
            if time.monotonic() > deadline:
                raise RuntimeError('Remote activation timed out')
            if channel.recv_ready():
                output.extend(channel.recv(4096))
                if len(output) > 10000:
                    raise RuntimeError('Unexpected output volume')
            if channel.recv_stderr_ready():
                channel.recv_stderr(4096)
            time.sleep(0.05)
        print(output.decode(errors='replace').replace(token, '[REDACTED]'))
        if channel.recv_exit_status() != 0:
            raise RuntimeError('Remote token activation failed')
    finally:
        if sftp is not None:
            try:
                sftp.remove(remote_path)
            except OSError:
                pass
            finally:
                sftp.close()
        transport.close()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Activation failed:', type(error).__name__)
        sys.exit(1)
