"""Tests for the DeepSeek provider, the `claude -p` provider and script-stage routing."""

from __future__ import annotations

import os
import stat
import tempfile
import textwrap
import unittest
from dataclasses import replace
from unittest.mock import AsyncMock, patch

os.environ.setdefault("GEMINI_API_KEY", "test_key")

import services.ai.client as client  # noqa: E402
import services.ai.providers as providers  # noqa: E402
from services.ai.providers import ProviderConfig, ProviderName  # noqa: E402


def _cfg(name: ProviderName, key: str = "k", model: str = "m") -> ProviderConfig:
    return ProviderConfig(name=name, api_key=key, base_url=None, model=model, json_model=model)


def _fake_claude(script_body: str) -> str:
    """Write an executable fake `claude` that ignores args and runs script_body."""
    d = tempfile.mkdtemp()
    path = os.path.join(d, "claude")
    with open(path, "w") as fh:
        fh.write("#!/bin/sh\n" + textwrap.dedent(script_body))
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


class TestProviderOrdering(unittest.TestCase):
    def test_preferred_providers_come_first_without_duplicates(self) -> None:
        registry = {
            ProviderName.DEEPSEEK: _cfg(ProviderName.DEEPSEEK),
            ProviderName.GROQ: _cfg(ProviderName.GROQ),
            ProviderName.CLAUDE_CLI: _cfg(ProviderName.CLAUDE_CLI, key="cli"),
            ProviderName.GEMINI: _cfg(ProviderName.GEMINI, key=""),  # disabled
        }
        order = [ProviderName.DEEPSEEK, ProviderName.GROQ, ProviderName.GEMINI]
        with patch.object(providers, "PROVIDER_REGISTRY", registry), patch.object(providers, "PROVIDER_ORDER", order):
            names = [c.name for c in providers.get_enabled_providers([ProviderName.CLAUDE_CLI, ProviderName.DEEPSEEK])]
            self.assertEqual(names, [ProviderName.CLAUDE_CLI, ProviderName.DEEPSEEK, ProviderName.GROQ])
            # Without a preference the CLI is not used at all.
            names = [c.name for c in providers.get_enabled_providers()]
            self.assertEqual(names, [ProviderName.DEEPSEEK, ProviderName.GROQ])

    def test_claude_cli_requires_opt_in(self) -> None:
        with patch.dict(os.environ, {"CLAUDE_CLI_ENABLED": "false"}):
            self.assertEqual(providers._claude_cli_marker(), "")
        fake = _fake_claude("echo '{}'\n")
        with patch.dict(os.environ, {"CLAUDE_CLI_ENABLED": "true", "CLAUDE_CLI_PATH": fake}):
            self.assertEqual(providers._claude_cli_marker(), "cli")
        with patch.dict(os.environ, {"CLAUDE_CLI_ENABLED": "true", "CLAUDE_CLI_PATH": "/nope/claude"}):
            self.assertEqual(providers._claude_cli_marker(), "")

    def test_deepseek_registered_with_default_model(self) -> None:
        cfg = providers.build_provider_registry()[ProviderName.DEEPSEEK]
        self.assertEqual(cfg.base_url, "https://api.deepseek.com")
        self.assertIn(cfg.model, {os.getenv("DEEPSEEK_MODEL", "deepseek-flash")})


class TestClaudeCliCaller(unittest.IsolatedAsyncioTestCase):
    async def test_success_parses_result_and_usage_and_hides_api_key(self) -> None:
        # The fake echoes whether ANTHROPIC_API_KEY leaked and the prompt it read on stdin.
        fake = _fake_claude(
            """
            PROMPT=$(cat)
            if [ -n "$ANTHROPIC_API_KEY" ]; then LEAK=yes; else LEAK=no; fi
            printf '{"type":"result","is_error":false,"result":"leak=%s prompt=%s","usage":{"input_tokens":10,"cache_read_input_tokens":5,"output_tokens":7}}' "$LEAK" "$PROMPT"
            """
        )
        with patch.dict(os.environ, {"CLAUDE_CLI_PATH": fake, "ANTHROPIC_API_KEY": "sk-should-not-leak"}):
            text, meta = await client._call_claude_cli(
                _cfg(ProviderName.CLAUDE_CLI, model="sonnet"),
                prompt="hello world", system="sys", temperature=0.5, max_tokens=100, json_mode=False,
            )
        self.assertEqual(text, "leak=no prompt=hello world")
        self.assertEqual(meta["prompt_tokens"], 15)
        self.assertEqual(meta["output_tokens"], 7)
        self.assertEqual(meta["finish_reason"], "stop")

    async def test_usage_limit_error_is_retryable(self) -> None:
        fake = _fake_claude(
            """
            cat >/dev/null
            echo '{"type":"result","is_error":true,"result":"Claude AI usage limit reached"}'
            exit 1
            """
        )
        with patch.dict(os.environ, {"CLAUDE_CLI_PATH": fake}):
            with self.assertRaises(client.AIResponseError) as ctx:
                await client._call_claude_cli(
                    _cfg(ProviderName.CLAUDE_CLI), prompt="p", system="", temperature=0.5,
                    max_tokens=10, json_mode=False,
                )
        self.assertTrue(client._is_retryable(ctx.exception))


