"""Single-parser, one-shot terminal audit for sync/async Chat SSE bodies.

Subscribers receive separate redacted copies, never the original tool history.
No file IO or HTTP monkey patch is installed by importing this module. Transport
callers defer publication until their complete HTTP context has closed.
"""
from __future__ import annotations

import copy
import json
import logging
import math
import os
import re
import threading
from collections.abc import Callable
from pathlib import Path

import httpx

from app.llm.audit import redact_opaque
from app.llm.chat_sse import MAX_STREAM_BYTES, ChatStream, numeric_usage
from app.llm.retry import check_provider_response

KEY = "cs2_packaged_chat_sse_audit_v1"
AuditCallback = Callable[[dict, BaseException | None, bool], None]
logger = logging.getLogger(__name__)


class AuditDeliveryError(RuntimeError):
    pass


def delivery_warning(error: Exception) -> None:
    try:
        logger.warning("Compatible SSE audit delivery failed (%s); provider outcome retained.", type(error).__name__)
    except Exception:
        # Broken logging must not change a completed/provider-rejected request.
        pass


def _ledger_record(value: dict) -> dict:
    """Allowlist only accounting/protocol metadata, including a bounded profile."""
    result = {}
    for key in ("attempt_id", "model_id", "requested_model", "returned_model", "response_id", "transport",
                "transport_version", "transport_encoding", "error_type", "usage_scope", "started_at", "finished_at"):
        item = value.get(key)
        if isinstance(item, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:+/\-]{0,511}", item):
            result[key] = item
    for key in ("http_status", "input_tokens", "output_tokens", "reasoning_tokens", "cached_input_tokens"):
        item = value.get(key)
        if item is None or type(item) is int and 0 <= item <= 1_000_000_000:
            result[key] = item
    for key in ("protocol_complete", "usage_known", "dispatch_attempted", "elapsed_includes_queue"):
        if type(value.get(key)) is bool:
            result[key] = value[key]
    elapsed = value.get("elapsed_seconds")
    if type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed >= 0:
        result["elapsed_seconds"] = elapsed
    profile = value.get("profile")
    if isinstance(profile, dict):
        result["profile"] = {key: profile[key] for key in ("strict_json", "thinking")
                             if type(profile.get(key)) is bool}
        for key in ("min_output_tokens", "max_output_tokens", "context_tokens", "thinking_headroom"):
            if type(profile.get(key)) is int and 0 <= profile[key] <= 1_000_000_000:
                result["profile"][key] = profile[key]
        if profile.get("provider") in ("google", "anthropic"):
            result["profile"]["provider"] = profile["provider"]
        if profile.get("reasoning_effort") in (None, "minimal", "low", "medium", "high"):
            result["profile"]["reasoning_effort"] = profile.get("reasoning_effort")
        timeout = profile.get("min_timeout_seconds")
        if type(timeout) in (int, float) and math.isfinite(timeout) and 0 <= timeout <= 3600:
            result["profile"]["min_timeout_seconds"] = timeout
    if isinstance(value.get("reported_usage"), dict):
        result["reported_usage"] = numeric_usage(value["reported_usage"])
    return result


