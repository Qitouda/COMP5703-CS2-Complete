"""CLI/product selection parity and actual Mock payloads; never paid requests."""
from __future__ import annotations

import argparse
import json

import httpx
import pytest

from app.config import Settings
from app.llm.compatible import CompatibleChatClient
from app.llm.retry import LLMOutputInvalid
from app.llm.streaming import StreamingCompatibleChatClient
from app.pipeline import orchestrator
from scripts import run_full_benchmark as benchmark


def sse_reply(*, terminal=True):
    values = [{"choices": [{"index": 0, "delta": {"role": "assistant", "content": "{}"}, "finish_reason": None}]},
              {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
              {"choices": [], "usage": {"prompt_tokens": 27, "completion_tokens": 1}}]
    wire = "".join("data: " + json.dumps({"id": "cli-offline", "model": "served-model", **value}) + "\n\n"
                   for value in values)
    if terminal:
        wire += "data: [DONE]\n\n"
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=wire.encode())


@pytest.fixture
def transport(monkeypatch):
    original = httpx.Client.__init__

    def configure(handler):
        def init(instance, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(handler)
            return original(instance, *args, **kwargs)
        monkeypatch.setattr(httpx.Client, "__init__", init)
    return configure


@pytest.mark.parametrize("provider", ["google", "anthropic"])
@pytest.mark.parametrize("mode", ["json", "sse"])
def test_cli_effective_config_matches_product_client_and_actual_payload(
        monkeypatch, tmp_path, transport, provider, mode):
    ledger = tmp_path / "model-ledger.jsonl"
    settings = Settings(_env_file=None, gemini_api_key="private-test-canary", anthropic_api_key="private-test-canary",
        gemini_base_url="https://relay.example/v1", anthropic_base_url="https://relay.example/v1",
        gemini_chat_transport=mode, anthropic_chat_transport=mode, gemini_reasoning_effort="low",
        gemini_thinking_headroom=4096, compatible_sse_audit_path=str(ledger), llm_timeout_seconds=120)
    args = argparse.Namespace(provider=provider, model="explicit-model-override")
    config = benchmark.provider_configuration(settings, args)
    seen, sent = [], []

    def handle(request):
        sent.append(json.loads(request.content))
        if mode == "sse":
            return sse_reply()
        return httpx.Response(200, json={"model": "served-model", "usage": {
            "prompt_tokens": 27, "completion_tokens": 1}, "choices": [{"finish_reason": "stop", "message": {
                "role": "assistant", "content": "{}"}}]})

    transport(handle)
    cli = benchmark.build_client(settings, config, response_observer=seen.append)
    monkeypatch.setattr(orchestrator, "get_settings", lambda: settings)
    product = orchestrator.build_llm_client(config["model_id"])
    assert type(cli) is type(product)
    assert isinstance(cli, StreamingCompatibleChatClient) is (mode == "sse")
    assert cli.profile_metadata == product.profile_metadata == config["profile"]
    assert cli.timeout == product.timeout == config["timeout_seconds"] == (300 if provider == "google" else 120)
    assert cli.transport == config["transport"] == mode
    assert config["sse_audit_enabled"] is (mode == "sse") and not ledger.exists()
    assert config["model"] == cli.model == "explicit-model-override"
    assert "private-test-canary" not in json.dumps(config) and str(ledger) not in json.dumps(config)
    assert cli.complete_json("system", "paper", max_tokens=25000).text == "{}"
    assert len(seen) == len(sent) == 1 and seen[0]["model"] == "served-model"
    assert sent[0]["model"] == "explicit-model-override"
    if provider == "google":
        assert config["reasoning_effort"] == "low" and config["profile"]["thinking_headroom"] == 4096
        assert sent[0]["max_tokens"] == 29096 and sent[0]["reasoning_effort"] == "low"
        assert "temperature" not in sent[0] and sent[0]["response_format"] == {"type": "json_object"}
    else:
        assert config["reasoning_effort"] is None and config["profile"]["thinking_headroom"] == 0
        assert sent[0]["max_tokens"] == 25000 and sent[0]["temperature"] == 0.2
        assert "reasoning_effort" not in sent[0] and "response_format" not in sent[0]
    if mode == "sse":
        assert sent[0]["stream"] and sent[0]["stream_options"] == {"include_usage": True}
        assert len(ledger.read_text().splitlines()) == 1
    else:
        assert "stream" not in sent[0] and not ledger.exists()


@pytest.mark.parametrize("provider", ["google", "anthropic"])
def test_cli_compatible_defaults_remain_json_with_actual_inherited_timeout(provider):
    settings = Settings(_env_file=None, gemini_chat_transport="json", anthropic_chat_transport="json",
        gemini_reasoning_effort="medium", gemini_thinking_headroom=24576, compatible_sse_audit_path="",
        llm_timeout_seconds=120)
    config = benchmark.provider_configuration(settings, argparse.Namespace(provider=provider))
    instance = benchmark.build_client(settings, config)
    assert type(instance) is CompatibleChatClient
    assert config["transport"] == "json" and not config["sse_audit_enabled"]
    if provider == "google":
        assert config["profile"]["thinking_headroom"] == 24576 and config["reasoning_effort"] == "medium"
        assert instance.timeout == config["timeout_seconds"] == 300


@pytest.mark.parametrize("mode", ["json", "sse"])
@pytest.mark.parametrize("requested,expected_budget", [(700, 8192), (25000, 25000)])
def test_google_minimal_zero_headroom_flows_to_wire_metadata_and_optional_sink(
        transport, monkeypatch, tmp_path, mode, requested, expected_budget):
    ledger = tmp_path / "minimal.jsonl"
    settings = Settings(_env_file=None, gemini_model="gemini-3.1-flash-lite", gemini_chat_transport=mode,
        gemini_reasoning_effort="minimal", gemini_thinking_headroom=0,
        compatible_sse_audit_path=str(ledger), llm_timeout_seconds=120)
    config = benchmark.provider_configuration(settings, argparse.Namespace(provider="google"))
    instance = benchmark.build_client(settings, config)
    monkeypatch.setattr(orchestrator, "get_settings", lambda: settings)
    assert orchestrator.build_llm_client("model_gemini_v1").profile_metadata == instance.profile_metadata
    assert config["reasoning_effort"] == "minimal" and config["profile"]["thinking_headroom"] == 0
    assert config["profile"]["thinking"] is True and config["timeout_seconds"] == 300
    sent = []

    def handle(request):
        sent.append(json.loads(request.content))
        if mode == "sse":
            return sse_reply()
        return httpx.Response(200, json={"model": "served-model", "usage": {
            "prompt_tokens": 27, "completion_tokens": 1}, "choices": [{"finish_reason": "stop", "message": {
                "role": "assistant", "content": "{}"}}]})

    transport(handle)
    assert instance.complete_json("system", "paper", max_tokens=requested).text == "{}"
    assert sent[0]["model"] == "gemini-3.1-flash-lite" and sent[0]["reasoning_effort"] == "minimal"
    assert sent[0]["max_tokens"] == expected_budget and "temperature" not in sent[0]
    if mode == "sse":
        row = json.loads(ledger.read_text())
        assert row["profile"]["reasoning_effort"] == "minimal" and row["profile"]["thinking_headroom"] == 0
    else:
        assert not ledger.exists()
    assert Settings.model_fields["gemini_reasoning_effort"].default == "medium"
    assert Settings.model_fields["gemini_chat_transport"].default == "json"


@pytest.mark.parametrize("model", ["gpt-6.1-sol", "gpt-4o"])
def test_gpt_cli_model_reasoning_observer_and_180s_timeout_are_preserved(transport, model):
    settings = Settings(_env_file=None, openai_base_url="https://relay.example/v1")
    config = benchmark.provider_configuration(settings, argparse.Namespace(provider="openai", model=model,
                                                                          reasoning_effort="high"))
    sent, seen = [], []

    def handle(request):
        assert request.url.path == "/v1/responses"
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"model": "served-gpt", "output": [{"type": "message", "content": [
            {"type": "output_text", "text": "{}"}]}], "usage": {"input_tokens": 9, "output_tokens": 3}})

    transport(handle)
    instance = benchmark.build_client(settings, config, response_observer=seen.append)
    assert instance.timeout == config["timeout_seconds"] == 180
    assert instance.complete_json("system", "paper").text == "{}"
    assert config["model"] == sent[0]["model"] == model and len(seen) == 1
    if model == "gpt-6.1-sol":
        assert config["reasoning_effort"] == "high" and sent[0]["reasoning"] == {"effort": "high"}
    else:
        assert config["reasoning_effort"] is None and "reasoning" not in sent[0]