class TestFailover(unittest.IsolatedAsyncioTestCase):
    async def asyncTearDown(self) -> None:
        client._provider_cooldown_until.clear()

    async def test_script_stage_falls_back_from_claude_cli_to_deepseek_and_cools_down(self) -> None:
        cli, deepseek = _cfg(ProviderName.CLAUDE_CLI, key="cli"), _cfg(ProviderName.DEEPSEEK)
        calls: list[ProviderName] = []

        async def fake_call(cfg, **_kw):
            calls.append(cfg.name)
            if cfg.name == ProviderName.CLAUDE_CLI:
                raise client.AIResponseError("claude_cli provider unavailable: usage limit reached")
            return "narration text", {"finish_reason": "stop", "output_tokens": 3}

        with patch.object(client, "get_enabled_providers", lambda preferred=None: [cli, deepseek] if preferred else [deepseek]), \
             patch.object(client, "_call_provider", side_effect=fake_call), \
             patch.object(client, "SCRIPT_PROVIDER_ORDER", [ProviderName.CLAUDE_CLI]):
            with client.script_writing_providers():
                text, meta = await client.generate_text_with_metadata("p")
                self.assertEqual((text, meta["provider"]), ("narration text", "deepseek"))
                # Second call skips the CLI while it cools down.
                await client.generate_text_with_metadata("p")

        self.assertEqual(calls, [ProviderName.CLAUDE_CLI, ProviderName.DEEPSEEK, ProviderName.DEEPSEEK])

    async def test_insufficient_balance_falls_through_instead_of_aborting(self) -> None:
        deepseek, groq = _cfg(ProviderName.DEEPSEEK), _cfg(ProviderName.GROQ)

        async def fake_call(cfg, **_kw):
            if cfg.name == ProviderName.DEEPSEEK:
                raise RuntimeError("Error code: 402 - Insufficient Balance")
            return "ok", {"finish_reason": "stop"}

        with patch.object(client, "get_enabled_providers", lambda preferred=None: [deepseek, groq]), \
             patch.object(client, "_call_provider", side_effect=fake_call), \
             patch.object(client.asyncio, "sleep", AsyncMock()):
            text, meta = await client.generate_text_with_metadata("p")
        self.assertEqual(meta["provider"], "groq")


class TestDeepSeekRequest(unittest.IsolatedAsyncioTestCase):
    async def test_thinking_disabled_by_default(self) -> None:
        captured: dict = {}

        class FakeCompletions:
            async def create(self, **kwargs):
                captured.update(kwargs)
                msg = type("M", (), {"content": "hi"})
                choice = type("C", (), {"message": msg, "finish_reason": "stop"})
                return type("R", (), {"choices": [choice], "usage": None})

        class FakeClient:
            def __init__(self, **_kw):
                self.chat = type("Chat", (), {"completions": FakeCompletions()})

        cfg = replace(providers.build_provider_registry()[ProviderName.DEEPSEEK], api_key="k")
        with patch("openai.AsyncOpenAI", FakeClient), patch.dict(os.environ, {"DEEPSEEK_THINKING": "disabled"}):
            text, _ = await client._call_groq(cfg, prompt="p", system="s", temperature=0.5, max_tokens=50, json_mode=True)
        self.assertEqual(text, "hi")
        self.assertEqual(captured["extra_body"], {"thinking": {"type": "disabled"}})
        self.assertEqual(captured["response_format"], {"type": "json_object"})


if __name__ == "__main__":
    unittest.main()
