"""Actual local model/Qdrant/API/React integration. No network response mocks."""
from contextlib import nullcontext
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from uuid import uuid4
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / 'backend/.venv/bin/python'


def main():
    with nullcontext(tempfile.mkdtemp(prefix='opsguard-rag-integration-')) as directory:
        Path(directory).chmod(0o700)
        print('Disposable evidence preserved for owner review: ' + directory, flush=True)
        with socket.socket() as socket_:
            socket_.bind(('127.0.0.1', 0)); port = socket_.getsockname()[1]
        token = secrets.token_urlsafe(32)
        env = {**os.environ, 'DATABASE_URL':'sqlite:///' + directory + '/incidents.db',
            'AGENT_MANAGED_ENABLED':'false','AGENT_MANAGED_HTTP_ENABLED':'false','AGENT_EXECUTION_ENABLED':'false','QDRANT_URL':'', 'QDRANT_PATH':directory+'/qdrant', 'MONITOR_ENABLED':'false',
            'INCIDENT_WEBHOOK_TOKEN':token, 'HF_HUB_OFFLINE':'1', 'TRANSFORMERS_OFFLINE':'1'}
        subprocess.run([str(PYTHON), '-m', 'app.knowledge_cli', 'index'], cwd=ROOT/'backend', env=env, stdout=subprocess.DEVNULL, check=True)
        process = subprocess.Popen([str(PYTHON), '-m', 'uvicorn', 'app.main:app', '--host','127.0.0.1','--port',str(port)], cwd=ROOT/'backend', env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        api = f'http://127.0.0.1:{port}'
        try:
            for _ in range(200):
                if process.poll() is not None: raise RuntimeError('FastAPI exited before readiness')
                try:
                    with urlopen(api+'/api/knowledge/status', timeout=1) as response:
                        assert json.load(response)['indexed_incidents'] == 24
                    break
                except OSError: time.sleep(.05)
            event = dict(event_id=str(uuid4()), service_name='payment-service',timestamp=datetime.now(timezone.utc).isoformat(),
                severity='error',error_type='CalculationRegression',error_message='Payment total violated fee invariant',
                stack_trace='Fee subtraction detected\n at calculate (/app/payment.js:4:2)',http_status=500,
                request_id=str(uuid4()),endpoint='/payments',duration_ms=1)
            request = Request(api+'/api/incidents/events', data=json.dumps(event).encode(), headers={'Content-Type':'application/json','Authorization':'Bearer '+token})
            with urlopen(request) as response: incident = json.load(response)['incident']
            subprocess.run(['npm','test','--','integration/live-knowledge.test.tsx'], cwd=ROOT/'frontend',
                env={**env,'NEXT_PUBLIC_API_URL':api,'OPSGUARD_LIVE_KNOWLEDGE_ID':incident['id']}, check=True)
            with sqlite3.connect(directory+'/incidents.db') as db:
                assert db.execute('select status, occurrence_count from incidents').fetchone() == ('OPEN',1)
            print('PASS: real offline model -> persistent local Qdrant -> FastAPI -> React search/detail/similar UI; operational SQLite incident unchanged')
        finally:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait()


if __name__ == '__main__': main()
