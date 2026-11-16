"""Real stateless FastAPI/React integration; no database, model or external service."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
ROOT = Path(__file__).resolve().parents[1]


def main():
    directory = Path(tempfile.mkdtemp(prefix='opsguard-hosted-check-'))
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
    api = f'http://127.0.0.1:{port}'
    env = {**os.environ, 'CORS_ORIGINS': '[]', 'PYTHONDONTWRITEBYTECODE': '1', 'DATABASE_URL': 'sqlite:///' + str(directory/'must-not-exist.db')}
    with (directory/'api.log').open('w') as log:
        child = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.hosted:app', '--host', '127.0.0.1', '--port', str(port)], cwd=ROOT/'backend', env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(200):
                if child.poll() is not None: raise RuntimeError('Hosted API exited')
                try:
                    with urlopen(api+'/api/health', timeout=1) as response: health=json.load(response)
                    break
                except OSError: time.sleep(.05)
            else: raise RuntimeError('Hosted API readiness timeout')
            assert health['storage']=='stateless' and health['database']=='not_configured'
            try:
                urlopen(Request(api+'/api/incidents/events',data=b'{}',headers={'Content-Type':'application/json'}))
                raise AssertionError('Mutation accepted')
            except HTTPError as error: assert error.code==403
            subprocess.run(['npm','test','--','integration/hosted-api.test.tsx'],cwd=ROOT/'frontend',env={**env,'NEXT_PUBLIC_API_URL':api,'NEXT_PUBLIC_HOSTED_API':'true','NEXT_PUBLIC_DEMO_MODE':'false','OPSGUARD_HOSTED_API_TEST_URL':api},check=True)
            assert not (directory/'must-not-exist.db').exists()
            print('PASS: real stateless FastAPI -> React seven-page contract; writes denied; no DB/model. Evidence:',directory)
        finally:
            child.terminate()
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired: child.kill();child.wait()


if __name__=='__main__': main()
