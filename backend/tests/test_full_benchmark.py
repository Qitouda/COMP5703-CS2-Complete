"""Offline safeguards for the paid corpus runner and its comparison arithmetic."""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import math
import socket
import sys
from collections import Counter
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.llm.base import LLMResponse, LLMUsage
from app.llm.network import load_denied_hosts
from app.llm.retry import LLMOutputInvalid, LLMQuotaExceeded
from scripts import run_full_benchmark as benchmark

DATA_ROOT = benchmark.BACKEND.parent / "data"


@pytest.fixture(autouse=True)
def no_network_or_paid_client(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("These benchmark tests must remain offline.")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(benchmark, "build_client", forbidden)


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [
            {"status": "failed", "reference_total": 7.0, "program_total": 8.0},
            {"status": "pending", "reference_total": 7.0, "program_total": None},
            {"status": "completed", "reference_total": 7.0, "program_total": None},
        ],
    ],
)
def test_metrics_does_not_treat_missing_or_failed_scores_as_zero(rows):
    assert benchmark.metrics(rows) == {"total": len(rows), "paired_count": 0}


def test_metrics_one_pair_has_error_but_no_correlation():
    result = benchmark.metrics([
        {"status": "completed", "reference_total": 7.6, "program_total": 7.2},
    ])

    assert result["total"] == result["paired_count"] == 1
    assert result["mae"] == pytest.approx(0.4)
    assert result["rmse"] == pytest.approx(0.4)
    assert result["mean_signed_difference"] == pytest.approx(-0.4)
    assert result["exact_match_count"] == 0
    assert result["within_0_5_count"] == result["within_1_0_count"] == 1
    assert result["pearson_r"] is None


def test_metrics_reports_paired_accuracy_and_ignores_unusable_rows():
    rows = [
        {"status": "completed", "reference_total": 7.0, "program_total": 7.0},
        {"status": "completed", "reference_total": 8.0, "program_total": 7.5},
        {"status": "completed", "reference_total": 6.0, "program_total": 7.0},
        {"status": "completed", "reference_total": 9.0, "program_total": None},
        {"status": "failed", "reference_total": 1.0, "program_total": 10.0},
        {"status": "pending", "reference_total": 1.0, "program_total": 10.0},
    ]

    result = benchmark.metrics(rows)

    assert result["total"] == 6
    assert result["paired_count"] == 3
    assert result["mae"] == pytest.approx(0.5)
    assert result["rmse"] == pytest.approx(math.sqrt(1.25 / 3))
    assert result["mean_signed_difference"] == pytest.approx(1 / 6)
    assert result["exact_match_count"] == 1
    assert result["within_0_5_count"] == 2
    assert result["within_1_0_count"] == 3
    assert result["pearson_r"] == pytest.approx(math.sqrt(3) / 2)


@pytest.mark.parametrize("pairs", [[(7.0, 6.0), (7.0, 8.0)], [(6.0, 7.0), (8.0, 7.0)]])
def test_metrics_constant_scores_have_undefined_correlation(pairs):
    rows = [
        {"status": "completed", "reference_total": reference, "program_total": score}
        for reference, score in pairs
    ]

    result = benchmark.metrics(rows)

    assert result["paired_count"] == 2
    assert result["mae"] == result["rmse"] == 1.0
    assert result["pearson_r"] is None


