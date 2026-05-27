#!/usr/bin/env bash
# Mint AAP Gateway Bearer token for Microsoft Copilot Studio (gitignored output).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=scripts/workshop-lab-env.sh
source "$ROOT/scripts/workshop-lab-env.sh"

OUT="$ROOT/copilotstudio/copilot-studio-token.txt"
python3 <<PY
import base64, json, os, ssl
from http.client import HTTPSConnection
from urllib.parse import urlparse

base = os.environ.get("AAP_BASE_URL", "").rstrip("/")
user = os.environ.get("AAP_USER", "admin")
password = os.environ["AAP_PASSWORD"]
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
payload = json.dumps({
    "description": "microsoft-copilot-studio",
    "application": "",
    "scope": "write",
}).encode()
auth = base64.b64encode(f"{user}:{password}".encode()).decode()
p = urlparse(base + "/api/gateway/v1/tokens/")
conn = HTTPSConnection(p.hostname, p.port or 443, context=ctx, timeout=60)
conn.request("POST", p.path, body=payload, headers={
    "Content-Type": "application/json",
    "Authorization": f"Basic {auth}",
})
resp = conn.getresponse()
body = resp.read().decode()
conn.close()
if resp.status not in (200, 201):
    raise SystemExit(f"HTTP {resp.status}: {body[:400]}")
token = json.loads(body)["token"]
path = "$OUT"
with open(path, "w") as f:
    f.write(
        "# Gitignored — paste into Power Apps custom connector API Key\\n\\n"
        f"Bearer {token}\\n"
    )
import os
os.chmod(path, 0o600)
print(f"Wrote {path}")
print(f"Value for Copilot Studio: Bearer {token[:8]}...{token[-4:]}")
PY

echo "See copilotstudio/README.md for connector setup."