def test_compatible_client_refuses_config_drift_before_request_or_sink_creation(tmp_path):
    settings = Settings(_env_file=None, gemini_chat_transport="sse", gemini_reasoning_effort="low",
        gemini_thinking_headroom=4096, compatible_sse_audit_path=str(tmp_path / "ledger.jsonl"))
    config = benchmark.provider_configuration(settings, argparse.Namespace(provider="google"))
    settings.gemini_thinking_headroom = 8192
    with pytest.raises(ValueError, match="changed since preflight"):
        benchmark.build_client(settings, config)
    assert not (tmp_path / "ledger.jsonl").exists()


def test_preflight_persists_effective_profile_transport_and_timeout_without_exposing_sink_path(tmp_path, monkeypatch):
    data = benchmark.BACKEND.parent / "data"
    if not (data / "data/manifests/pipeline_papers.json").is_file():
        pytest.skip("The independent data corpus is unavailable.")
    ledger = tmp_path / "private-ledger.jsonl"
    settings = Settings(_env_file=None, gemini_chat_transport="sse", gemini_reasoning_effort="low",
        gemini_thinking_headroom=4096, compatible_sse_audit_path=str(ledger), llm_timeout_seconds=120)
    monkeypatch.setattr(benchmark, "Settings", lambda **_kwargs: settings)
    args = argparse.Namespace(provider="google")
    output = tmp_path / "preflight"
    _, config = benchmark.prepare(data, output, args)
    saved = (output / "run_config.json").read_bytes()
    metadata = json.loads(saved)
    assert metadata["profile"]["thinking_headroom"] == 4096 and metadata["reasoning_effort"] == "low"
    assert metadata["transport"] == "sse" and metadata["timeout_seconds"] == 300
    assert metadata["sse_audit_enabled"] and str(ledger) not in saved.decode() and not ledger.exists()
    assert metadata["configuration_sha256"] == config["configuration_sha256"]
    settings.gemini_chat_transport = "json"
    with pytest.raises(ValueError, match="different inputs/settings"):
        benchmark.prepare(data, output, args)
    assert (output / "run_config.json").read_bytes() == saved


def test_cli_sse_failure_keeps_known_usage_even_without_a_success_response_observer(tmp_path, transport):
    settings = Settings(_env_file=None, gemini_chat_transport="sse", gemini_reasoning_effort="low",
                        gemini_thinking_headroom=4096)
    config = benchmark.provider_configuration(settings, argparse.Namespace(provider="google"))
    config["max_attempts_per_call"] = 1
    transport(lambda _request: sse_reply(terminal=False))
    audited = benchmark.AuditedClient(settings, tmp_path, config, "fresh")
    with pytest.raises(LLMOutputInvalid):
        audited.complete_json("system", "paper")
    assert len(audited.calls) == 1 and audited.calls[0]["status"] == "failed"
    assert audited.calls[0]["usage"]["prompt_tokens"] == 27 and audited.calls[0]["usage"]["completion_tokens"] == 1
    assert audited.calls[0]["usage_source"] == "provider_diagnostics_core_counts_only"
    assert audited.calls[0]["usage_details_known"] is False
    assert not list(tmp_path.glob("*.response.json"))  # no synthetic response is invented
