"""HTTP smoke checks; this does not inspect a rendered browser layout."""
import sys
from urllib.error import HTTPError
from urllib.request import urlopen

base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000").rstrip("/")
pages = {"/": "Operations overview", "/incidents": "All incidents", "/services": "Service directory", "/investigations": "Investigation workspace", "/knowledge": "Incident knowledge library", "/analytics": "Incidents by severity", "/settings": "Workspace preferences"}
for path, expected in pages.items():
    with urlopen(base + path, timeout=10) as response:
        html = response.read().decode()
        assert response.status == 200 and expected in html, path
        assert "Demonstration workspace" not in html and "INC-1042" not in html, path
        print(f"PASS: {path}")
try:
    urlopen(base + "/missing-page", timeout=10)
    raise AssertionError("Unknown route should return 404")
except HTTPError as error:
    assert error.code == 404
    print("PASS: unknown route returns 404")
