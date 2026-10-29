"""Candidate transport contracts and resource ownership; every request is mocked."""
from __future__ import annotations

import asyncio
import json
import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.credibility import runtime
from app.credibility.snapshots import capture_snapshot, read_snapshot
from app.llm import chat_sse, interrupt, stream_audit
from app.llm.audit import redact_opaque
from app.llm.compatible import PROFILES, CompatibleChatClient
from app.llm.network import install_network_guard, load_denied_hosts
from app.llm.openai import OpenAIClient
from app.llm.retry import (
    LLMAuthenticationError,
    LLMOutputInvalid,
    LLMQuotaExceeded,
    LLMRateLimited,
    LLMRequestRejected,
    LLMTimeout,
    LLMUnavailable,
)
from app.llm.streaming import StreamingCompatibleChatClient
from app.pipeline.orchestrator import build_llm_client

USAGE = {"prompt_tokens": 15, "completion_tokens": 7, "total_tokens": 22,
         "completion_tokens_details": {"reasoning_tokens": 4}}


def _sink_worker(path, prefix, count):
    sink = stream_audit.jsonl_sink(path)
    for index in range(count):
        sink({"attempt_id": f"{prefix}-{index}", "usage_known": False,
              "input_tokens": None, "output_tokens": None, "prompt": "private-canary",
              "Authorization": "private-canary", "thought_signature": "private-canary",
              "profile": {"provider": "google", "reasoning_effort": "low",
                          "thinking_headroom": 4096, "reasoning_content": "private-canary"}})


def frame(delta=None, finish=None, *, usage=None, choices=True):
    data = {"id": "offline-chat", "model": "gemini-offline", "created": 123,
            "choices": [{"index": 0, "delta": delta or {}, "finish_reason": finish}] if choices else []}
    if usage is not None:
        data["usage"] = usage
    return "data: " + json.dumps(data, ensure_ascii=False) + "\r\n\r\n"


TAIL = frame({}, "stop") + frame(usage=USAGE, choices=False) + "data: [DONE]\r\n\r\n"
GOOD = frame({"role": "assistant", "content": '{"ok":true}'}) + TAIL


class Pieces(httpx.SyncByteStream):
    def __init__(self, body, size=7):
        self.body = body.encode() if isinstance(body, str) else body
        self.size, self.closed = size, False

    def __iter__(self):
        for start in range(0, len(self.body), self.size):
            yield self.body[start:start + self.size]

    def close(self):
        self.closed = True


def response(body=GOOD):
    return httpx.Response(200, headers={"content-type": "text/event-stream; charset=utf-8"}, stream=Pieces(body))


@pytest.fixture
def transport(monkeypatch):
    original = httpx.Client.__init__

    def install(handler):
        def init(instance, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return original(instance, *args, **kwargs)
        monkeypatch.setattr(httpx.Client, "__init__", init)
    return install


def client(**kwargs):
    return StreamingCompatibleChatClient(model_id="model_gemini_v1", profile=PROFILES["google"],
        api_key="offline-not-a-key", base_url="https://relay.example/v1", model="gemini-offline", **kwargs)


def test_settings_default_and_factory_select_only_explicit_gemini(monkeypatch):
    for name in ("GEMINI_CHAT_TRANSPORT", "ANTHROPIC_CHAT_TRANSPORT", "GEMINI_REASONING_EFFORT",
                 "GEMINI_THINKING_HEADROOM", "COMPATIBLE_SSE_AUDIT_PATH"):
        monkeypatch.delenv(name, raising=False)
    assert Settings(_env_file=None).gemini_chat_transport == "json"
    assert Settings(_env_file=None).gemini_reasoning_effort == "medium"
    assert Settings(_env_file=None).gemini_thinking_headroom == 24576
    assert Settings(_env_file=None).gemini_enabled is False
    assert Settings(_env_file=None).anthropic_chat_transport == "json"
    assert Settings(_env_file=None).claude_enabled is False
    assert Settings(_env_file=None).compatible_sse_audit_path == ""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, gemini_chat_transport="automatic")
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_chat_transport", "json")
    assert type(build_llm_client("model_gemini_v1")) is CompatibleChatClient
    before = runtime.request_versions()
    monkeypatch.setattr(settings, "gemini_chat_transport", "sse")
    instance = build_llm_client("model_gemini_v1")
    assert isinstance(instance, StreamingCompatibleChatClient)
    assert instance.profile == PROFILES["google"] and instance.timeout == 300
    assert type(build_llm_client("model_claude_v1")) is CompatibleChatClient
    assert build_llm_client("model_gpt_v1").provider == "openai"
    assert runtime.digest(before) != runtime.digest(runtime.request_versions())
    from app.api.routes_options import list_models
    monkeypatch.setattr(settings, "gemini_api_key", "offline-not-a-key")
    assert not next(item for item in list_models() if item.model_id == "model_gemini_v1").is_available


@pytest.mark.parametrize("field,value", [("gemini_reasoning_effort", "none"), ("anthropic_chat_transport", "auto"),
    ("gemini_thinking_headroom", -1), ("gemini_thinking_headroom", 57345)])
