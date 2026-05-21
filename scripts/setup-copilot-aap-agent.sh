#!/usr/bin/env bash
# Install GitHub Copilot SDK agent deps and write gitignored .env for AAP MCP.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pip install -q -r copilot-aap-agent/requirements.txt

# shellcheck source=scripts/workshop-lab-env.sh
source "$ROOT/scripts/workshop-lab-env.sh"

ansible-playbook playbooks/create-gateway-token.yml -e @group_vars/all.yml >/dev/null

TOKEN="$(python3 -c "import sys; sys.path.insert(0,'scripts'); from aap_mcp_client import gateway_token; print(gateway_token())")"
ENV_FILE="$ROOT/copilot-aap-agent/.env"
cat >"$ENV_FILE" <<EOF
AAP_GATEWAY_TOKEN=${TOKEN}
AAP_MCP_URL=https://aap-mcp-aap.apps.cluster-wg2cd-2.dynamic2.redhatworkshops.io/job_management/mcp
COPILOT_MODEL=gpt-4.1
# Optional Azure BYOM (uncomment after setting deployment):
# AZURE_OPENAI_ENDPOINT=https://foundry-wg2cd-1.services.ai.azure.com/api/projects/foundry-wg2cd-1-project/openai/v1
# AZURE_MODEL_NAME=o4-mini
EOF
chmod 600 "$ENV_FILE"

echo "Installed github-copilot-sdk and wrote $ENV_FILE"
echo "Test: python3 copilot-aap-agent/test_mcp_session.py"
