"""Thin, provider-specific REST calls to OpenAI/Anthropic — the only place in this
backend that makes an outbound HTTP call to a third-party API at request time (every
other `requests` usage in this codebase is text emitted into a *generated* Playwright
script, never executed by the server itself). Uses `requests` (already a hard
dependency) rather than adding either provider's SDK, since this is a single call/
response exchange with no need for the SDKs' extra surface (streaming, retries,
typed clients, etc).
"""

import requests

# One place to bump the model used for reconstruction — trivial to change per provider.
PROVIDER_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-opus-5",
}


class LLMError(Exception):
    """Raised when the provider call itself fails — network error, non-2xx, auth
    failure, refusal, or an unexpected response shape."""


def call_llm(provider: str, api_key: str, system_prompt: str, user_prompt: str, json_schema: dict) -> str:
    """Returns the raw text of the model's reply (expected to be a JSON document,
    possibly still wrapped in markdown fences — the caller is responsible for
    parsing/validating it, see app/services/workflow_reconstructor.py). Raises
    LLMError on any failure reaching or interpreting the provider's response."""
    if provider == "openai":
        return _call_openai(api_key, system_prompt, user_prompt, json_schema)
    if provider == "anthropic":
        return _call_anthropic(api_key, system_prompt, user_prompt, json_schema)
    raise LLMError(f"Unsupported provider {provider!r} — expected 'openai' or 'anthropic'")


def _call_openai(api_key: str, system_prompt: str, user_prompt: str, json_schema: dict) -> str:
    # Chat Completions with basic JSON mode (response_format: json_object) — this is
    # the long-stable "guarantee syntactically valid JSON" feature, not the newer
    # strict-schema constraint (whose exact current shape/API surface we didn't want
    # to lock this plan to without live-verifying it first — see the plan file).
    # The schema itself is instead spelled out in the system prompt, and
    # workflow_reconstructor.py's parsing/repair layer is the real safety net.
    try:
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": PROVIDER_MODELS["openai"],
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
                "response_format": {"type": "json_object"},
            },
            timeout=120,
        )
    except requests.RequestException as exc:
        raise LLMError(f"Couldn't reach OpenAI: {exc}") from exc

    if not resp.ok:
        raise LLMError(f"OpenAI API error {resp.status_code}: {resp.text[:500]}")

    try:
        return resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError(f"Unexpected OpenAI response shape: {resp.text[:500]}") from exc


def _call_anthropic(api_key: str, system_prompt: str, user_prompt: str, json_schema: dict) -> str:
    # Native Structured Outputs (GA) — output_config.format constrains the model to
    # emit JSON matching json_schema at the token level, which eliminates almost the
    # entire "wrapped the answer in markdown" failure class for this path specifically.
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": PROVIDER_MODELS["anthropic"],
                "max_tokens": 8192,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "output_config": {"format": {"type": "json_schema", "schema": json_schema}},
            },
            timeout=120,
        )
    except requests.RequestException as exc:
        raise LLMError(f"Couldn't reach Anthropic: {exc}") from exc

    if not resp.ok:
        raise LLMError(f"Anthropic API error {resp.status_code}: {resp.text[:500]}")

    body = resp.json()
    if body.get("stop_reason") == "refusal":
        raise LLMError("Anthropic declined the request — try again, simplify the script, or use a different provider")

    text_block = next((b.get("text") for b in body.get("content", []) if b.get("type") == "text"), None)
    if text_block is None:
        raise LLMError(f"Unexpected Anthropic response shape: {resp.text[:500]}")
    return text_block
