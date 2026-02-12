"""Ad-hoc demo: sanitize/block sensitive input before LLM call.

This uses GovernanceADKMiddleware to run guardrails + DLP before a model call,
then calls Azure OpenAI with the sanitized prompt.
"""

import asyncio
from pathlib import Path
import tempfile
import os
import time
import requests

from agent_governance.integrations import GovernanceADKMiddleware
from agent_governance.exceptions import InputBlockedError

def _load_env(path: Path) -> None:
  if not path.exists():
    return
  for line in path.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or "=" not in line:
      continue
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip().strip("'").strip('"')
    os.environ.setdefault(key, value)


_load_env(Path(__file__).resolve().parent.parent / ".env")

AZURE_OPENAI_ENDPOINT = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
AZURE_OPENAI_TOKEN_URL = os.environ["AZURE_OPENAI_TOKEN_URL"]
AZURE_OPENAI_CLIENT_ID = os.environ.get("AZURE_OPENAI_CLIENT_ID") or os.environ["CLIENT_ID"]
AZURE_OPENAI_CLIENT_SECRET = os.environ.get("AZURE_OPENAI_CLIENT_SECRET") or os.environ["CLIENT_SECRET"]
AZURE_OPENAI_SCOPE = os.environ.get("AZURE_OPENAI_SCOPE", "Mulescope")
AZURE_OPENAI_MODEL = os.environ.get("AZURE_OPENAI_MODEL") or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-06-01")
AZURE_OPENAI_CA_BUNDLE = os.environ.get("AZURE_OPENAI_CA_BUNDLE")
AZURE_OPENAI_SKIP_VERIFY = os.environ.get("AZURE_OPENAI_SKIP_VERIFY", "false").lower() in {"1", "true", "yes"}

_cached_token: dict[str, float] | None = None


def get_access_token() -> str:
  global _cached_token
  now = time.time()
  if _cached_token and _cached_token["expires_at"] - 60 > now:
    return _cached_token["token"]

  data = {
    "grant_type": "client_credentials",
    "client_id": AZURE_OPENAI_CLIENT_ID,
    "client_secret": AZURE_OPENAI_CLIENT_SECRET,
    "scope": AZURE_OPENAI_SCOPE,
  }
  resp = requests.post(
    AZURE_OPENAI_TOKEN_URL,
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    data=data,
    timeout=30,
    verify=False if AZURE_OPENAI_SKIP_VERIFY else (AZURE_OPENAI_CA_BUNDLE or True),
  )
  resp.raise_for_status()
  payload = resp.json()
  token = payload["access_token"]
  expires_in = int(payload.get("expires_in", 3600))
  _cached_token = {"token": token, "expires_at": now + expires_in}
  return token


def complete(prompt: str) -> str:
  token = get_access_token()
  url = (
    f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/"
    f"{requests.utils.quote(AZURE_OPENAI_MODEL)}/chat/completions"
    f"?api-version={AZURE_OPENAI_API_VERSION}"
  )
  body = {
    "model": AZURE_OPENAI_MODEL,
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 1,
  }
  resp = requests.post(
    url,
    headers={
      "Authorization": f"Bearer {token}",
      "Content-Type": "application/json",
    },
    json=body,
    timeout=60,
    verify=False if AZURE_OPENAI_SKIP_VERIFY else (AZURE_OPENAI_CA_BUNDLE or True),
  )
  if not resp.ok:
    try:
      print("Azure error:", resp.status_code, resp.text)
    except Exception:
      pass
    resp.raise_for_status()
  data = resp.json()
  choice = data.get("choices", [{}])[0]
  message = choice.get("message", {}).get("content") or choice.get("text", "")
  return (message or "").strip()


def _write_config(tmp: Path) -> Path:
    cfg = tmp / "governance.yaml"
    cfg.write_text(
        f"""
agent:
  agent_id: "azure-demo-agent"
  agent_name: "Azure Demo Agent"
  agent_type: "adk"
  version: "0.1.1"
  env: "dev"
  gcp_project: "demo-project"

dlp:
  enabled: true
  scan_input: true
  action_on_input_pii: "redact"
  info_types:
    - "EMAIL_ADDRESS"
    - "PHONE_NUMBER"
    - "SSN"
    - "CREDIT_CARD"
    - "PERSON_NAME"
    - "ADDRESS"
"""
    )
    return cfg


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg_path = _write_config(Path(tmpdir))
        governance = GovernanceADKMiddleware.from_config(str(cfg_path))
        agent = governance.agent

        user_input = "Contact me at jane.doe@example.com or +1-415-555-1234, ssn 123-45-6789, credit card 4111 1111 1111 1111"

        try:
            processed_input, ctx, start_time = await governance.before_agent_call(
                agent, user_input, user_id="user-1"
            )
        except InputBlockedError as exc:
            print(f"Guardrails blocked input as expected: {exc}")
            return

        print("Original:", user_input)
        print("Sanitized:", processed_input)

        output = complete(processed_input)
        print("Azure response:", output)
        await governance.after_agent_call(agent, ctx, output, start_time)


if __name__ == "__main__":
    asyncio.run(main())
