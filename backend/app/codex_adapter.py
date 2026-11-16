"""One paid SDK turn only after application/per-request authorization. No fake fallback."""
import asyncio
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import tempfile
import time
from app.agent_reports import AgentAnalysis

AGENT_DIR = Path(__file__).resolve().parents[2]/'agent'


class AgentUnavailable(RuntimeError): pass


def resource_bounds():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
    resource.setrlimit(resource.RLIMIT_FSIZE,(8*1024*1024,8*1024*1024))
    resource.setrlimit(resource.RLIMIT_CPU,(180,180))


class CodexAdapter:
    mode = 'live-codex'
    def __init__(self,settings):
        self.settings=settings
        self.cached=None
        self.checked=0

    def status(self):
        configured = bool(self.settings.agent_execution_enabled and self.settings.agent_auth_token
            and self.settings.agent_codex_api_key.get_secret_value() and self.settings.agent_codex_model)
        if not configured:
            return {'available':False,'mode':self.mode,'sdk':'@openai/codex-sdk 0.169.0',
                'message':'Live execution disabled or missing dedicated agent token, API key or model. No AI output is substituted.'}
        if self.cached is None or (self.cached.get("available") and time.monotonic()-self.checked>30):
            try:
                result=subprocess.run([shutil.which('node') or 'node',str(AGENT_DIR/'adapter.mjs'),'--status'],
                    env={'PATH':os.environ.get('PATH',os.defpath)},capture_output=True,text=True,timeout=10)
                runtime=json.loads(result.stdout) if result.returncode==0 else {'available':False}
                self.cached=runtime
            except Exception: self.cached={'available':False}
            self.checked=time.monotonic()
        return {**self.cached,'mode':self.mode,'message':'Ready for explicitly authorized paid investigation.' if self.cached.get('available') else 'Required native SDK/sandbox containment is unavailable. Live execution is blocked.'}

    async def run(self,bundle):
        if not self.status()['available']: raise AgentUnavailable('Codex not configured or contained')
        with tempfile.TemporaryDirectory(prefix='opsguard-agent-') as directory:
            env={'PATH':os.environ.get('PATH',os.defpath), 'TMPDIR':directory,
                'OPSGUARD_AGENT_RUNTIME':directory,'OPSGUARD_AGENT_AUTHORIZED':'true',
                'AGENT_CODEX_API_KEY':self.settings.agent_codex_api_key.get_secret_value(),
                'AGENT_CODEX_MODEL':self.settings.agent_codex_model}
            process=await asyncio.create_subprocess_exec(shutil.which('node') or 'node','--max-old-space-size=256',str(AGENT_DIR/'adapter.mjs'),
                cwd=AGENT_DIR, env=env,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,start_new_session=True,preexec_fn=resource_bounds)
            try:
                payload=json.dumps({'bundle':bundle,'schema':AgentAnalysis.model_json_schema(),'timeout_ms':self.settings.agent_timeout_seconds*1000}).encode()
                if len(payload)>180000: raise ValueError('Agent evidence exceeds input bound')
                process.stdin.write(payload);await process.stdin.drain();process.stdin.close()
                output=bytearray()
                while True:
                    chunk=await process.stdout.read(4096)
                    if not chunk: break
                    output.extend(chunk)
                    if len(output)>131072: raise ValueError('Agent response exceeds output bound')
                await process.wait()
                if process.returncode: raise AgentUnavailable('SDK execution failed; no generated report was accepted')
                return json.loads(output)
            finally:
                if process.returncode is None:
                    try: os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                    await process.wait()