def test_google_override_rejects_unsupported_effort_or_headroom(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


@pytest.mark.parametrize("mode", ["json", "sse"])
def test_google_profile_override_changes_effective_payload_metadata_and_fingerprint_only_for_google(
        transport, monkeypatch, mode):
    sent, attempts = [], []

    def handle(request):
        sent.append(json.loads(request.content))
        return response() if mode == "sse" else httpx.Response(200, json={
            "model": "gemini-offline", "usage": USAGE, "choices": [{"finish_reason": "stop", "message": {
                "role": "assistant", "content": '{"ok":true}'}}]})

    transport(handle)
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_chat_transport", mode)
    original = runtime.request_versions()
    monkeypatch.setattr(settings, "gemini_reasoning_effort", "low")
    monkeypatch.setattr(settings, "gemini_thinking_headroom", 4096)
    instance = build_llm_client("model_gemini_v1")
    if mode == "sse":
        instance.attempt_observer = attempts.append
    instance.complete_json("system", "paper", max_tokens=25000)
    assert sent[0]["reasoning_effort"] == "low" and sent[0]["max_tokens"] == 29096
    assert sent[0]["response_format"] == {"type": "json_object"} and "temperature" not in sent[0]
    assert PROFILES["google"].thinking_headroom == 24576 and PROFILES["google"].reasoning_effort == "medium"
    assert instance.profile_metadata["thinking_headroom"] == 4096
    assert instance.profile_metadata["reasoning_effort"] == "low"
    assert build_llm_client("model_claude_v1").profile is PROFILES["anthropic"]
    assert build_llm_client("model_gpt_v1").reasoning_effort == settings.openai_reasoning_effort
    updated = runtime.request_versions()
    assert updated["gemini_reasoning_effort"] == "low" and updated["gemini_thinking_headroom"] == 4096
    assert runtime.digest(original) != runtime.digest(updated)
    if mode == "sse":
        assert attempts[0]["profile"] == instance.profile_metadata
    exposed = instance.profile_metadata
    exposed["reasoning_effort"] = "high"
    assert instance.profile.reasoning_effort == "low"


@pytest.mark.parametrize("mode", ["json", "sse"])
def test_anthropic_transport_opt_in_preserves_its_original_profile_and_wire_payload(transport, monkeypatch, mode):
    sent, attempts = [], []

    def handle(request):
        sent.append(json.loads(request.content))
        text = '```json\n{"ok":true}\n```'
        return response(frame({"content": text}) + TAIL) if mode == "sse" else httpx.Response(200, json={
            "usage": USAGE, "model": "claude-offline", "choices": [{"finish_reason": "stop", "message": {
                "role": "assistant", "content": text}}]})

    transport(handle)
    settings = get_settings()
    before = runtime.request_versions()
    monkeypatch.setattr(settings, "anthropic_chat_transport", mode)
    monkeypatch.setattr(settings, "gemini_reasoning_effort", "low")
    monkeypatch.setattr(settings, "gemini_thinking_headroom", 4096)
    instance = build_llm_client("model_claude_v1")
    assert instance.profile is PROFILES["anthropic"]
    assert isinstance(instance, StreamingCompatibleChatClient) is (mode == "sse")
    if mode == "sse":
        instance.attempt_observer = attempts.append
    assert instance.complete_json("system", "paper", max_tokens=8000).text == '{"ok":true}'
    assert sent[0]["max_tokens"] == 8000 and sent[0]["temperature"] == 0.2
    assert "reasoning_effort" not in sent[0] and "response_format" not in sent[0]
    assert instance.profile_metadata["thinking"] is False
    if mode == "sse":
        assert sent[0]["stream_options"] == {"include_usage": True}
        assert attempts[0]["profile"]["provider"] == "anthropic"
        assert runtime.digest(before) != runtime.digest(runtime.request_versions())


def test_json_payload_compatibility_and_sse_only_adds_stream_options(transport):
    sent = []

    def handle(request):
        payload = json.loads(request.content)
        sent.append(payload)
        if payload.get("stream"):
            return response()
        return httpx.Response(200, json={"model": "gemini-offline", "usage": USAGE,
            "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": '{"ok":true}'}}]})

    transport(handle)
    ordinary = CompatibleChatClient(model_id="model_gemini_v1", profile=PROFILES["google"],
        api_key="offline", base_url="https://relay.example/v1", model="gemini-offline")
    assert ordinary.complete_json("system", "paper", max_tokens=25000).text == '{"ok":true}'
    result = client().complete_json("system", "paper", max_tokens=25000)
    assert result.text == '{"ok":true}' and result.usage.total_tokens == 22
    assert sent[1] == {**sent[0], "stream": True, "stream_options": {"include_usage": True}}
    assert sent[0]["max_tokens"] == 49576 and sent[0]["reasoning_effort"] == "medium"
    assert sent[0]["response_format"] == {"type": "json_object"} and "temperature" not in sent[0]