def jsonl_sink(path: str | Path) -> Callable[[dict], None]:
    """Opt-in POSIX JSONL sink; separate flock per append is safe across workers.

    Merely constructing the callback has no filesystem side effects. Failures
    emit only a fixed diagnostic and exception class, never the private path,
    record, exception prose or a new retryable model error.
    """
    target = Path(path)

    def append(value: dict) -> None:
        try:
            import fcntl

            encoded = (json.dumps(_ledger_record(value), ensure_ascii=False, allow_nan=False) + "\n").encode()
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(target, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(descriptor, "ab") as stream:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                stream.write(encoded)
                stream.flush()
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        except Exception as exc:
            delivery_warning(exc)
    return append


def terminal_metadata(data: dict, error: BaseException | None, complete: bool,
                      http_status: int | None = None) -> dict:
    """Chat accounting only; missing prompt/completion totals are unknown.

    Responses clients own their input/output accounting; their zero-valued
    aliases must never override a compatible Chat stream's reported totals.
    """
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    prompt, completion = usage.get("prompt_tokens"), usage.get("completion_tokens")
    known = all(type(value) is int and 0 <= value <= 1_000_000_000 for value in (prompt, completion))
    result = {"transport": "sse", "http_status": http_status, "protocol_complete": complete,
              "usage_known": known, "input_tokens": prompt if known else None,
              "output_tokens": completion if known else None,
              "usage_scope": "final" if complete else "observed_frame" if known else "unknown",
              "error_type": type(error).__name__ if error is not None else None}
    result["reported_usage"] = numeric_usage(usage)
    for field, target in (("model", "returned_model"), ("id", "response_id")):
        value = data.get(field)
        if isinstance(value, str) and len(value) <= 512:
            result[target] = value
    for details, key, target in (("completion_tokens_details", "reasoning_tokens", "reasoning_tokens"),
                                 ("prompt_tokens_details", "cached_tokens", "cached_input_tokens")):
        value = (usage.get(details) or {}).get(key) if isinstance(usage.get(details), dict) else None
        if type(value) is int and 0 <= value <= 1_000_000_000:
            result[target] = value
    return result


class State:
    def __init__(self, response: httpx.Response, provider: str):
        self.response = response
        media = response.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
        self.parser = (ChatStream(provider, response.status_code)
                       if media == "text/event-stream" and response.status_code < 400 else None)
        self.callbacks: list[AuditCallback] = []
        self.lock = threading.Lock()
        self.body_complete = response.is_stream_consumed
        self.deferred = self.finished = self.complete = False
        self.error: BaseException | None = None
        self.data: dict = {}
        self.bytes_received = 0

    def feed(self, block: bytes) -> None:
        self.bytes_received += len(block)
        if self.bytes_received > MAX_STREAM_BYTES:
            parser = self.parser or ChatStream(http_status=self.response.status_code)
            raise parser.invalid("sse_body_too_large")
        if self.parser is not None:
            self.parser.feed(block)

    def add(self, callback: AuditCallback) -> None:
        with self.lock:
            if callback in self.callbacks:
                return
            self.callbacks.append(callback)
            finished = self.finished
        if finished:
            try:
                callback(copy.deepcopy(self.data), self.error, self.complete)
            except Exception as exc:
                delivery_warning(exc)
                if self.error is None:
                    raise AuditDeliveryError("stream audit delivery failed") from None

    def finish(self, error: BaseException | None = None) -> None:
        with self.lock:
            if self.finished:
                return
            if error is not None:
                self.error = error
            if self.parser is not None:
                if self.error is None:
                    try:
                        if not self.body_complete:
                            raise self.parser.invalid("sse_missing_terminal_frame")
                        data, _ = self.parser.finish()
                        self.data = redact_opaque(data)
                        self.complete = True
                    except BaseException as exc:
                        self.error = exc
                if self.error is not None:
                    self.data = redact_opaque(self.parser.snapshot())
            self.finished = True
            callbacks = list(self.callbacks)
        failed = False
        for callback in callbacks:
            try:
                callback(copy.deepcopy(self.data), self.error, self.complete)
            except Exception as exc:
                delivery_warning(exc)
                failed = True
        # Audit failure cannot disguise a permanent provider rejection or cause
        # more paid retries. Every subscriber is notified before a safe error.
        if failed and self.error is None:
            raise AuditDeliveryError("stream audit delivery failed")


class SyncBody(httpx.SyncByteStream):
    def __init__(self, inner, state: State):
        self.inner, self.state = inner, state

    def __iter__(self):
        try:
            for block in self.inner:
                self.state.feed(block)
                yield block
            self.state.body_complete = True
        except BaseException as exc:
            self.state.error = exc
            raise

    def close(self):
        try:
            self.inner.close()
        except BaseException as exc:
            self.state.error = exc
            raise
        finally:
            if not self.state.deferred:
                self.state.finish()


class AsyncBody(httpx.AsyncByteStream):
    def __init__(self, inner, state: State):
        self.inner, self.state = inner, state

    async def __aiter__(self):
        try:
            async for block in self.inner:
                self.state.feed(block)
                yield block
            self.state.body_complete = True
        except BaseException as exc:
            self.state.error = exc
            raise

    async def aclose(self):
        try:
            await self.inner.aclose()
        except BaseException as exc:
            self.state.error = exc
            raise
        finally:
            if not self.state.deferred:
                self.state.finish()


def state_for(response: httpx.Response, provider: str | None = None) -> State:
    state = response.extensions.get(KEY)
    if state is None:
        state = State(response, provider or "google")
        response.extensions[KEY] = state
        if response.is_stream_consumed:
            try:
                state.feed(response.content)
            except BaseException as exc:
                state.error = exc
        elif isinstance(response.stream, httpx.SyncByteStream):
            response.stream = SyncBody(response.stream, state)
        else:
            response.stream = AsyncBody(response.stream, state)
    elif provider is not None and state.parser is not None:
        state.parser.provider = provider
        diagnostics = getattr(state.error, "provider_diagnostics", None)
        if isinstance(diagnostics, dict):
            diagnostics["provider"] = provider
    return state


def subscribe(response: httpx.Response, callback: AuditCallback) -> None:
    state_for(response).add(callback)


def deferred(response: httpx.Response, provider: str = "google") -> State:
    state = state_for(response, provider)
    state.deferred = True
    return state


def publish(response: httpx.Response, error: BaseException | None = None) -> None:
    state = state_for(response)
    state.finish(error)


def _json_data(response: httpx.Response) -> dict:
    try:
        value = response.json()
    except (ValueError, RuntimeError, RecursionError):
        return {}
    if not isinstance(value, dict):
        return {}
    # Error bodies can echo credentials in provider prose. Keep accounting only.
    if response.status_code >= 400:
        try:
            return {"usage": numeric_usage(value.get("usage") or {})}
        except ValueError:
            return {"usage": {}}
    return redact_opaque(value)


def record_json(response: httpx.Response) -> None:
    state = state_for(response)
    state.data = _json_data(response)
    state.complete = response.status_code < 400


def _encoding_error(response: httpx.Response, state: State):
    if response.headers.get("content-encoding", "").strip().casefold() in ("", "identity"):
        return None
    if response.status_code >= 400:
        try:
            check_provider_response(httpx.Response(response.status_code, json={}))
        except Exception as exc:
            return exc
    return (state.parser or ChatStream(http_status=response.status_code)).invalid("sse_unsupported_encoding")


def observe_sync(response: httpx.Response, callback: AuditCallback) -> None:
    state = state_for(response)
    state.add(callback)
    if (error := _encoding_error(response, state)) is not None:
        state.finish(error)
        return
    if state.parser is None:
        state.deferred = True
        try:
            response.read()
            record_json(response)
        except BaseException as exc:
            state.error = exc
            raise
        finally:
            state.finish()
    elif response.is_stream_consumed:
        state.finish()


async def observe_async(response: httpx.Response, callback: AuditCallback) -> None:
    state = state_for(response)
    state.add(callback)
    if (error := _encoding_error(response, state)) is not None:
        state.finish(error)
        return
    if state.parser is None:
        state.deferred = True
        try:
            await response.aread()
            record_json(response)
        except BaseException as exc:
            state.error = exc
            raise
        finally:
            state.finish()
    elif response.is_stream_consumed:
        state.finish()
