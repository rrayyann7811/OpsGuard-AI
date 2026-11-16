"""Actual services/RAG/source/Git/SQLite/React; agent is explicitly a TEST DOUBLE, NOT Codex."""
import hashlib
from contextlib import nullcontext
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
PYTHON=ROOT/'backend/.venv/bin/python'
sys.path.insert(0,str(ROOT/'backend/tests'))
from agent_support import git_fixture


def port():
    with socket.socket() as connection:
        connection.bind(('127.0.0.1',0));return connection.getsockname()[1]


def read(url):
    with urlopen(url,timeout=5) as response:return json.load(response)


def wait(url,child):
    for _ in range(200):
        if child.poll() is not None:raise RuntimeError('Test server exited before readiness')
        try:return read(url)
        except OSError:time.sleep(.05)
    raise RuntimeError('Test server did not become ready')


def source_hashes():
    return {str(file.relative_to(ROOT)):hashlib.sha256(file.read_bytes()).hexdigest()
        for name in ('shared','fixtures','user-service','order-service','payment-service')
        for file in (ROOT/'services'/name).glob('*.js')}


def main(local_ollama=False, without_embeddings=False):
    if local_ollama and without_embeddings:
        raise SystemExit('Model-free verification cannot authorize real inference; nothing started.')
    if local_ollama:
        if os.environ.get('OPSGUARD_LIVE_OLLAMA_TEST') != 'I_AUTHORIZE_LOCAL_INFERENCE':
            raise SystemExit('Local inference requires separate explicit authorization; nothing started.')
        selected = os.environ.get('AGENT_OLLAMA_MODEL', '')
        if not selected: raise SystemExit('Select an already installed local model first.')
        sys.path.insert(0,str(ROOT/'backend'))
        import asyncio
        from app.config import Settings
        from app.ollama_adapter import OllamaAdapter
        check=OllamaAdapter(Settings(_env_file=None,agent_execution_enabled=True,
            agent_auth_token='disposable-local-demo',agent_ollama_model=selected))
        if not asyncio.run(check.probe())['available']:
            raise SystemExit('Local runtime/model/memory preflight failed; nothing started.')
        print('GENUINE LOCAL OLLAMA DEMO: no cloud API; runtime must already be running.')
    else:
        print('TEST DOUBLE WORKFLOW ONLY: no live Codex request or AI benchmark.')
    if without_embeddings:
        print('MODEL-FREE CHECK: historical context intentionally unavailable; no semantic retrieval claim.')
    original=source_hashes();processes=[]
    with nullcontext(tempfile.mkdtemp(prefix='opsguard-investigation-test-')) as directory:
        Path(directory).chmod(0o700)
        print('Disposable evidence preserved for owner review: ' + directory, flush=True)
        fixture,sha=git_fixture(Path(directory)/'fixture',ROOT)
        api_port,payment_port=port(),port();api=f'http://127.0.0.1:{api_port}';payment=f'http://127.0.0.1:{payment_port}'
        webhook,agent_token=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        env={**os.environ,'DATABASE_URL':'sqlite:///'+directory+'/incidents.db','QDRANT_URL':'','QDRANT_PATH':directory+'/qdrant',
            'INCIDENT_WEBHOOK_TOKEN':webhook,'AGENT_AUTH_TOKEN':agent_token,'AGENT_CODEX_API_KEY':'','AGENT_EXECUTION_ENABLED':'false',
            'AGENT_PROJECT_ROOT':str(fixture),'MONITOR_ENABLED':'false','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1'}
        if not without_embeddings:
            subprocess.run([str(PYTHON),'-m','app.knowledge_cli','index'],cwd=ROOT/'backend',env=env,stdout=subprocess.DEVNULL,check=True)
        server_code="""import sys,uvicorn
sys.path.insert(0,'tests')
from agent_support import TestAgent
import app.main as main
from app.investigation_worker import InvestigationManager
class DemoManager(InvestigationManager):
    def __init__(self,*args,**kwargs):
        kwargs['adapter']=TestAgent()
        super().__init__(*args,**kwargs)
main.InvestigationManager=DemoManager
uvicorn.run(main.app,host='127.0.0.1',port=int(sys.argv[1]))
"""
        if without_embeddings:
            # Fail closed if any code path unexpectedly tries to initialize embeddings.
            server_code=server_code.replace('import app.main as main', '''from app.knowledge_embeddings import LocalEmbedder, KnowledgeUnavailable

def deny_model_load(self):
    raise KnowledgeUnavailable('Model loading prohibited during model-free verification')
LocalEmbedder.load=deny_model_load
import app.main as main''')
        if local_ollama:
            env.update(AGENT_EXECUTION_BACKEND='local-ollama',AGENT_EXECUTION_ENABLED='true',
                       AGENT_OLLAMA_MODEL=selected,AGENT_MANAGED_ENABLED='false',AGENT_MANAGED_HTTP_ENABLED='false')
            server_code="import sys,uvicorn;from app.main import app;uvicorn.run(app,host='127.0.0.1',port=int(sys.argv[1]))"
        try:
            backend=subprocess.Popen([str(PYTHON),'-c',server_code,str(api_port)],cwd=ROOT/'backend',env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            processes.append(backend);wait(api+'/api/health',backend)
            node=subprocess.Popen(['node','payment-service/index.js'],cwd=ROOT/'services',env={**env,'HOST':'127.0.0.1','PORT':str(payment_port),
                'NODE_ENV':'development','ENABLE_FAULT_INJECTION':'true','INCIDENT_INGESTION_URL':api+'/api/incidents/events'},stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            processes.append(node);wait(payment+'/health',node)
            try:
                urlopen(Request(payment+'/simulate/faulty-commit',data=b'{}',headers={'Content-Type':'application/json'}))
                raise AssertionError('Expected controlled failure')
            except HTTPError as error:assert error.code==500
            for _ in range(100):
                incidents=read(api+'/api/incidents')['items']
                if incidents:break
                time.sleep(.05)
            incident=incidents[0]
            subprocess.run(['npm','test','--','integration/investigation-workflow.test.tsx'],cwd=ROOT/'frontend',env={**env,
                'NEXT_PUBLIC_API_URL':api,'OPSGUARD_INVESTIGATION_DEMO_INCIDENT':incident['id'],
                'OPSGUARD_INVESTIGATION_DEMO_TOKEN':agent_token,'OPSGUARD_INVESTIGATION_DEMO_SHA':sha,
                'OPSGUARD_INVESTIGATION_REAL_LOCAL':'1' if local_ollama else '',
                'OPSGUARD_INVESTIGATION_WITHOUT_EMBEDDINGS':'1' if without_embeddings else ''},check=True)
            with sqlite3.connect(directory+'/incidents.db') as db:
                assert db.execute('select status from incidents').fetchone()[0]=='OPEN'
                status,metadata=db.execute('select status,execution_metadata from investigations').fetchone()
                assert status=='COMPLETED' and json.loads(metadata)['mode']==('local-ollama' if local_ollama else 'test-double')
                if local_ollama:
                    print('Actual local execution metadata:',metadata)
            assert original==source_hashes()
            if local_ollama:
                print('PASS: actual local Ollama response accepted/persisted/displayed; source unchanged. Accuracy not established by one case.')
            else:
                if without_embeddings:
                    with sqlite3.connect(directory+'/incidents.db') as db:
                        report=json.loads(db.execute('select report from investigations').fetchone()[0])
                        assert any('No historical matches' in value for value in report['limitations'])
                    print('PASS: MODEL-FREE Node/ingestion/source/Git/SQLite/report/React with TEST DOUBLE and explicit missing-history limitation; semantic retrieval NOT tested.')
                else:
                    print('PASS: real Node failure/ingestion + actual RAG/source/Git + persistent lifecycle/report + React UI, with explicitly labeled TEST DOUBLE. Original source unchanged. Live Codex NOT tested.')
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':main(local_ollama='--local-ollama' in sys.argv[1:], without_embeddings='--without-embeddings' in sys.argv[1:])
