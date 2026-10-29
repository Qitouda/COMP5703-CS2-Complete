"""Typed, content-free protocol diagnostics shared by model transports."""
from __future__ import annotations

from app.llm.base import LLMUsage
from app.llm.retry import LLMEmptyContent, LLMOutputInvalid

_OUTPUT_CODES = {
    "invalid_json_response", "invalid_response_envelope", "invalid_choices", "invalid_choice",
    "invalid_assistant_message", "response_truncated", "invalid_tool_calls", "too_many_tool_calls",
    "invalid_tool_call", "duplicate_tool_call_ids", "invalid_assistant_content", "empty_response",
    "invalid_usage",
    "sse_invalid_utf8", "sse_body_too_large", "sse_event_too_large", "sse_output_too_large",
    "sse_too_many_events", "sse_invalid_line", "sse_incomplete_event", "sse_invalid_json",
    "sse_invalid_chunk", "sse_changed_identity", "sse_invalid_identity", "sse_invalid_choices",
    "sse_invalid_delta", "sse_invalid_role", "sse_invalid_content", "sse_choice_after_finish",
    "sse_duplicate_done", "sse_data_after_done", "sse_missing_terminal_frame", "sse_missing_usage",
    "sse_invalid_usage", "sse_conflicting_usage", "sse_invalid_tool_fragment", "sse_invalid_signature",
    "sse_conflicting_signature", "sse_tool_finish_mismatch", "sse_non_sse_response",
    "sse_unsupported_finish_reason",
    "sse_request_failed",
    "sse_unsupported_encoding",
}
_FINISH_REASONS = {"stop", "length", "tool_calls", "function_call", "content_filter",
                   "insufficient_system_resource", "missing", "unknown"}


def safe_provider_diagnostics(value: object) -> dict:
    """Copy only typed, finite protocol facts; never exception/provider prose."""
    if (not isinstance(value, dict) or not isinstance(value.get("provider"), str)
            or value["provider"] not in {"openai", "anthropic", "google"}
            or not isinstance(value.get("error_code"), str) or value["error_code"] not in _OUTPUT_CODES):
        return {}
    result = {"provider": value["provider"], "error_code": value["error_code"]}
    if isinstance(value.get("finish_reason"), str) and value["finish_reason"] in _FINISH_REASONS:
        result["finish_reason"] = value["finish_reason"]
    for key, limit in (("http_status", 599), ("choices_count", 1000), ("tool_call_count", 1000)):
        item = value.get(key)
        if type(item) is int and 0 <= item <= limit:
            result[key] = item
    usage = value.get("usage")
    if isinstance(usage, dict):
        result["usage"] = {key: item for key in ("prompt_tokens", "completion_tokens", "total_tokens")
                           if type(item := usage.get(key)) is int and 0 <= item <= 1_000_000_000}
    return result


def output_error(code: str, data: object, http_status: int, provider: str, *, empty: bool = False):
    facts = {"provider": provider, "error_code": code, "http_status": http_status}
    if isinstance(data, dict):
        facts["usage"] = data.get("usage")
        choices = data.get("choices")
        if isinstance(choices, list):
            facts["choices_count"] = len(choices)
            choice = choices[0] if choices and isinstance(choices[0], dict) else {}
            finish = choice.get("finish_reason")
            facts["finish_reason"] = (finish if isinstance(finish, str) and finish in _FINISH_REASONS
                                      else "missing" if finish is None else "unknown")
            message = choice.get("message")
            if isinstance(message, dict) and isinstance(message.get("tool_calls"), list):
                facts["tool_call_count"] = len(message["tool_calls"])
    error = LLMEmptyContent("provider returned empty content") if empty else LLMOutputInvalid(
        "provider output failed protocol validation: " + code
    )
    error.provider_diagnostics = safe_provider_diagnostics(facts)
    return error


def parse_chat_message(data: object, http_status: int, provider: str) -> tuple[dict, dict]:
    if not isinstance(data, dict):
        raise output_error("invalid_response_envelope", data, http_status, provider)
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise output_error("invalid_choices", data, http_status, provider)
    choice = choices[0]
    if not isinstance(choice, dict):
        raise output_error("invalid_choice", data, http_status, provider)
    # Reject the entire truncated turn before examining or admitting any call.
    if choice.get("finish_reason") == "length":
        raise output_error("response_truncated", data, http_status, provider)
    message = choice.get("message")
    if not isinstance(message, dict) or message.get("role", "assistant") != "assistant":
        raise output_error("invalid_assistant_message", data, http_status, provider)
    return data, message


def response_usage(data, http_status: int, provider: str) -> LLMUsage:
    usage = data.get("usage")
    if usage is None:
        usage = {}
    if (not isinstance(usage, dict) or any(type(usage.get(key, 0)) is not int or usage.get(key, 0) < 0
                                        or usage.get(key, 0) > 1_000_000_000
                                        for key in ("prompt_tokens", "completion_tokens"))):
        raise output_error("invalid_usage", data, http_status, provider)
    return LLMUsage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))

