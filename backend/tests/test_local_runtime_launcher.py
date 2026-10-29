"""No-network checks for the portable local launcher and relocated capacity gate."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

from scripts import relay_capacity


def test_launcher_reads_portable_template_from_another_working_directory(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(backend / "scripts/serve_local.py"), "--env-file",
         str(backend / ".env.example"), "--check"],
        cwd=tmp_path, check=True, capture_output=True, text=True,
    )
    configuration = json.loads(result.stdout)
    assert configuration["llm_timeout_seconds"] == 300
    assert configuration["credibility_workers"] == 1
    assert configuration["relay_capacity"] == 1
    assert configuration["relay_cooldown_seconds"] == 150
    assert configuration["anthropic_chat_transport"] == configuration["gemini_chat_transport"] == "sse"
    assert configuration["gemini_model"] == "gemini-3.1-flash-lite"
    assert configuration["gemini_reasoning_effort"] == "minimal"
    assert configuration["gemini_thinking_headroom"] == 0
    assert not any("key" in name or "token" in name for name in configuration)
    assert not list(tmp_path.iterdir())


def test_relay_capacity_remains_held_until_stream_body_finishes(tmp_path):
    gate = relay_capacity.install(state_dir=tmp_path, poll_seconds=0.005)
    first_entered, second_entered, release_body = threading.Event(), threading.Event(), threading.Event()
    errors = []
    calls = []

    class HeldBody(httpx.SyncByteStream):
        def __iter__(self):
            assert release_body.wait(3)
            yield b'{"ok":true}'

    def handler(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            first_entered.set()
            return httpx.Response(200, stream=HeldBody())
        second_entered.set()
        return httpx.Response(200, json={"ok": True})

    def worker():
        try:
            with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                with client.stream("POST", "https://www.yunzhuhub.com/v1/chat/completions",
                                   json={"model": "offline-only"}) as response:
                    assert json.loads(response.read()) == {"ok": True}
        except BaseException as error:
            errors.append(error)

    first, second = threading.Thread(target=worker), threading.Thread(target=worker)
    try:
        first.start()
        assert first_entered.wait(2)
        second.start()
        assert not second_entered.wait(0.15)
        release_body.set()
        first.join(3)
        second.join(3)
        assert not first.is_alive() and not second.is_alive()
        assert not errors
        assert second_entered.is_set()
        finished = [json.loads(line) for line in gate.audit_path.read_text().splitlines()
                    if json.loads(line)["event"] == "request_finished"]
        assert len(finished) == 2 and all(row["body_complete"] for row in finished)
        assert not gate.cooldown_path.exists()
    finally:
        release_body.set()
        first.join(3)
        if second.ident is not None:
            second.join(3)
        gate.restore()


def test_relay_timeout_records_150_second_cooldown_and_other_hosts_pass_through(tmp_path):
    gate = relay_capacity.install(state_dir=tmp_path, cooldown_seconds=150)

    def handler(request):
        if request.url.host == "www.yunzhuhub.com":
            raise httpx.ReadTimeout("offline timeout", request=request)
        return httpx.Response(200, json={"ok": True})

    try:
        before = time.time()
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(httpx.ReadTimeout):
                client.post("https://www.yunzhuhub.com/v1/chat/completions", json={"model": "offline-only"})
            cooldown = json.loads(gate.cooldown_path.read_text())
            assert cooldown["not_before"] >= before + 150
            assert client.post("https://api.openai.com/v1/responses", json={}).status_code == 200
        rows = [json.loads(line) for line in gate.audit_path.read_text().splitlines()]
        assert [row["event"] for row in rows] == ["installed", "request_started", "request_finished"]
        assert rows[-1]["cooldown_reason"] == "timeout"
    finally:
        gate.restore()
