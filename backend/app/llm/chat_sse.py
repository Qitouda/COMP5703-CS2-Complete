"""Bounded Chat Completions SSE framing and assembly; no transport or persistence.

Supports LF/CRLF records and complete (not concatenated) thought signatures at
tool, function and extra_content.google levels. Differing signature fragments
are rejected: no real signed-fragment protocol has been established.

The byte limits are safety bounds, not model token budgets. Even the maximum
65,536-token profile has ample visible-output headroom; comments/opaque fields
still count against the entire stream limit.
"""
from __future__ import annotations

import codecs
import json

import httpx

from app.llm.audit import redact_opaque
from app.llm.diagnostics import output_error, parse_chat_message
from app.llm.retry import LLMUnavailable, check_provider_response

SSE_VERSION = "compatible-chat-sse-1"
MAX_STREAM_BYTES = 16 * 1024 * 1024
MAX_EVENT_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_EVENTS = 100_000
_TOKEN_COUNTERS = {
    "prompt_tokens", "completion_tokens", "total_tokens", "input_tokens", "output_tokens",
    "cached_tokens", "text_tokens", "audio_tokens", "image_tokens", "reasoning_tokens",
    "accepted_prediction_tokens", "rejected_prediction_tokens", "cache_write_tokens",
    "cache_creation_input_tokens", "cache_read_input_tokens", "claude_cache_creation_5_m_tokens",
    "claude_cache_creation_1_h_tokens",
}
_USAGE_CONTAINERS = {
    "prompt_tokens_details", "completion_tokens_details", "input_tokens_details", "output_tokens_details",
    "billing_usage", "claude_usage", "cache_creation",
}


def numeric_usage(value, depth: int = 0, *, details: bool = False) -> dict:
    """Project token counters, numeric details and Claude billing counters only.

    The relay's observed usage_source/usage_semantic and billing source/semantic
    strings are metadata, not counters. They cannot invalidate a complete Chat
    response or enter the ledger. Known counters still reject bad types/values.
    """
    if not isinstance(value, dict) or depth > 8:
        raise ValueError("invalid numeric usage")
    result = {}
    for key, item in redact_opaque(value).items():
        if key in _USAGE_CONTAINERS:
            if item is not None:
                result[key] = numeric_usage(item, depth + 1, details=key.endswith("_details")
                                            or key in {"claude_usage", "cache_creation"})
        elif key in _TOKEN_COUNTERS or details and type(item) is int:
            if item is not None:
                if type(item) is not int or not 0 <= item <= 1_000_000_000:
                    raise ValueError("invalid numeric usage")
                result[key] = item
    return result


