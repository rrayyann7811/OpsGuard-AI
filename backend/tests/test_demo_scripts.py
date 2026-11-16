import json
from pathlib import Path
import shutil
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[2] / "scripts"


def test_cleanup_requires_confirmation_and_preserves_unrelated_data(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(SOURCE / "clear-incident-demo.py", scripts)
    name = "phase3-abcdef123456"
    folder = tmp_path / "backend/.demo" / name
    folder.mkdir(parents=True)
    (folder / ".opsguard-disposable").write_text(json.dumps({"disposable":True,"name":name}))
    database = folder / "incidents.db"
    database.write_text("disposable data")
    unrelated = tmp_path / "backend/opsguard.db"
    unrelated.write_text("real data")
    (folder / "environment.sh").write_text("private config")
    command = [sys.executable, str(scripts / "clear-incident-demo.py"), name]
    result = subprocess.run(command, input="no\n", text=True, capture_output=True)
    assert result.returncode != 0 and database.exists()
    result = subprocess.run(command, input="DELETE " + name + "\n", text=True, capture_output=True)
    assert result.returncode == 0 and not database.exists()
    assert unrelated.read_text() == "real data"
    assert (folder / "environment.sh").exists()


def test_cleanup_rejects_unscoped_paths_and_symlinks(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(SOURCE / "clear-incident-demo.py", scripts)
    command = [sys.executable, str(scripts / "clear-incident-demo.py")]
    assert subprocess.run(command + ["../opsguard.db"], capture_output=True).returncode != 0
    folder = tmp_path / "backend/.demo"
    folder.mkdir(parents=True)
    (folder / "phase3-abcdef123456").symlink_to(tmp_path, target_is_directory=True)
    assert subprocess.run(command + ["phase3-abcdef123456"], capture_output=True).returncode != 0


def test_preparation_isolates_data_and_disables_execution(tmp_path):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    shutil.copy(SOURCE / 'prepare-incident-demo.py', scripts)
    result = subprocess.run([sys.executable, str(scripts / 'prepare-incident-demo.py')],
                            text=True, capture_output=True, check=True)
    folder, = (tmp_path / 'backend/.demo').iterdir()
    import shlex
    values = dict(shlex.split(line.removeprefix('export '))[0].split('=', 1)
                  for line in (folder / 'environment.sh').read_text().splitlines())
    assert values['INCIDENT_WEBHOOK_TOKEN'] not in result.stdout
    assert values['DATABASE_URL'] == 'sqlite:///' + str(folder / 'incidents.db')
    assert values['QDRANT_PATH'] == str(folder / 'qdrant')
    assert values['QDRANT_URL'] == ''
    for key in ('AGENT_EXECUTION_ENABLED', 'AGENT_MANAGED_ENABLED',
                'AGENT_MANAGED_HTTP_ENABLED', 'ENABLE_INCIDENT_MANAGEMENT'):
        assert values[key] == 'false'
    assert (folder / 'environment.sh').stat().st_mode & 0o777 == 0o600
    assert not (folder / 'incidents.db').exists()
