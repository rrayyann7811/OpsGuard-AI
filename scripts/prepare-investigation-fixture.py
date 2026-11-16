"""Create ONLY a new temporary synthetic Git fixture; never change project Git history."""
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend/tests'))
from agent_support import git_fixture
folder=Path(tempfile.mkdtemp(prefix='opsguard-synthetic-git-')).resolve()
root,sha=git_fixture(folder,ROOT)
print('Synthetic disposable Git fixture (actual new local commits, not project history):')
print(root)
print('Known faulty fixture commit: '+sha)
print('Set AGENT_PROJECT_ROOT to this path only for a controlled development demonstration.')