class ChatStream:
    def __init__(self, provider: str = "google", http_status: int = 200):
        self.provider, self.http_status = provider, http_status
        self.decoder = codecs.getincrementaldecoder("utf-8")("strict")
        self.buffer, self.lines = "", []
        self.bytes_received = self.event_bytes = self.output_bytes = self.event_count = 0
        self.identity, self.tools, self.content = {}, {}, []
        self.usage, self.finish_reason = None, None
        self.done = self.eof = self.usage_conflicted = False

    def snapshot(self) -> dict:
        message = {"role": "assistant", "content": "".join(self.content)}
        if self.tools:
            message["tool_calls"] = [self.tools[i] for i in sorted(self.tools)]
        return {**self.identity, "object": "chat.completion",
                "choices": [{"index": 0, "message": message, "finish_reason": self.finish_reason}],
                "usage": {} if self.usage_conflicted else self.usage or {}}

    def invalid(self, code: str):
        return output_error(code, self.snapshot(), self.http_status, self.provider)

    def feed(self, block: bytes) -> None:
        self.bytes_received += len(block)
        if self.bytes_received > MAX_STREAM_BYTES:
            raise self.invalid("sse_body_too_large")
        try:
            self.buffer += self.decoder.decode(block)
        except UnicodeError as exc:
            raise self.invalid("sse_invalid_utf8") from exc
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            self._line(line.removesuffix("\r"))
        if self.event_bytes + len(self.buffer.encode("utf-8")) > MAX_EVENT_BYTES:
            raise self.invalid("sse_event_too_large")

    def _line(self, line: str) -> None:
        self.event_bytes += len(line.encode("utf-8")) + 1
        if self.event_bytes > MAX_EVENT_BYTES:
            raise self.invalid("sse_event_too_large")
        if not line:
            self.event_bytes = 0
            if self.lines:
                event, self.lines = "\n".join(self.lines), []
                self._event(event)
        elif line.startswith("data:"):
            self.lines.append(line[5:].removeprefix(" "))
        elif not line.startswith((":", "event:", "id:", "retry:")):
            raise self.invalid("sse_invalid_line")

    def _numeric_usage(self, value):
        try:
            return numeric_usage(value)
        except ValueError as exc:
            raise self.invalid("sse_invalid_usage") from exc

    def _event(self, event: str) -> None:
        if event == "[DONE]":
            if self.done:
                raise self.invalid("sse_duplicate_done")
            self.done = True
            return
        if self.done:
            raise self.invalid("sse_data_after_done")
        self.event_count += 1
        if self.event_count > MAX_EVENTS:
            raise self.invalid("sse_too_many_events")
        try:
            chunk = json.loads(event)
        except (ValueError, RecursionError) as exc:
            raise self.invalid("sse_invalid_json") from exc
        if not isinstance(chunk, dict):
            raise self.invalid("sse_invalid_chunk")
        if "error" in chunk:
            error = chunk["error"]
            if not isinstance(error, dict):
                raise LLMUnavailable("provider returned an SSE error")
            code = str(error.get("code", "")).casefold()
            status = 429 if "rate" in code or "concurrency" in code else 503
            if "auth" in code or "invalid_api_key" in code:
                status = 401
            check_provider_response(httpx.Response(status, json={"error": error}))
            raise LLMUnavailable("provider returned an SSE error")
        for key in ("id", "model", "created"):
            if chunk.get(key) is None:
                continue
            value = chunk[key]
            valid = (type(value) is int and value >= 0 if key == "created"
                     else isinstance(value, str) and 0 < len(value) <= 512)
            if not valid:
                raise self.invalid("sse_invalid_identity")
            if key in self.identity and self.identity[key] != value:
                raise self.invalid("sse_changed_identity")
            self.identity[key] = value
        if chunk.get("usage") is not None:
            candidate = self._numeric_usage(chunk["usage"])
            if self.usage is not None and any(
                    key in candidate and key in self.usage and candidate[key] != self.usage[key]
                    for key in ("prompt_tokens", "completion_tokens")):
                self.usage_conflicted = True
                raise self.invalid("sse_conflicting_usage")
            # Compare the Chat totals, not ancillary aliases/metadata. Preserve
            # the latest numeric aliases separately for accounting inspection.
            self.usage = (candidate if any(key in candidate for key in ("prompt_tokens", "completion_tokens"))
                          else {**(self.usage or {}), **candidate})
        choices = chunk.get("choices")
        if not isinstance(choices, list) or len(choices) > 1:
            raise self.invalid("sse_invalid_choices")
        if not choices:
            if chunk.get("usage") is None:
                raise self.invalid("sse_invalid_choices")
            return
        choice = choices[0]
        if not isinstance(choice, dict) or type(choice.get("index")) is not int or choice["index"] != 0:
            raise self.invalid("sse_invalid_choices")
        delta = choice.get("delta")
        if not isinstance(delta, dict):
            raise self.invalid("sse_invalid_delta")
        if self.finish_reason is not None and (any(delta.get(k) for k in ("role", "content", "tool_calls"))
                                               or choice.get("finish_reason") is not None):
            raise self.invalid("sse_choice_after_finish")
        if delta.get("role") not in (None, "assistant"):
            raise self.invalid("sse_invalid_role")
        if delta.get("content") is not None:
            if not isinstance(delta["content"], str):
                raise self.invalid("sse_invalid_content")
            self._append(self.content, delta["content"])
        if delta.get("tool_calls") is not None:
            if not isinstance(delta["tool_calls"], list):
                raise self.invalid("sse_invalid_tool_fragment")
            for fragment in delta["tool_calls"]:
                self._tool(fragment)
        if choice.get("finish_reason") is not None:
            finish = choice["finish_reason"]
            self.finish_reason = finish
            if finish == "length":
                raise self.invalid("response_truncated")
            if finish not in ("stop", "tool_calls"):
                raise self.invalid("sse_unsupported_finish_reason")

    def _count(self, text: str) -> None:
        self.output_bytes += len(text.encode("utf-8"))
        if self.output_bytes > MAX_OUTPUT_BYTES:
            raise self.invalid("sse_output_too_large")

    def _append(self, target: list, text: str) -> None:
        self._count(text)
        target.append(text)

    def _signature(self, target: dict, value) -> None:
        if value is None:
            return
        if not isinstance(value, str) or not value:
            raise self.invalid("sse_invalid_signature")
        if "thought_signature" in target and target["thought_signature"] != value:
            raise self.invalid("sse_conflicting_signature")
        if "thought_signature" not in target:
            self._count(value)
            target["thought_signature"] = value

    def _tool(self, fragment) -> None:
        if not isinstance(fragment, dict):
            raise self.invalid("sse_invalid_tool_fragment")
        index = fragment.get("index")
        if type(index) is not int or not 0 <= index < 20 or fragment.get("type") not in (None, "function"):
            raise self.invalid("sse_invalid_tool_fragment")
        tool = self.tools.setdefault(index, {"id": "", "type": "function",
                                            "function": {"name": "", "arguments": ""}})
        function = fragment.get("function", {})
        if not isinstance(function, dict):
            raise self.invalid("sse_invalid_tool_fragment")
        for target, source, keys in ((tool, fragment, ("id",)), (tool["function"], function, ("name", "arguments"))):
            for key in keys:
                if source.get(key) is not None:
                    if not isinstance(source[key], str):
                        raise self.invalid("sse_invalid_tool_fragment")
                    self._count(source[key])
                    target[key] += source[key]
            self._signature(target, source.get("thought_signature"))
        extra = fragment.get("extra_content")
        if extra is not None:
            if not isinstance(extra, dict) or (extra.get("google") is not None
                                             and not isinstance(extra["google"], dict)):
                raise self.invalid("sse_invalid_signature")
            if isinstance(extra.get("google"), dict) and extra["google"].get("thought_signature") is not None:
                target = tool.setdefault("extra_content", {}).setdefault("google", {})
                self._signature(target, extra["google"]["thought_signature"])

    def finish(self) -> tuple[dict, dict]:
        if not self.eof:
            self.eof = True
            try:
                self.buffer += self.decoder.decode(b"", final=True)
            except UnicodeError as exc:
                raise self.invalid("sse_invalid_utf8") from exc
        if self.buffer or self.lines:
            raise self.invalid("sse_incomplete_event")
        if not self.done or self.finish_reason is None:
            raise self.invalid("sse_missing_terminal_frame")
        if not self.identity.get("id") or not self.identity.get("model"):
            raise self.invalid("sse_invalid_identity")
        if self.usage is None or any(type(self.usage.get(k)) is not int
                                     for k in ("prompt_tokens", "completion_tokens")):
            raise self.invalid("sse_missing_usage")
        if (bool(self.tools) != (self.finish_reason == "tool_calls")
                or sorted(self.tools) != list(range(len(self.tools)))
                or any(not t["id"] or not t["function"]["name"] or not t["function"]["arguments"]
                       for t in self.tools.values())):
            raise self.invalid("sse_tool_finish_mismatch")
        if len({t["id"] for t in self.tools.values()}) != len(self.tools):
            raise self.invalid("duplicate_tool_call_ids")
        return parse_chat_message(self.snapshot(), self.http_status, self.provider)
