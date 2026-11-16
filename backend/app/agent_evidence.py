"""Application-controlled collectors. No model-selected commands or host-wide Git discovery."""
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import time
from app.incidents import redact

SOURCE_SUFFIXES = {'.js','.mjs','.cjs','.ts'}


def sanitize(text):
    text = re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', lambda match:'[PRIVATE KEY REDACTED]'+'\n'*match.group(0).count('\n'), text, flags=re.S)
    text = re.sub(r'\bsk-[A-Za-z0-9_-]{16,}', '[API KEY REDACTED]', text)
    return redact(text)


def bounded_command(args, cwd, timeout=4, limit=65536):
    env = {'PATH':os.defpath, 'HOME':'/nonexistent', 'GIT_CONFIG_NOSYSTEM':'1',
           'GIT_CONFIG_GLOBAL':'/dev/null','GIT_TERMINAL_PROMPT':'0','GIT_OPTIONAL_LOCKS':'0', 'LC_ALL':'C'}
    process = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True)
    output = bytearray()
    errors = bytearray()
    deadline = time.monotonic()+timeout
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ, "stdout")
    selector.register(process.stderr, selectors.EVENT_READ, "stderr")
    try:
        while selector.get_map():
            if time.monotonic() > deadline: raise TimeoutError('Read-only command timed out')
            for key, _ in selector.select(.05):
                chunk = os.read(key.fileobj.fileno(), 4096)
                if not chunk: selector.unregister(key.fileobj); continue
                (output if key.data == "stdout" else errors).extend(chunk)
                if len(output)+len(errors) > limit: raise ValueError('Read-only command output limit exceeded')
        code = process.wait(timeout=max(.1, deadline-time.monotonic()))
        return code, sanitize(output.decode('utf-8',errors='replace'))
    finally:
        selector.close()
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGKILL)
        process.wait()
        process.stdout.close()
        process.stderr.close()


