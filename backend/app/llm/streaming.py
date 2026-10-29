"""Opt-in compatible Chat SSE transport; candidate, default off in Settings.

Model payloads are inherited. A 300-second HTTPX read timeout is an idle-read
timeout, not a total wall deadline. The entire stream context remains on the
interrupt worker when its caller stops waiting; upstream work can continue.
Only uncompressed UTF-8 SSE is accepted: request identity encoding explicitly
so the single bounded parser and HTTP error reader see the actual wire bytes.
"""
from __future__ import annotations

import ssl
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

import certifi
import httpx

from app.llm import interrupt, stream_audit
from app.llm.audit import redact_opaque
from app.llm.chat_sse import SSE_VERSION
from app.llm.compatible import CompatibleChatClient
from app.llm.diagnostics import output_error
from app.llm.retry import LLMTimeout, LLMUnavailable, check_provider_response


class StreamingCompatibleChatClient(CompatibleChatClient):
    transport = "sse"
    transport_version = SSE_VERSION

    def __init__(self, *args, attempt_observer: Callable[[dict], None] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.attempt_observer = attempt_observer

    def _post(self, payload: dict) -> tuple[dict, dict, int, int]:
        started = time.perf_counter()
        started_at = datetime.now(timezone.utc).isoformat()
        attempt_id = uuid.uuid4().hex
        trace = {"dispatch_attempted": False}
        streamed = {**payload, "stream": True, "stream_options": {"include_usage": True}}

        def accounting(data, error, complete, status=None):
            record = stream_audit.terminal_metadata(data, error, complete, status)
            record.update(requested_model=self.model, transport_version=self.transport_version,
                          profile=self.profile_metadata, model_id=self.model_id, attempt_id=attempt_id,
                          started_at=started_at, finished_at=datetime.now(timezone.utc).isoformat(),
                          elapsed_seconds=round(time.perf_counter() - started, 6),
                          dispatch_attempted=trace["dispatch_attempted"], elapsed_includes_queue=True,
                          transport_encoding="identity")
            return record

        def receive():
            response, state = None, None
            try:
                with httpx.Client(timeout=self.timeout,
                                  verify=ssl.create_default_context(cafile=certifi.where())) as client:
                    # This marks entering the HTTP API, not proof of delivery
                    # through a deployment's network/capacity guard or socket.
                    trace["dispatch_attempted"] = True
                    with client.stream("POST", f"{self.base_url}/chat/completions",
                                       headers={"Authorization": f"Bearer {self.api_key}",
                                                "Accept-Encoding": "identity"}, json=streamed) as response:
                        state = stream_audit.deferred(response, self.provider)
                        if self.attempt_observer is not None:
                            def observe(data, error, complete):
                                self.attempt_observer(accounting(data, error, complete, response.status_code))
                            state.add(observe)
                        encoding = response.headers.get("content-encoding", "").strip().casefold()
                        if encoding not in ("", "identity"):
                            if response.status_code >= 400:
                                check_provider_response(httpx.Response(response.status_code, json={}))
                            raise output_error("sse_unsupported_encoding", None, response.status_code, self.provider)
                        if response.status_code >= 400:
                            try:
                                response.read()  # bounded by the body's shared audit wrapper
                            except Exception:
                                # A broken error body must not turn known permanent
                                # rejection into a retryable read/protocol failure.
                                if 400 <= response.status_code < 500 and response.status_code not in (408, 429):
                                    check_provider_response(httpx.Response(response.status_code, json={}))
                                raise
                            stream_audit.record_json(response)
                            check_provider_response(response)
                        if state.parser is None:
                            raise output_error("sse_non_sse_response", None, response.status_code, self.provider)
                        if state.error is not None:
                            raise state.error
                        # One strict parser, shared by the client and both audit subscribers.
                        if not response.is_stream_consumed:
                            for _ in response.iter_bytes(chunk_size=65_536):
                                pass
                        data, message = state.parser.finish()
            except BaseException as exc:
                if response is not None:
                    stream_audit.publish(response, error=exc)
                    if state is not None:
                        exc.stream_audit = accounting(state.data, exc, False, response.status_code)
                        if not getattr(exc, "provider_diagnostics", None):
                            exc.provider_diagnostics = output_error(
                                "sse_request_failed", state.data, response.status_code, self.provider
                            ).provider_diagnostics
                elif self.attempt_observer is not None:
                    try:
                        self.attempt_observer(accounting({}, exc, False))
                    except Exception as observer_error:
                        stream_audit.delivery_warning(observer_error)
                raise
            stream_audit.publish(response)
            return data, message, response.status_code

        try:
            data, message, status = interrupt.call(receive)
        except httpx.TimeoutException as exc:
            error = LLMTimeout("provider SSE request timed out")
            error.stream_audit = getattr(exc, "stream_audit", None)
            error.provider_diagnostics = getattr(exc, "provider_diagnostics", None)
            raise error from exc
        except httpx.HTTPError as exc:
            error = LLMUnavailable("provider SSE transport failed")
            error.stream_audit = getattr(exc, "stream_audit", None)
            error.provider_diagnostics = getattr(exc, "provider_diagnostics", None)
            raise error from exc
        if self.response_observer is not None:
            self.response_observer(redact_opaque(data))
        return data, message, status, int((time.perf_counter() - started) * 1000)