@pytest.mark.parametrize("signature_location", [None, "tool", "function", "google"])
def test_two_http_tool_turns_keep_signature_in_memory_and_out_of_observer_and_snapshot(
        transport, signature_location):
    sent, seen, attempts = [], [], []
    canary = "opaque-sse-tool-signature"
    tool = {"index": 0, "id": "call_", "type": "function", "function": {"name": "local_", "arguments": '{"a":'}}
    if signature_location == "tool":
        tool["thought_signature"] = canary
    elif signature_location == "function":
        tool["function"]["thought_signature"] = canary
    elif signature_location == "google":
        tool["extra_content"] = {"google": {"thought_signature": canary}}
    first = frame({"role": "assistant", "tool_calls": [tool], "reasoning_content": canary})
    first += frame({"tool_calls": [{"index": 0, "id": "1", "function": {
        "name": "add", "arguments": '2,"b":3}'}}]})
    first += frame({}, "tool_calls") + frame(usage=USAGE, choices=False) + "data: [DONE]\n\n"

    def handle(request):
        sent.append(json.loads(request.content))
        return response(first if len(sent) == 1 else frame({"content": '{"sum":5}'}) + TAIL)

    transport(handle)
    instance = client(response_observer=seen.append, attempt_observer=attempts.append)
    messages = [{"role": "user", "content": "add"}]
    turn = instance.complete_tools(messages, [{"type": "function", "function": {"name": "local_add"}}])
    assert turn.tool_calls[0].call_id == "call_1" and turn.tool_calls[0].name == "local_add"
    assert json.loads(turn.tool_calls[0].arguments) == {"a": 2, "b": 3}
    original = json.dumps(turn.assistant_message)
    messages += [turn.assistant_message, {"role": "tool", "tool_call_id": "call_1", "content": '{"sum":5}'}]
    saved = capture_snapshot(kind="sse_candidate_model_input", normalized_json=redact_opaque({"messages": messages}))
    assert canary not in json.dumps(read_snapshot(saved).normalized_json)
    assert json.dumps(turn.assistant_message) == original
    assert instance.complete_tools(messages, []).text == '{"sum":5}'
    assert sent[1]["messages"][1] == turn.assistant_message
    assert (canary in json.dumps(sent[1])) is (signature_location is not None)
    assert canary not in json.dumps(seen + attempts)
    assert len(attempts) == 2 and all(item["usage_known"] for item in attempts)
    assert seen[0]["usage"]["completion_tokens_details"]["reasoning_tokens"] == 4


@pytest.mark.parametrize("body,code", [
    (GOOD.replace("data: [DONE]\r\n\r\n", ""), "sse_missing_terminal_frame"),
    (frame({"content": "{}"}) + frame(usage=USAGE, choices=False) + "data: [DONE]\n\n",
     "sse_missing_terminal_frame"),
    (frame({"content": "{}"}) + frame({}, "stop") + "data: [DONE]\n\n", "sse_missing_usage"),
    (GOOD + "data: [DONE]\n\n", "sse_duplicate_done"),
    (GOOD + frame({"content": "extra"}), "sse_data_after_done"),
    (GOOD.replace('"finish_reason": "stop"', '"finish_reason": "length"'), "response_truncated"),
    (GOOD.replace('"finish_reason": "stop"', '"finish_reason": "content_filter"'), "sse_unsupported_finish_reason"),
    (GOOD.replace('"model": "gemini-offline"', '"model": "other"', 1), "sse_changed_identity"),
    (GOOD.replace('"index": 0', '"index": false', 1), "sse_invalid_choices"),
    (GOOD.replace('"completion_tokens": 7', '"completion_tokens": true'), "sse_invalid_usage"),
    (frame({"content": "{}"}) + frame({}, "stop") + frame(
        usage={"input_tokens": 15, "output_tokens": 7}, choices=False) + "data: [DONE]\n\n", "sse_missing_usage"),
    (frame({"content": "{}"}) + frame({}, "stop") + frame(
        usage={"prompt_tokens": "15", "completion_tokens": 7}, choices=False), "sse_invalid_usage"),
    (frame({"content": "{}"}) + frame({}, "stop") + frame(
        usage={"prompt_tokens": -1, "completion_tokens": 7}, choices=False), "sse_invalid_usage"),
    ("data: {bad}\n\n", "sse_invalid_json"),
    ("data: []\n\n", "sse_invalid_chunk"),
    (b"data: \xff\n\n", "sse_invalid_utf8"),
    (GOOD.removesuffix("\r\n\r\n"), "sse_incomplete_event"),
])
def test_incomplete_and_invalid_streams_fail_with_safe_usage_diagnostics(transport, body, code):
    attempts, seen = [], []
    transport(lambda _request: response(body))
    with pytest.raises(LLMOutputInvalid) as caught:
        client(response_observer=seen.append, attempt_observer=attempts.append).complete_json("s", "u")
    assert caught.value.provider_diagnostics["error_code"] == code
    assert len(attempts) == 1 and not attempts[0]["protocol_complete"] and not seen
    if code == "sse_missing_usage":
        assert not attempts[0]["usage_known"] and attempts[0]["input_tokens"] is None
        assert attempts[0]["output_tokens"] is None
    if code == "sse_missing_terminal_frame":
        assert attempts[0]["usage_known"] and attempts[0]["output_tokens"] == 7


