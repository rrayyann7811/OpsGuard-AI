"""Check the same endpoint used by the frontend. Run with Python 3."""
import json
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen

url = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
try:
    request = Request(f"{url}/api/health", headers={"Origin": "http://localhost:3000"})
    with urlopen(request, timeout=5) as response:
        data = json.load(response)
        assert data["status"] == "healthy" and data["database"] == "connected"
        assert response.headers["Access-Control-Allow-Origin"] == "http://localhost:3000"
        print(json.dumps(data, indent=2))
        print("PASS: health response and frontend CORS origin")
except (URLError, AssertionError, KeyError, ValueError) as error:
    print(f"FAIL: {error}", file=sys.stderr)
    sys.exit(1)