class RepositoryReader:
    def __init__(self, project_root):
        requested = Path(project_root).absolute()
        if requested.is_symlink() or requested.resolve() != requested:
            raise ValueError('Repository root must not traverse symbolic links')
        self.root = requested.resolve()
        if not (self.root/'services').is_dir(): raise ValueError('Approved repository lacks services directory')

    def allowed(self, service):
        if service not in ('user-service','order-service','payment-service'):
            raise ValueError('Unknown service')
        return [Path('services/shared'),Path('services/fixtures'),Path('services')/service]

    def safe_file(self, relative, service):
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or any(part.startswith('.') or part in ('node_modules','__pycache__') for part in path.parts):
            raise ValueError('Unauthorized source path')
        if path.suffix not in SOURCE_SUFFIXES or not any(path.is_relative_to(root) for root in self.allowed(service)):
            raise ValueError('Source file is not allowlisted')
        current = self.root
        for part in path.parts:
            current = current/part
            if current.is_symlink(): raise ValueError('Symbolic links are not allowed')
        resolved = current.resolve(strict=True)
        if not resolved.is_relative_to(self.root) or not resolved.is_file() or resolved.stat().st_size > 65536:
            raise ValueError('Source file outside bounds')
        return resolved

    def read(self, relative, service):
        self.safe_file(relative,service)
        # Walk from a directory descriptor so intermediate symlink swaps cannot escape.
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptor = None
        try:
            parts = Path(relative).parts
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = child
            descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or opened.st_size > 65536:
                raise ValueError('Source descriptor is not a bounded regular file')
            raw = os.read(descriptor,65537)
            if len(raw)>65536: raise ValueError('Source size limit')
            return sanitize(raw.decode('utf-8')), hashlib.sha256(raw).hexdigest()
        finally:
            if descriptor is not None: os.close(descriptor)
            os.close(directory)

    def collect(self, service, incident):
        paths = []
        for root in self.allowed(service):
            directory = self.root/root
            if not directory.exists() or directory.is_symlink(): continue
            for path in sorted(directory.rglob('*')):
                if path.is_file() and path.suffix in SOURCE_SUFFIXES:
                    try:
                        self.safe_file(path.relative_to(self.root), service)
                        paths.append(path.relative_to(self.root).as_posix())
                    except (ValueError,OSError): continue
                if len(paths)>=20: break
        results = []
        for relative in paths[:20]:
            text,digest = self.read(relative,service)
            lines = text.splitlines()
            centers = [1]
            for index,line in enumerate(lines,1):
                if (incident['error_type'] in line or incident['error_message'] in line) and len(centers)<5:
                    centers.append(index)
            for name, line in re.findall(r'([A-Za-z0-9_.-]+\.(?:js|ts|mjs)):(\d+)',incident.get('stack_trace') or ''):
                if Path(relative).name==name and 1<=int(line)<=len(lines): centers.append(int(line))
            seen = set()
            for center in centers[:7]:
                start,end = max(1,center-12),min(len(lines),center+18)
                if (start,end) in seen: continue
                seen.add((start,end))
                results.append({'kind':'source','path':relative,'start_line':start,'end_line':end,
                    'content':'\n'.join(lines[start-1:end]),'sha256':digest})
                if len(results)>=30: return results
        return results

    def git(self, operation, paths, commit=None, line_range=None):
        if operation not in ('log','show','diff','blame','status'):
            raise ValueError('Git operation is not allowlisted')
        # Reject inherited parent repositories, gitdir redirects, hooks/config includes and alternates.
        gitdir = self.root/'.git'
        if not gitdir.is_dir() or gitdir.is_symlink(): raise ValueError('No project-scoped Git repository. Parent repository discovery is prohibited.')
        if any(path.is_symlink() for path in gitdir.rglob('*')): raise ValueError('Git metadata symlinks prohibited')
        config = (gitdir/'config').read_text() if (gitdir/'config').exists() else ''
        if len(config)>16384 or re.search(r'\[include|worktree\s*=|fsmonitor\s*=',config,re.I) or (gitdir/'commondir').exists() or (gitdir/'objects/info/alternates').exists():
            raise ValueError('Unsupported Git indirection/configuration')
        if not paths: raise ValueError('Git operations require explicit approved source paths')
        for path in paths:
            if Path(path).is_absolute() or '..' in Path(path).parts or not str(path).startswith('services/') or Path(path).suffix not in SOURCE_SUFFIXES or any(part.startswith('.') for part in Path(path).parts):
                raise ValueError('Unscoped Git path')
            if not any(Path(path).is_relative_to(root) for service in ('user-service','order-service','payment-service') for root in self.allowed(service)):
                raise ValueError('Git path outside allowlisted service roots')
            current=self.root
            for part in Path(path).parts:
                current=current/part
                if current.is_symlink(): raise ValueError('Git source symlinks prohibited')
            if not current.resolve().is_relative_to(self.root): raise ValueError('Git path escaped')
        prefix = ['git','--no-pager','-c','core.hooksPath=/dev/null','-c','core.fsmonitor=false','-c','diff.external=','-c','log.showSignature=false','-c','core.pager=cat']
        code, top = bounded_command(prefix+['rev-parse','--show-toplevel'],self.root)
        if code or Path(top.strip()).resolve()!=self.root: raise ValueError('Unexpected Git root')
        if commit is not None and not re.fullmatch(r'[0-9a-f]{40}',commit): raise ValueError('Invalid commit hash')
        if operation=='status': args=['status','--porcelain=v1','--untracked-files=no']
        elif operation=='log': args=['log','-n','8','--format=%H%x1f%aI%x1f%an%x1f%s']
        elif operation=='show': args=['show','--no-ext-diff','--no-textconv','--format=fuller','--stat',commit]
        elif operation=='diff': args=['diff','--no-ext-diff','--no-textconv','--unified=3',commit+'^',commit]
        else:
            start,end = line_range
            if not 1<=start<=end<=start+40: raise ValueError('Invalid blame range')
            args=['blame','--line-porcelain','-L',f'{start},{end}']
        return bounded_command(prefix+args+['--',*paths],self.root)

    def collect_git(self, sources):
        paths = sorted({source['path'] for source in sources})[:12]
        evidence, limitations = [], []
        try:
            code,status = self.git('status',paths)
            if code: raise ValueError('Git status unavailable')
            evidence.append({'kind':'git','operation':'status','commit_sha':None,'content':status or 'No tracked changes within inspected paths.'})
            code,history = self.git('log',paths)
            if code or not history.strip(): raise ValueError('No useful commits for inspected source files')
            commits=[]
            for line in history.splitlines():
                parts=line.split('\x1f',3)
                if len(parts)==4 and re.fullmatch(r'[0-9a-f]{40}',parts[0]):
                    commits.append(parts[0])
                    evidence.append({'kind':'git','operation':'log','commit_sha':parts[0], 'date':parts[1],'author':parts[2], 'content':parts[3]})
            for sha in commits[:3]:
                for operation in ('show','diff'):
                    code,output = self.git(operation,paths,commit=sha)
                    if not code: evidence.append({'kind':'git','operation':operation,'commit_sha':sha,'content':output})
                    else: limitations.append(f'Git {operation} unavailable for one scoped commit (root commits may lack a parent).')
            for source in sources[:2]:
                code,output=self.git('blame',[source['path']],line_range=(source['start_line'],source['end_line']))
                if not code: evidence.append({'kind':'git','operation':'blame','commit_sha':None,'path':source['path'],'content':output})
        except (ValueError,OSError,TimeoutError):
            limitations.append('Project-scoped Git evidence unavailable or rejected. The inherited parent/home repository was not inspected.')
        return evidence,limitations