def test_utf8_crlf_comments_multiline_and_no_opaque_content(transport):
    body = ': heartbeat\r\n\r\n' + frame({"role": "assistant", "reasoning_content": "private-canary"})
    body += frame({"content": '{"说明":"值"}'}).replace('data: {"id":', 'data: {\r\ndata: "id":', 1) + TAIL
    seen = []
    transport(lambda _request: response(body))
    result = client(response_observer=seen.append).complete_json("s", "u")
    assert result.text == '{"说明":"值"}' and "private-canary" not in json.dumps(seen)


@pytest.mark.parametrize("limit,body,code", [
    ("MAX_STREAM_BYTES", GOOD, "sse_body_too_large"),
    ("MAX_EVENT_BYTES", frame({"content": "x" * 1000}), "sse_event_too_large"),
    ("MAX_OUTPUT_BYTES", frame({"content": "x" * 1000}), "sse_output_too_large"),
    ("MAX_EVENTS", GOOD, "sse_too_many_events"),
])
def test_explicit_stream_event_output_and_event_count_bounds(transport, monkeypatch, limit, body, code):
    monkeypatch.setattr(chat_sse, limit, 1 if limit == "MAX_EVENTS" else 128)
    transport(lambda _request: response(body))
    with pytest.raises(LLMOutputInvalid) as caught:
        client().complete_json("s", "u")
    assert caught.value.provider_diagnostics["error_code"] == code


def test_signature_fragments_are_not_invented_or_concatenated(transport):
    tool = {"index": 0, "id": "tool", "function": {"name": "find", "arguments": "{}"},
            "extra_content": {"google": {"thought_signature": "first-part"}}}
    body = frame({"tool_calls": [tool]}) + frame({"tool_calls": [
        {"index": 0, "extra_content": {"google": {"thought_signature": "different-part"}}}]})
    transport(lambda _request: response(body))
    with pytest.raises(LLMOutputInvalid) as caught:
        client().complete_tools([], [])
    assert caught.value.provider_diagnostics["error_code"] == "sse_conflicting_signature"
    assert "first-part" not in json.dumps(caught.value.provider_diagnostics)


@pytest.mark.parametrize("status,code,error", [
    (401, "invalid_api_key", LLMAuthenticationError), (403, "access_denied", LLMAuthenticationError),
    (402, "insufficient_quota", LLMQuotaExceeded), (429, "insufficient_quota", LLMQuotaExceeded),
    (429, "user_concurrency_limit", LLMRateLimited), (524, "gateway_timeout", LLMUnavailable),
])
def test_http_errors_keep_classification_and_never_expose_provider_body(transport, status, code, error):
    attempts = []
    transport(lambda _request: httpx.Response(status, headers={"content-type": "text/event-stream"}, json={
        "error": {"code": code, "message": "secret-key-canary"}, "usage": USAGE}))
    with pytest.raises(error) as caught:
        client(attempt_observer=attempts.append).complete_json("s", "u")
    assert "secret-key-canary" not in str(caught.value) + json.dumps(attempts)
    assert len(attempts) == 1 and attempts[0]["http_status"] == status
    assert attempts[0]["usage_known"] and attempts[0]["input_tokens"] == 15
    assert caught.value.provider_diagnostics["usage"]["prompt_tokens"] == 15


@pytest.mark.parametrize("status", [401, 403, 402])
@pytest.mark.parametrize("body_failure", ["timeout", "oversized"])
def test_permanent_http_status_does_not_become_retryable_if_error_body_fails(
        transport, monkeypatch, status, body_failure):
    attempts = []

    class FailedBody(Pieces):
        def __iter__(self):
            if body_failure == "timeout":
                yield b"{"
                raise httpx.ReadTimeout("private error-body prose")
            yield b"x" * 128

    if body_failure == "oversized":
        monkeypatch.setattr(stream_audit, "MAX_STREAM_BYTES", 64)
    transport(lambda _request: httpx.Response(status, stream=FailedBody("")))
    expected = LLMAuthenticationError if status in (401, 403) else LLMRequestRejected
    with pytest.raises(expected) as caught:
        client(attempt_observer=attempts.append).complete_json("s", "u")
    assert not caught.value.retryable and len(attempts) == 1
    assert attempts[0]["http_status"] == status and attempts[0]["input_tokens"] is None
    assert "private error-body prose" not in str(caught.value) + json.dumps(attempts)


@pytest.mark.parametrize("status", [200, 401, 403, 402, 524])
def test_identity_encoding_is_requested_and_compressed_responses_are_not_read(transport, status):
    read, attempts = [], []

    class UnreadBody(Pieces):
        def __iter__(self):
            read.append(1)
            raise AssertionError("Compressed body must not be consumed")
            yield b""  # pragma: no cover

    def handle(request):
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(status, headers={"content-type": "text/event-stream", "content-encoding": "gzip"},
                              stream=UnreadBody(""))

    transport(handle)
    expected = (LLMOutputInvalid if status == 200 else LLMAuthenticationError if status in (401, 403)
                else LLMRequestRejected if status == 402 else LLMUnavailable)
    with pytest.raises(expected) as caught:
        client(attempt_observer=attempts.append).complete_json("s", "u")
    assert not read and len(attempts) == 1 and attempts[0]["input_tokens"] is None
    if status == 200:
        assert caught.value.provider_diagnostics["error_code"] == "sse_unsupported_encoding"
    elif status in (401, 403, 402):
        assert not caught.value.retryable


