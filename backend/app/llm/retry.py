"""BE-05：超时、限流、空返回的重试。

模型 JSON 请求可能偶尔返回空内容，因此「空返回」必须
是一条独立的重试分支，不能只处理超时和限流。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from app.schemas.enums import ErrorCode

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """所有模型调用异常的基类。"""

    error_code: ErrorCode = ErrorCode.INTERNAL_ERROR
    retryable: bool = False


class LLMUnavailable(LLMError):
    error_code = ErrorCode.MODEL_UNAVAILABLE
    retryable = True


class LLMRequestRejected(LLMUnavailable):
    """A permanent provider rejection that must not be retried unchanged."""

    retryable = False


class LLMAuthenticationError(LLMRequestRejected):
    """The credential or its permissions cannot authorize this request."""


class LLMQuotaExceeded(LLMRequestRejected):
    """Billing balance or a hard spending quota has been exhausted."""


class LLMTimeout(LLMError):
    error_code = ErrorCode.MODEL_TIMEOUT
    retryable = True


class LLMRateLimited(LLMError):
    error_code = ErrorCode.MODEL_UNAVAILABLE
    retryable = True


class LLMEmptyContent(LLMError):
    """请求返回 200 但 content 为空，按可重试输出失败处理。"""

    error_code = ErrorCode.MODEL_OUTPUT_INVALID
    retryable = True


class LLMOutputInvalid(LLMError):
    error_code = ErrorCode.MODEL_OUTPUT_INVALID
    retryable = True


def check_provider_response(response):
    """Classify HTTP errors without exposing provider bodies or credentials.

    A normal throughput limit is retryable. Billing exhaustion is permanent even
    when a provider returns it as HTTP 429 instead of HTTP 402/403.
    """
    status = response.status_code
    if status < 400:
        return
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    error = error if isinstance(error, dict) else {}
    identifiers = {str(error.get(key, "")).casefold() for key in ("code", "type")}
    quota_codes = {
        "insufficient_quota", "insufficient_user_quota", "insufficient_balance",
        "billing_hard_limit_reached", "billing_limit_exceeded", "credit_balance_exhausted",
    }
    auth_codes = {"invalid_api_key", "invalid_key", "invalid_token", "authentication_error",
                  "unauthorized", "invalid_credentials", "access_denied", "token_expired"}
    message = str(error.get("message", "")).casefold()
    quota_messages = (
        "insufficient quota", "insufficient balance", "quota exhausted", "credit balance is too low",
        "exceeded your current quota", "余额不足", "额度不足", "额度已用尽",
    )
    throughput_limit = any(fragment in message for fragment in (
        "per minute", "per-minute", "rate limit", "tokens-per-minute", "requests-per-minute",
    ))
    generic_hard_quota = "quota_exceeded" in identifiers and not throughput_limit
    if identifiers & quota_codes or generic_hard_quota or any(fragment in message for fragment in quota_messages):
        raise LLMQuotaExceeded(f"provider billing quota exhausted: {status}")
    if status in {401, 403} or identifiers & auth_codes:
        raise LLMAuthenticationError(f"provider authentication or permission rejected: {status}")
    if status == 429:
        raise LLMRateLimited("rate limited by provider")
    if status == 408:
        raise LLMTimeout("provider request timed out")
    if status >= 500:
        raise LLMUnavailable(f"provider returned {status}")
    raise LLMRequestRejected(f"provider rejected the request: {status}")


@dataclass
class RetryPolicy:
    max_attempts: int = 3          # 首次 + 2 次重试
    base_delay_seconds: float = 1.0
    backoff_factor: float = 2.0
    max_delay_seconds: float = 20.0

    def delay_for(self, attempt: int) -> float:
        return min(
            self.base_delay_seconds * (self.backoff_factor ** (attempt - 1)),
            self.max_delay_seconds,
        )


def call_with_retry(fn, policy: RetryPolicy | None = None, *, sleep=time.sleep):
    """执行 fn()，对可重试的 LLMError 按退避重试。

    `sleep` 参数是为了让单元测试跑得快，不要在生产代码里传。
    """
    policy = policy or RetryPolicy()
    last: LLMError | None = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except LLMError as exc:
            last = exc
            if not exc.retryable or attempt == policy.max_attempts:
                raise
            delay = policy.delay_for(attempt)
            logger.warning(
                "llm call failed (attempt %s/%s): %s; retrying in %.1fs",
                attempt,
                policy.max_attempts,
                exc.__class__.__name__,
                delay,
            )
            sleep(delay)

    assert last is not None
    raise last