def test_main_rejects_a_second_run_before_loading_inputs_or_creating_client(tmp_path, monkeypatch):
    def should_not_prepare(*args, **kwargs):
        raise AssertionError("A locked directory must be rejected before preflight.")

    monkeypatch.setattr(benchmark, "prepare", should_not_prepare)
    monkeypatch.setattr(sys, "argv", ["run_full_benchmark.py", "--output", str(tmp_path), "--execute"])
    with (tmp_path / ".run.lock").open("a") as existing_lock:
        fcntl.flock(existing_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with pytest.raises(SystemExit, match="Another process is already using this run directory"):
                benchmark.main()
        finally:
            fcntl.flock(existing_lock.fileno(), fcntl.LOCK_UN)

    assert not (tmp_path / "run_config.json").exists()
    assert not (tmp_path / "papers").exists()


def test_real_corpus_preflight_covers_all_locked_full_text_without_generating_scores(tmp_path, monkeypatch):
    if not (DATA_ROOT / "data/manifests/pipeline_papers.json").is_file():
        pytest.skip("The independent data-team corpus is not installed in this checkout.")

    observed = []
    original_prompt = benchmark.build_analysis_prompt

    def inspect_full_prompt(doc, anchored_text, rubric):
        prompt = original_prompt(doc, anchored_text, rubric)
        assert all(block.text in prompt for block in doc.blocks)
        observed.append(doc.paper.paper_id)
        return prompt

    monkeypatch.setattr(benchmark, "build_analysis_prompt", inspect_full_prompt)
    rows, config = benchmark.prepare(DATA_ROOT, tmp_path, argparse.Namespace(thinking=False))

    expected_ids = {f"paper_{number:03d}" for number in range(1, 51)}
    assert set(observed) == {row["paper_id"] for row in rows} == expected_ids
    assert len(observed) == len(rows) == config["paper_count"] == 50
    assert Counter(row["subset"] for row in rows) == {"calibration_2024": 30, "temporal_2025_2026": 20}
    assert sum(row["page_count"] for row in rows) == 1348
    assert sum(row["chunk_count"] for row in rows) == 2198
    assert config["runner_sha256"] == benchmark.digest(Path(benchmark.__file__).read_bytes())
    assert config["input_mode"] == "data_team_locked_full_structured_text_no_truncation"
    assert all(row["status"] == "pending" and row["program_total"] is None for row in rows)
    assert all(row["program_dimensions"] == {} for row in rows)
    assert all(set(row["reference_dimensions"]) == set(benchmark.DIMENSIONS) for row in rows)
    assert not (tmp_path / "papers").exists()


def test_runner_identity_change_rejects_old_checkpoint_without_overwriting_it(tmp_path, monkeypatch):
    if not (DATA_ROOT / "data/manifests/pipeline_papers.json").is_file():
        pytest.skip("The independent data-team corpus is not installed in this checkout.")

    runner_copy = tmp_path / "runner_identity.py"
    runner_copy.write_bytes(Path(benchmark.__file__).read_bytes())
    monkeypatch.setattr(benchmark, "__file__", str(runner_copy))
    output = tmp_path / "run"
    args = argparse.Namespace(thinking=False)
    _, first_config = benchmark.prepare(DATA_ROOT, output, args)
    original_config_bytes = (output / "run_config.json").read_bytes()
    original_plan_bytes = (output / "input_plan.json").read_bytes()
    _, resumed_config = benchmark.prepare(DATA_ROOT, output, args)
    assert resumed_config == first_config

    runner_copy.write_bytes(runner_copy.read_bytes() + b"\n# Different runner identity for the test.\n")
    assert benchmark.digest(runner_copy.read_bytes()) != first_config["runner_sha256"]

    with pytest.raises(ValueError, match="Existing run has different inputs/settings"):
        benchmark.prepare(DATA_ROOT, output, args)

    assert (output / "run_config.json").read_bytes() == original_config_bytes
    assert (output / "input_plan.json").read_bytes() == original_plan_bytes
    assert not (output / "papers").exists()


def test_provider_configuration_keeps_relay_balance_units_separate_from_usd():
    settings = Settings(_env_file=None, openai_base_url="https://www.yunzhuhub.com/v1")
    config = benchmark.provider_configuration(settings, argparse.Namespace(provider="openai"))
    assert config["model"] == "gpt-6.1-sol"
    assert config["reasoning_effort"] == "medium"
    assert "temperature" not in config
    assert config["pricing"]["currency"] == "platform_unit"
    assert config["pricing"]["input_per_million"] == 1.5
    assert config["pricing"]["output_per_million"] == 9
    assert config["price_source"] == benchmark.RELAY_PRICE_SOURCE


def test_usage_normalization_counts_reasoning_once_and_honors_chat_completion_fields():
    assert benchmark.normalize_usage({"input_tokens": 100, "output_tokens": 30,
                                      "input_tokens_details": {"cached_tokens": 40},
                                      "output_tokens_details": {"reasoning_tokens": 20}}) == {
        "prompt_tokens": 100, "completion_tokens": 30, "prompt_cache_hit_tokens": 40,
        "prompt_cache_miss_tokens": 60, "reasoning_tokens": 20,
    }
    usage = benchmark.normalize_usage({"prompt_tokens": 15, "completion_tokens": 8,
                                       "input_tokens": 15, "output_tokens": 0})
    assert usage["completion_tokens"] == 8
    assert benchmark.normalize_usage(None) is None
    assert benchmark.normalize_usage({}) is None


def test_network_guard_blocks_the_retired_host_before_the_transport():
    requests = []
    transport = httpx.MockTransport(lambda request: requests.append(request) or httpx.Response(200))
    restore = benchmark.install_network_guard()
    try:
        with httpx.Client(transport=transport) as client:
            with pytest.raises(RuntimeError, match="disabled model provider"):
                client.get(f"https://api.{load_denied_hosts()[0]}/v1/models")
            assert not requests
            assert client.get("https://www.yunzhuhub.com/v1/models").status_code == 200
            assert len(requests) == 1
    finally:
        restore()


@pytest.mark.parametrize("asynchronous", [False, True])
def test_network_guard_checks_redirect_hops_before_transport(asynchronous):
    seen = []

    def handler(request):
        seen.append(request.url.host)
        return httpx.Response(302, headers={"location": f"https://api.{load_denied_hosts()[0]}/v1/models"})

    transport = httpx.MockTransport(handler)
    restore = benchmark.install_network_guard()
    try:
        if asynchronous:
            async def run():
                async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
                    await client.get("https://allowed.example/start")

            with pytest.raises(RuntimeError, match="disabled model provider"):
                asyncio.run(run())
        else:
            with httpx.Client(transport=transport, follow_redirects=True) as client:
                with pytest.raises(RuntimeError, match="disabled model provider"):
                    client.get("https://allowed.example/start")
        assert seen == ["allowed.example"]
    finally:
        restore()


def test_audited_client_retains_usage_from_a_failed_output_and_its_retry(tmp_path, monkeypatch):
    real_retry = benchmark.call_with_retry
    monkeypatch.setattr(benchmark, "call_with_retry", lambda fn, policy: real_retry(fn, policy, sleep=lambda _: None))

    class FakeProvider:
        model_id = "model_gpt_v1"
        model_version = "gpt-6.1-sol"
        calls = 0

        def complete_json(self, *args, **kwargs):
            self.calls += 1
            raw = {"id": f"response_{self.calls}", "model": self.model_version,
                   "usage": {"input_tokens": self.calls * 10, "output_tokens": self.calls * 20}}
            self.observer(raw)
            if self.calls == 1:
                raise LLMOutputInvalid("incomplete response")
            return LLMResponse(text='{"ok":true}', model_id=self.model_id, model_version=self.model_version,
                               usage=LLMUsage(20, 40), raw=raw)

    provider = FakeProvider()

    def build(settings, config, *, response_observer):
        provider.observer = response_observer
        return provider

    monkeypatch.setattr(benchmark, "build_client", build)
    settings = Settings(_env_file=None)
    config = {**benchmark.provider_configuration(settings, argparse.Namespace(provider="openai")),
              "timeout_seconds": 180, "max_attempts_per_call": 3}
    client = benchmark.AuditedClient(settings, tmp_path, config, "attempt_01")
    client.complete_json("system", "task")
    assert [row["status"] for row in client.calls] == ["failed", "completed"]
    assert [row["usage"]["completion_tokens"] for row in client.calls] == [20, 40]
    assert len(list(tmp_path.glob("*.response.json"))) == 2


def test_quota_error_trips_shared_batch_and_next_call_never_reaches_provider(tmp_path, monkeypatch):
    class Provider:
        model_id = "model_gpt_v1"
        model_version = "gpt-6.1-sol"
        calls = 0

        def complete_json(self, *args, **kwargs):
            self.calls += 1
            raise LLMQuotaExceeded("balance exhausted")

    provider = Provider()
    monkeypatch.setattr(benchmark, "build_client", lambda *args, **kwargs: provider)
    settings = Settings(_env_file=None)
    config = {**benchmark.provider_configuration(settings, argparse.Namespace(provider="openai")),
              "timeout_seconds": 180, "max_attempts_per_call": 3}
    control = benchmark.BatchControl()
    client = benchmark.AuditedClient(settings, tmp_path, config, "attempt_01", batch_control=control)
    with pytest.raises(LLMQuotaExceeded):
        client.complete_json("system", "task")
    assert provider.calls == 1
    assert control.reason == "provider_quota_exhausted"
    with pytest.raises(benchmark.BatchStopped):
        client.complete_json("system", "another paper")
    assert provider.calls == 1
    assert len(client.calls) == 1


def test_rolling_batch_does_not_submit_remaining_papers_after_permanent_error(tmp_path, monkeypatch):
    launched, completed = [], []

    def score(*args, batch_control):
        row = args[2]
        launched.append(row["paper_id"])
        batch_control.stop("provider_authentication_rejected")
        return {"paper_id": row["paper_id"], "status": "failed", "stopped_reason": batch_control.reason}

    monkeypatch.setattr(benchmark, "score_one", score)
    reason = benchmark.run_targets(None, tmp_path, [{"paper_id": str(i)} for i in range(50)], {}, None,
                                   workers=1, on_result=lambda row, stopped: completed.append((row, stopped)))
    assert reason == "provider_authentication_rejected"
    assert launched == ["0"]
    assert len(completed) == 1


def test_stopped_export_keeps_unstarted_rows_pending_and_persists_reason(tmp_path):
    settings = Settings(_env_file=None)
    config = {**benchmark.provider_configuration(settings, argparse.Namespace(provider="openai")),
              "backend_commit": "test", "created_at": "2026-10-25T00:00:00Z", "configuration_sha256": "test"}
    plan = [{"paper_id": f"paper_{i:03d}", "version": "v1", "title": "Paper", "subset": "calibration_2024",
             "status": "pending", "reference_total": 7.0, "program_total": None,
             "reference_dimensions": dict.fromkeys(benchmark.DIMENSIONS, 7), "program_dimensions": {}}
            for i in range(1, 4)]
    first = {**plan[0], "status": "failed", "error": "billing quota exhausted"}
    benchmark.save_json(tmp_path / "papers" / "paper_001" / "result.json", first)
    summary = benchmark.export_comparison(tmp_path, plan, config, stopped_reason="provider_quota_exhausted")
    assert summary["failed_count"] == 1 and summary["pending_count"] == 2
    record = benchmark.read_json(tmp_path / "run_record.json")
    assert record["status"] == "stopped"
    assert record["stopped_reason"] == "provider_quota_exhausted"
    assert not (tmp_path / "papers" / "paper_002").exists()
    # A read-only re-export cannot erase the stop signal.
    assert benchmark.export_comparison(tmp_path, plan, config)["stopped_reason"] == "provider_quota_exhausted"