@pytest.mark.parametrize("asynchronous", [False, True])
def test_audit_helpers_do_not_decompress_encoded_error_bodies(asynchronous):
    read, rows = [], []

    class SyncUnread(httpx.SyncByteStream):
        def __iter__(self):
            read.append(1)
            yield b""

    class AsyncUnread(httpx.AsyncByteStream):
        async def __aiter__(self):
            read.append(1)
            yield b""

    reply = httpx.Response(401, headers={"content-encoding": "gzip"},
                           stream=AsyncUnread() if asynchronous else SyncUnread())

    def collect(data, error, complete):
        rows.append((data, error, complete))

    if asynchronous:
        asyncio.run(stream_audit.observe_async(reply, collect))
        asyncio.run(reply.aclose())
    else:
        stream_audit.observe_sync(reply, collect)
        reply.close()
    assert not read and len(rows) == 1 and not rows[0][2]
    assert isinstance(rows[0][1], LLMAuthenticationError)


def test_in_band_quota_and_known_usage_failure_are_recorded_once(transport):
    attempts = []
    body = frame(usage=USAGE, choices=False)
    body += 'data: {"error":{"code":"insufficient_quota","message":"opaque-canary"}}\n\n'
    transport(lambda _request: response(body))
    with pytest.raises(LLMQuotaExceeded) as caught:
        client(attempt_observer=attempts.append).complete_json("s", "u")
    assert not caught.value.retryable
    assert len(attempts) == 1 and attempts[0]["usage_known"] and attempts[0]["output_tokens"] == 7
    assert "opaque-canary" not in json.dumps(attempts)


def test_conflicting_usage_is_unknown_instead_of_summed_or_selected(transport):
    attempts = []
    body = frame({"content": "{}"}) + frame({}, "stop") + frame(usage=USAGE, choices=False)
    body += frame(usage={**USAGE, "completion_tokens": 8}, choices=False)
    transport(lambda _request: response(body))
    with pytest.raises(LLMOutputInvalid) as caught:
        client(attempt_observer=attempts.append).complete_json("s", "u")
    assert caught.value.provider_diagnostics["error_code"] == "sse_conflicting_usage"
    assert len(attempts) == 1 and attempts[0]["input_tokens"] is None


def test_chat_usage_and_sink_do_not_let_zero_responses_aliases_override_chat_totals(transport, tmp_path):
    usage = {**USAGE, "input_tokens": 0, "output_tokens": 0}
    body = frame({"content": "{}"}) + frame({}, "stop") + frame(usage=usage, choices=False) + "data: [DONE]\n\n"
    path = tmp_path / "chat-aliases.jsonl"
    transport(lambda _request: response(body))
    result = client(attempt_observer=stream_audit.jsonl_sink(path)).complete_json("s", "u")
    assert result.usage.prompt_tokens == 15 and result.usage.completion_tokens == 7
    assert result.raw["usage"]["output_tokens"] == 0
    row = json.loads(path.read_text())
    assert row["input_tokens"] == 15 and row["output_tokens"] == 7
    assert row["reported_usage"]["output_tokens"] == 0


def test_observed_claude_usage_shape_accepts_metadata_without_saving_strings_or_bad_alias_totals(
        transport, monkeypatch, tmp_path):
    usage = {"prompt_tokens": 27, "completion_tokens": 1, "total_tokens": 28,
             "usage_semantic": "private-usage-canary", "usage_source": "private-usage-canary",
             "billing_usage": {"source": "private-usage-canary", "semantic": "private-usage-canary",
                               "claude_usage": {"input_tokens": 27, "output_tokens": 1,
                                   "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
                                   "claude_cache_creation_5_m_tokens": 0,
                                   "claude_cache_creation_1_h_tokens": 0}},
             "prompt_tokens_details": {"cached_tokens": 0, "text_tokens": 0},
             "completion_tokens_details": {"reasoning_tokens": 0, "text_tokens": 0},
             "input_tokens": 27, "output_tokens": 0, "input_tokens_details": None}
    body = frame({"content": "{}"}) + frame({}, "stop") + frame(usage=usage, choices=False)
    body += frame(usage={**usage, "usage_source": "different-private-canary", "output_tokens": 5}, choices=False)
    body += "data: [DONE]\n\n"
    path = tmp_path / "claude-usage.jsonl"
    settings = get_settings()
    monkeypatch.setattr(settings, "anthropic_chat_transport", "sse")
    monkeypatch.setattr(settings, "compatible_sse_audit_path", str(path))
    transport(lambda _request: response(body))
    result = build_llm_client("model_claude_v1").complete_json("s", "u")
    assert result.usage.prompt_tokens == 27 and result.usage.completion_tokens == 1
    row = json.loads(path.read_text())
    assert row["input_tokens"] == 27 and row["output_tokens"] == 1
    assert row["reported_usage"]["output_tokens"] == 5
    assert row["reported_usage"]["billing_usage"]["claude_usage"]["output_tokens"] == 1
    assert "private-usage-canary" not in path.read_text() + json.dumps(result.raw)
    assert "different-private-canary" not in path.read_text() + json.dumps(result.raw)


