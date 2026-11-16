"""Delete only the SQLite files of a marked disposable demo, after confirmation."""
import argparse
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser()
parser.add_argument("name", help="Exact phase3-<12 hex digits> name printed by prepare-incident-demo.py")
args = parser.parse_args()
if not re.fullmatch(r"phase3-[a-f0-9]{12}", args.name):
    parser.error("Invalid disposable demo name")
root = Path(__file__).resolve().parents[1] / "backend/.demo"
folder = root / args.name
if root.is_symlink() or folder.is_symlink() or folder.resolve().parent != root.resolve():
    parser.error("Unsafe demo directory")
marker = folder / ".opsguard-disposable"
if marker.is_symlink() or not marker.is_file() or json.loads(marker.read_text()) != {"disposable": True, "name": args.name}:
    parser.error("Missing or invalid disposable marker")
files = [folder / ("incidents.db" + suffix) for suffix in ("", "-wal", "-shm", "-journal")]
if any(file.is_symlink() for file in files):
    parser.error("Refusing symbolic links")
print("Stop the demo FastAPI process first. This clears only the marked demo's SQLite files.")
expected = "DELETE " + args.name
if input("Type " + expected + ": ") != expected:
    raise SystemExit("Cancelled; no data changed")
for file in files:
    if file.is_file(): file.unlink()
print("Disposable incident database cleared. Environment configuration retained.")
