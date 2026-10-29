"""Permanent billing/auth failures must not consume retry budgets."""
from __future__ import annotations

import httpx
import pytest

from app.llm import openai as openai_module
from app.llm.openai import OpenAIClient
from app.llm.retry import (
    LLMAuthenticationError,
    LLMQuotaExceeded,
    LLMRateLimited,
    LLMRequestRejected,
    LLMTimeout,
    LLMUnavailable,
    RetryPolicy,
    call_with_retry,
    check_provider_response,
)


@pytest.mark.parametrize("status,error,expected", [
    (401, {}, LLMAuthenticationError),
    (403, {"code": "access_denied"}, LLMAuthenticationError),
    (400, {"code": "invalid_api_key"}, LLMAuthenticationError),
    (429, {"code": "insufficient_quota"}, LLMQuotaExceeded),
    (403, {"code": "insufficient_user_quota"}, LLMQuotaExceeded),
    (402, {"message": "用户额度不足"}, LLMQuotaExceeded),
    (429, {"code": "rate_limit_exceeded", "message": "Too many requests per minute"}, LLMRateLimited),
    (429, {"code": "quota_exceeded", "message": "Token quota per minute exceeded"}, LLMRateLimited),
    (400, {"code": "invalid_request_error"}, LLMRequestRejected),
    (408, {}, LLMTimeout),
    (503, {}, LLMUnavailable),
])
def test_http_error_classification_preserves_transient_rate_limits(status, error, expected):
    with pytest.raises(expected) as caught:
        check_provider_response(httpx.Response(status, json={"error": error}))
    assert caught.value.retryable is (expected in {LLMRateLimited, LLMTimeout, LLMUnavailable})


@pytest.mark.parametrize("use_tools", [False, True])
def test_openai_auth_failure_sends_only_once_under_retry_policy(monkeypatch, use_tools):
    requests = []
    real_client = httpx.Client

    def handler(request):
        requests.append(request)
        return httpx.Response(401, json={"error": {"code": "invalid_api_key", "message": "Rejected"}})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(openai_module.httpx, "Client", lambda **kwargs: real_client(transport=transport))
    client = OpenAIClient(api_key="TEST_ONLY")
    action = (lambda: client.complete_tools([{"role": "user", "content": "x"}], [])) if use_tools else (
        lambda: client.complete_json("Return JSON", "x")
    )
    with pytest.raises(LLMAuthenticationError):
        call_with_retry(action, RetryPolicy(max_attempts=3), sleep=lambda _: None)
    assert len(requests) == 1


def test_normal_rate_limit_retries_and_can_recover():
    attempts = []

    def request():
        attempts.append(1)
        status = 429 if len(attempts) < 3 else 200
        response = httpx.Response(status, json={"error": {"code": "rate_limit_exceeded"}})
        check_provider_response(response)
        return "recovered"

    assert call_with_retry(request, RetryPolicy(max_attempts=3), sleep=lambda _: None) == "recovered"
    assert len(attempts) == 3