def test_shared_responses_client_uses_responses_totals_despite_conflicting_chat_aliases(transport):
    def handle(request):
        assert request.url.path == "/v1/responses" and not json.loads(request.content).get("stream")
        return httpx.Response(200, json={"model": "gpt-offline", "status": "completed", "output": [{
            "type": "message", "content": [{"type": "output_text", "text": "{}"}]}], "usage": {
                "input_tokens": 11, "output_tokens": 13, "prompt_tokens": 0, "completion_tokens": 0}})

    transport(handle)
    result = OpenAIClient(api_key="offline", base_url="https://relay.example/v1", model="gpt-offline").complete_json(
        "s", "u")
    assert result.usage.prompt_tokens == 11 and result.usage.completion_tokens == 13


def test_interleaved_multiple_tools_and_complete_repeated_signature(transport):
    body = frame({"tool_calls": [
        {"index": 0, "id": "a", "function": {"name": "find", "arguments": '{"q":'},
         "thought_signature": "whole-signature"},
        {"index": 1, "id": "b", "function": {"name": "fetch", "arguments": '{"url":'}}]})
    body += frame({"tool_calls": [
        {"index": 1, "function": {"arguments": '"https://example.org"}'}},
        {"index": 0, "function": {"arguments": '"paper"}'}, "thought_signature": "whole-signature"}]})
    body += frame({}, "tool_calls") + frame(usage=USAGE, choices=False) + "data: [DONE]\n\n"
    transport(lambda _request: response(body))
    turn = client().complete_tools([], [])
    assert [(call.call_id, call.name, json.loads(call.arguments)) for call in turn.tool_calls] == [
        ("a", "find", {"q": "paper"}), ("b", "fetch", {"url": "https://example.org"})]
    assert turn.assistant_message["tool_calls"][0]["thought_signature"] == "whole-signature"


def test_json_instead_of_requested_sse_is_rejected_without_automatic_fallback(transport):
    sent = []

    def handle(request):
        sent.append(request)
        return httpx.Response(200, json={"choices": []})

    transport(handle)
    with pytest.raises(LLMOutputInvalid) as caught:
        client().complete_json("s", "u")
    assert caught.value.provider_diagnostics["error_code"] == "sse_non_sse_response" and len(sent) == 1


def test_dual_subscribers_and_duplicate_close_publish_each_receive_one_independent_copy(transport):
    first, second, replies = [], [], []

    def mutate(data, error, complete):
        first.append((data, error, complete))
        data["usage"]["prompt_tokens"] = 999

    def handle(_request):
        reply = response()
        stream_audit.subscribe(reply, mutate)
        stream_audit.subscribe(reply, lambda d, e, c: second.append((d, e, c)))
        replies.append(reply)
        return reply

    transport(handle)
    assert client().complete_json("s", "u").usage.prompt_tokens == 15
    replies[0].close()
    stream_audit.publish(replies[0])
    stream_audit.publish(replies[0], error=RuntimeError("late-close-canary"))
    late = []
    stream_audit.subscribe(replies[0], lambda d, e, c: late.append((d, e, c)))
    assert len(first) == len(second) == 1
    assert second[0][0]["usage"]["prompt_tokens"] == 15 and second[0][2]
    assert len(late) == 1 and late[0][1] is None and late[0][2]


@pytest.mark.parametrize("quota", [False, True])
def test_late_subscriber_failure_is_safe_and_does_not_mask_provider_rejection(transport, quota):
    replies, attempts = [], []

    def handle(_request):
        reply = httpx.Response(402, json={"error": {"code": "insufficient_quota"}}) if quota else response()
        replies.append(reply)
        return reply

    def failed_observer(_data, _error, _complete):
        attempts.append(1)
        raise ValueError("private callback prose")

    transport(handle)
    if quota:
        with pytest.raises(LLMQuotaExceeded):
            client().complete_json("s", "u")
        stream_audit.subscribe(replies[0], failed_observer)
    else:
        client().complete_json("s", "u")
        with pytest.raises(stream_audit.AuditDeliveryError) as caught:
            stream_audit.subscribe(replies[0], failed_observer)
        assert "private callback prose" not in str(caught.value)
    assert attempts == [1]


@pytest.mark.parametrize("consume", [False, True])
def test_async_consumption_and_unconsumed_close_notify_once_with_unknown_usage(consume):
    rows = []

    class AsyncPieces(httpx.AsyncByteStream):
        async def __aiter__(self):
            for block in Pieces(GOOD):
                yield block

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _request: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=AsyncPieces()))) as instance:
            async with instance.stream("POST", "https://relay.example/v1/chat/completions") as reply:
                await stream_audit.observe_async(reply, lambda d, e, c: rows.append(
                    stream_audit.terminal_metadata(d, e, c, reply.status_code)))
                if consume:
                    await reply.aread()
            await reply.aclose()
    asyncio.run(run())
    assert len(rows) == 1 and rows[0]["protocol_complete"] is consume
    assert rows[0]["usage_known"] is consume
    assert rows[0]["input_tokens"] == (15 if consume else None)


