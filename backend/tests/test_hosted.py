import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from app.hosted import HostedSettings, create_app


def test_hosted_health_counts_and_no_fabricated_monitoring():
    with TestClient(create_app(HostedSettings(cors_origins=[]))) as client:
        health = client.get('/api/health').json()
        assert health['database'] == 'not_configured' and health['storage'] == 'stateless'
        assert not any(health['capabilities'].values())
        assert client.get('/api/incidents').json()['total'] == 0
        assert client.get('/api/incidents/summary').json()['history'] == []
        assert client.get('/api/investigations').json()['items'] == []
        assert client.get('/api/investigations/configuration').json()['available'] is False
        assert client.get('/api/investigations/readiness').json()['can_start'] is False
        for service in client.get('/api/services').json()['items']:
            assert service['status'] == 'Unknown' and service['last_attempt'] is None
        assert client.get('/api/knowledge/status').json()['status'] == 'unavailable'
        assert client.get('/api/knowledge/incidents').status_code == 503
        assert client.get('/api/incidents?page=0').status_code == 422


@pytest.mark.parametrize('path,method', [('/api/incidents/events','post'),('/api/incidents/example/status','patch'),('/api/incidents/example/investigate','post'),('/api/knowledge/search','post'),('/api/investigations/runtime/acknowledge-stop','post')])
def test_hosted_denies_mutations_even_with_credentials(path, method):
    with TestClient(create_app(HostedSettings(cors_origins=[]))) as client:
        assert getattr(client,method)(path,json={},headers={'Authorization':'Bearer synthetic-test-token'}).status_code == 403


def test_hosted_cors_exact_allowed_origin_and_denial():
    with TestClient(create_app(HostedSettings(cors_origins=['https://owner-example.vercel.app']))) as client:
        for origin, expected in [('https://owner-example.vercel.app',200),('https://untrusted.invalid',400)]:
            response=client.options('/api/health',headers={'Origin':origin,'Access-Control-Request-Method':'GET'})
            assert response.status_code == expected
            assert response.headers.get('access-control-allow-origin') == (origin if expected==200 else None)
        assert client.options('/api/incidents/events',headers={'Origin':'https://owner-example.vercel.app','Access-Control-Request-Method':'POST'}).status_code == 400


@pytest.mark.parametrize('origin',['*','http://localhost:3000','https://127.0.0.1','https://a.vercel.app/path','https://user:password@a.vercel.app','https://a.vercel.app/'])
def test_hosted_rejects_unsafe_cors(origin):
    with pytest.raises(ValidationError): HostedSettings(cors_origins=[origin])


def test_hosted_fresh_process_never_imports_runtime_or_creates_database(tmp_path):
    code="""import socket,sys
socket.create_connection=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network forbidden'))
from app.hosted import app
from fastapi.testclient import TestClient
with TestClient(app) as client:
    assert client.get('/api/health').json()['storage']=='stateless'
    assert client.get('/api/investigations/configuration').json()['available'] is False
assert not {'app.main','app.database','app.investigation_worker','app.knowledge_store','app.ollama_adapter'}.intersection(sys.modules)
"""
    env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]),'PYTHONDONTWRITEBYTECODE':'1','CORS_ORIGINS':'[]','DATABASE_URL':'sqlite:///'+str(tmp_path/'must-not-exist.db'),'AGENT_EXECUTION_ENABLED':'true','MONITOR_ENABLED':'true'}
    subprocess.run([sys.executable,'-c',code],cwd=tmp_path,env=env,check=True,capture_output=True)
    assert not (tmp_path/'must-not-exist.db').exists()
