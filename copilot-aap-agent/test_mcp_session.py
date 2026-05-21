#!/usr/bin/env python3
"""Verify Copilot SDK session wires AAP MCP; optional chat if model auth works."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from aap_mcp_client import McpClient, gateway_token  # noqa: E402

MCP_URL = os.environ.get(
    "AAP_MCP_URL",
    "https://aap-mcp-aap.apps.cluster-wg2cd-2.dynamic2.redhatworkshops.io/job_management/mcp",
)


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _probe_mcp_direct(token: str) -> tuple[str, int, list[str]]:
    client = McpClient(MCP_URL, token=token)
    try:
        info = client.connect()
        tools = client.list_tools()
        names = [t.get("name", "") for t in tools if t.get("name")]
        return info.get("name", "?"), len(names), names
    finally:
        client.close()


async def _probe_copilot_session(token: str) -> str:
    bundled = Path(__import__("copilot").__file__).resolve().parent / "bin" / "copilot"
    if bundled.is_file():
        os.environ["COPILOT_CLI_PATH"] = str(bundled)

    from copilot import CopilotClient
    from copilot.session import PermissionHandler

    client = CopilotClient()
    await client.start()
    try:
        kwargs: dict = {
            "on_permission_request": PermissionHandler.approve_all,
            "mcp_servers": {
                "aap-rhpds": {
                    "type": "http",
                    "url": MCP_URL,
                    "headers": {
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json, text/event-stream",
                    },
                    "tools": ["*"],
                    "timeout": 120000,
                }
            },
        }
        if os.environ.get("AZURE_OPENAI_ENDPOINT"):
            import yaml
            from azure.identity import ClientSecretCredential

            gv = yaml.safe_load((REPO_ROOT / "group_vars/all.yml").read_text())
            cred = ClientSecretCredential(
                tenant_id=gv.get("azure_tenant", "RedHat.com"),
                client_id=gv["azure_client_id"],
                client_secret=gv["azure_client_secret"],
            )
            scope_token = cred.get_token("https://ai.azure.com/.default").token
            kwargs["model"] = os.environ.get("AZURE_MODEL_NAME", "o4-mini")
            kwargs["provider"] = {
                "type": "openai",
                "base_url": os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/"),
                "bearer_token": scope_token,
                "wire_api": "completions",
            }
        else:
            kwargs["model"] = os.environ.get("COPILOT_MODEL", "gpt-4.1")

        session = await client.create_session(**kwargs)
        sid = session.session_id
        await session.disconnect()
        return sid
    finally:
        await client.stop()


async def main() -> int:
    _load_dotenv()
    token = os.environ.get("AAP_GATEWAY_TOKEN", "").strip() or gateway_token()

    print("=== 1) Direct MCP (same URL as Copilot agent) ===")
    name, count, names = _probe_mcp_direct(token)
    print(f"Server: {name} | tools on {MCP_URL}: {count}")
    if "job_templates_list" in names:
        print("  OK: job_templates_list present")
    else:
        print("  WARN: job_templates_list missing")

    print("\n=== 2) Copilot SDK session + MCP config ===")
    try:
        sid = await _probe_copilot_session(token)
        print(f"  OK: session created with aap-rhpds MCP ({sid})")
    except Exception as exc:
        print(f"  FAIL: {exc}")
        return 1

    if os.environ.get("SKIP_COPILOT_CHAT", "").lower() in {"1", "true", "yes"}:
        print("\n(SKIP_COPILOT_CHAT set — skipping model chat test)")
        return 0

    print("\n=== 3) Copilot chat + MCP tool use (needs GitHub Copilot or Azure BYOM) ===")
    bundled = Path(__import__("copilot").__file__).resolve().parent / "bin" / "copilot"
    if bundled.is_file():
        os.environ["COPILOT_CLI_PATH"] = str(bundled)
    from copilot import CopilotClient
    from copilot.session import PermissionHandler

    client = CopilotClient()
    await client.start()
    try:
        kwargs: dict = {
            "on_permission_request": PermissionHandler.approve_all,
            "mcp_servers": {
                "aap-rhpds": {
                    "type": "http",
                    "url": MCP_URL,
                    "headers": {
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json, text/event-stream",
                    },
                    "tools": ["*"],
                    "timeout": 120000,
                }
            },
            "model": os.environ.get("COPILOT_MODEL", "gpt-4.1"),
        }
        session = await client.create_session(**kwargs)
        result = await session.send_and_wait(
            "Use AAP MCP only. List job template IDs and names."
        )
        text = result.data.content if result and result.data else ""
        print(text[:2000] if text else "(empty — check Copilot subscription / enterprise policy)")
        await session.disconnect()
        return 0 if text else 2
    except Exception as exc:
        print(f"  Chat blocked: {exc}")
        print(
            "  MCP is wired (steps 1–2 passed). Enable GitHub Copilot Enterprise "
            "or set AZURE_OPENAI_ENDPOINT + AZURE_MODEL_NAME in copilot-aap-agent/.env"
        )
        return 0
    finally:
        await client.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