@pytest.mark.parametrize("usage_known", [False, True])
def test_read_timeout_preserves_observed_usage_or_explicit_unknown_and_closes_context(transport, usage_known):
    attempts = []

    class TimeoutBody(Pieces):
        def __iter__(self):
            yield frame({"content": "{"}).encode()
            if usage_known:
                yield frame(usage=USAGE, choices=False).encode()
            raise httpx.ReadTimeout("private transport prose")

    body = TimeoutBody("")
    transport(lambda _request: httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body))
    with pytest.raises(LLMTimeout) as caught:
        client(attempt_observer=attempts.append).complete_json("s", "u")
    assert body.closed and len(attempts) == 1
    assert attempts[0]["input_tokens"] == (15 if usage_known else None)
    assert caught.value.provider_diagnostics["usage"].get("prompt_tokens") == (15 if usage_known else None)
    assert "private transport prose" not in str(caught.value) + json.dumps(attempts)


def test_connection_failure_has_one_unknown_attempt_without_provider_prose(transport):
    attempts = []

    def handle(_request):
        raise httpx.ConnectError("private transport canary")

    transport(handle)
    with pytest.raises(LLMUnavailable) as caught:
        client(attempt_observer=attempts.append).complete_json("s", "u")
    assert len(attempts) == 1 and attempts[0]["http_status"] is None and attempts[0]["input_tokens"] is None
    assert "private transport canary" not in str(caught.value) + json.dumps(attempts)


def test_cancelled_caller_keeps_http_context_open_and_audits_background_finish(transport, monkeypatch, tmp_path):
    entered, release, cancelled, drained = (threading.Event() for _ in range(4))
    results, attempts, observations = [], [], []
    ledger = tmp_path / "background.jsonl"
    sink = stream_audit.jsonl_sink(ledger)

    class Stop(Exception):
        pass

    class BlockingBody(Pieces):
        def __iter__(self):
            yield frame({"content": '{"ok":true}'}).encode()
            entered.set()
            assert release.wait(3)
            yield TAIL.encode()

    body = BlockingBody("")
    transport(lambda _request: httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body))
    monkeypatch.setattr(interrupt, "_POLL_SECONDS", 0.005)

    def stop():
        if cancelled.is_set():
            raise Stop()

    def observe(row):
        attempts.append(row)
        sink(row)
        drained.set()

    def run():
        try:
            with interrupt.watch(stop):
                results.append(client(response_observer=observations.append,
                                      attempt_observer=observe).complete_json("s", "u"))
        except Stop:
            results.append("cancelled")

    worker = threading.Thread(target=run, daemon=True)
    try:
        worker.start()
        assert entered.wait(1)
        cancelled.set()
        worker.join(1)
        assert results == ["cancelled"] and not worker.is_alive()
        assert not body.closed and not attempts and not observations
        assert not ledger.exists()
        release.set()
        assert drained.wait(1) and body.closed
        assert len(attempts) == 1 and attempts[0]["usage_known"] and not observations
        assert len(ledger.read_text().splitlines()) == 1
    finally:
        release.set()
        worker.join(2)


@pytest.mark.parametrize("body,known,complete", [
    (GOOD, True, True),
    (GOOD.replace("data: [DONE]\r\n\r\n", ""), True, False),
    (frame({"content": "{}"}) + frame({}, "stop") + "data: [DONE]\n\n", False, False),
])
def test_factory_opt_in_sink_records_success_and_failed_known_or_unknown_usage_once(
        transport, monkeypatch, tmp_path, body, known, complete):
    path = tmp_path / "attempts.jsonl"
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_chat_transport", "sse")
    monkeypatch.setattr(settings, "compatible_sse_audit_path", str(path))
    transport(lambda _request: response(body))
    instance = build_llm_client("model_gemini_v1")
    assert not path.exists()
    if complete:
        instance.complete_json("private prompt", "private text")
    else:
        with pytest.raises(LLMOutputInvalid):
            instance.complete_json("private prompt", "private text")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["usage_known"] is known
    assert rows[0]["input_tokens"] == (15 if known else None)
    assert rows[0]["protocol_complete"] is complete
    assert rows[0]["transport_version"] == chat_sse.SSE_VERSION and rows[0]["started_at"]
    assert rows[0]["finished_at"] and rows[0]["elapsed_seconds"] >= 0
    assert "private prompt" not in path.read_text() and "private text" not in path.read_text()


