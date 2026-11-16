"""Explicit TEST DOUBLE only. Never used as a runtime fallback or AI accuracy benchmark."""
import asyncio
from pathlib import Path
import shutil
import subprocess


def git_fixture(path, project):
    root=Path(path).resolve();root.mkdir(parents=True,exist_ok=True)
    for directory in ['shared','fixtures','user-service','order-service','payment-service']:
        target=root/'services'/directory;target.mkdir(parents=True,exist_ok=True)
        for source in (Path(project)/'services'/directory).glob('*.js'):
            shutil.copyfile(source,target/source.name)
    file=root/'services/fixtures/faulty-commit.js'
    file.write_text('export const total = amount => amount + Math.round(amount * 0.02);\n')
    def git(*args):
        return subprocess.run(['git','-c','core.hooksPath=/dev/null','-C',str(root),*args],env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null',
            'GIT_AUTHOR_NAME':'OpsGuard Synthetic Fixture','GIT_AUTHOR_EMAIL':'fixture@example.invalid','GIT_COMMITTER_NAME':'OpsGuard Synthetic Fixture','GIT_COMMITTER_EMAIL':'fixture@example.invalid',
            'GIT_AUTHOR_DATE':'2026-01-01T00:00:00Z','GIT_COMMITTER_DATE':'2026-01-01T00:00:00Z'},text=True,capture_output=True,check=True).stdout.strip()
    git('init');git('add','services');git('commit','-m','Synthetic fixture: correct fee addition')
    file.write_text('export const total = amount => amount - Math.round(amount * 0.02);\n')
    git('add','services/fixtures/faulty-commit.js');git('commit','-m','Synthetic faulty fixture: subtract processing fee')
    return root,git('rev-parse','HEAD')


class TestAgent:
    mode='test-double'
    def status(self): return {'available':True,'mode':self.mode,'message':'Explicit deterministic test double; not Codex execution.'}
    async def run(self,bundle):
        log=next(item for item in bundle['evidence'] if item['kind']=='log')
        source=next((item for item in bundle['evidence'] if item['kind']=='source'),None)
        refs=[log['id']]+([source['id']] if source else [])
        finding=lambda classification,statement:{'classification':classification,'statement':statement,'evidence_ids':refs}
        return {'analysis':{'error_summary':'Deterministic test-double report for collected failure evidence.',
            'suspected_root_cause':finding('uncertain','Test double does not infer a real root cause; inspect the collected controlled-failure evidence.'),
            'verified_facts':[finding('verified_fact','The application collected persisted incident evidence.')],
            'explanation':[finding('uncertain','This output verifies application wiring only, not AI reasoning.')],
            'affected_files':([{'path':source['path'],'start_line':source['start_line'],'end_line':source['end_line'],'evidence_id':source['id']}] if source else []),
            'suspected_commits':[],'historical_references':[],
            'recommended_remediation':[finding('recommendation','Review the evidence manually before deciding any corrective action.')],
            'limitations':['TEST DOUBLE: no live Codex reasoning or model benchmark was performed.']},
            'metadata':{'mode':self.mode,'provider':'deterministic-test-double'}}