def test_sink_is_not_used_by_json_or_disabled_clients_and_does_not_duplicate_across_clients(
        transport, monkeypatch, tmp_path):
    path = tmp_path / "opt-in.jsonl"
    settings = get_settings()
    monkeypatch.setattr(settings, "compatible_sse_audit_path", str(path))
    monkeypatch.setattr(settings, "gemini_chat_transport", "json")
    transport(lambda _request: httpx.Response(200, json={"model": "offline", "usage": USAGE, "choices": [{
        "finish_reason": "stop", "message": {"role": "assistant", "content": "{}"}}]}))
    build_llm_client("model_gemini_v1").complete_json("s", "u")
    assert not path.exists()
    monkeypatch.setattr(settings, "gemini_chat_transport", "sse")
    transport(lambda _request: response())
    build_llm_client("model_gemini_v1").complete_json("s", "u")
    build_llm_client("model_gemini_v1").complete_json("s", "u")
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 2 and rows[0]["attempt_id"] != rows[1]["attempt_id"]


@pytest.mark.parametrize("outcome", ["ok", "quota", "connect"])
def test_sink_write_failure_does_not_retry_or_change_provider_outcome(
        transport, monkeypatch, tmp_path, caplog, outcome):
    settings = get_settings()
    monkeypatch.setattr(settings, "gemini_chat_transport", "sse")
    monkeypatch.setattr(settings, "compatible_sse_audit_path", str(tmp_path))  # a directory cannot be appended
    requests = []

    def handle(request):
        requests.append(request)
        if outcome == "quota":
            return httpx.Response(402, json={"error": {"code": "insufficient_quota"}})
        if outcome == "connect":
            raise httpx.ConnectError("private provider prose")
        return response()

    transport(handle)
    instance = build_llm_client("model_gemini_v1")
    if outcome == "ok":
        assert instance.complete_json("s", "u").text == '{"ok":true}'
    else:
        with pytest.raises(LLMQuotaExceeded if outcome == "quota" else LLMUnavailable):
            instance.complete_json("s", "u")
    assert len(requests) == 1 and "audit delivery failed" in caplog.text
    assert str(tmp_path) not in caplog.text and "private provider prose" not in caplog.text


def test_sink_allowlist_and_append_are_safe_across_processes_and_threads(tmp_path):
    path = tmp_path / "workers" / "ledger.jsonl"
    sink = stream_audit.jsonl_sink(path)
    assert not path.parent.exists()  # constructing a sink is inert
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_sink_worker, str(path), f"thread-{i}", 10) for i in range(4)]
        for future in futures:
            future.result(timeout=5)
    context = multiprocessing.get_context("spawn")
    workers = [context.Process(target=_sink_worker, args=(str(path), f"process-{i}", 5)) for i in range(3)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(10)
        assert worker.exitcode == 0
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == len({row["attempt_id"] for row in rows}) == 55
    assert "private-canary" not in path.read_text()
    assert all(row["input_tokens"] is None and row["profile"]["thinking_headroom"] == 4096 for row in rows)
    assert path.stat().st_mode & 0o077 == 0
    sink({"attempt_id": "last", "input_tokens": None, "output_tokens": None})
    assert len(path.read_text().splitlines()) == 56


def test_cancelled_caller_cannot_release_a_body_owned_capacity_lease(transport, monkeypatch):
    lease = threading.BoundedSemaphore(1)
    entered, release, cancelled, second_dispatched = (threading.Event() for _ in range(4))
    requests, results = [], []

    class Stop(Exception):
        pass

    class LeasedBody(Pieces):
        def __iter__(self):
            if not requests[0] == "first-finished":
                entered.set()
                assert release.wait(3)
            yield from super().__iter__()

        def close(self):
            if not self.closed:
                super().close()
                lease.release()

    def handle(_request):
        assert lease.acquire(timeout=3)
        if not requests:
            requests.append("first")
        else:
            requests[0] = "first-finished"
            second_dispatched.set()
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=LeasedBody(GOOD))

    transport(handle)
    monkeypatch.setattr(interrupt, "_POLL_SECONDS", 0.005)

    def check():
        if cancelled.is_set():
            raise Stop()

    def first():
        try:
            with interrupt.watch(check):
                client().complete_json("s", "u")
        except Stop:
            results.append("cancelled")

    def second():
        results.append(client().complete_json("s", "u").text)

    worker1, worker2 = threading.Thread(target=first, daemon=True), threading.Thread(target=second, daemon=True)
    try:
        worker1.start()
        assert entered.wait(1)
        cancelled.set()
        worker1.join(1)
        assert results == ["cancelled"]
        worker2.start()
        assert not second_dispatched.wait(0.05)
        release.set()
        worker2.join(2)
        assert second_dispatched.is_set() and results == ["cancelled", '{"ok":true}']
    finally:
        release.set()
        worker1.join(2)
        if worker2.ident:
            worker2.join(2)


def test_sse_redirect_still_blocks_forbidden_second_hop_before_transport(transport):
    visited = []

    def handle(request):
        visited.append(request.url.host)
        return httpx.Response(302, headers={"location": f"https://{load_denied_hosts()[0]}/v1/chat/completions"})

    guard = install_network_guard()
    transport(handle)
    try:
        with httpx.Client(follow_redirects=True) as instance, pytest.raises(RuntimeError, match="forbidden"):
            instance.post("https://relay.example/v1/chat/completions", json={"stream": True})
        assert visited == ["relay.example"]
    finally:
        guard()
