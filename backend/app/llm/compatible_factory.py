"""One compatible-provider selection for the product and offline-prepared CLI."""
from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from typing import Any

from app.config import Settings
from app.llm.chat_sse import SSE_VERSION
from app.llm.compatible import PROFILES, CompatibleChatClient, ModelProfile

_PREFIXES = {"anthropic": "anthropic", "google": "gemini"}


@dataclass(frozen=True)
class CompatibleSelection:
    profile: ModelProfile
    transport: str
    timeout_seconds: float
    sse_audit_enabled: bool

    def public_metadata(self) -> dict[str, Any]:
        return {"profile": asdict(self.profile), "transport": self.transport,
                "transport_version": (SSE_VERSION if self.transport == "sse"
                                      else CompatibleChatClient.transport_version),
                "timeout_seconds": self.timeout_seconds, "sse_audit_enabled": self.sse_audit_enabled,
                "timeout_semantics": "httpx_idle_read_not_total_wall_deadline"}


def resolve_compatible(settings: Settings, provider: str, *, timeout: float | None = None) -> CompatibleSelection:
    if provider not in _PREFIXES:
        raise ValueError("Compatible provider must be anthropic or google.")
    profile = (PROFILES["anthropic"] if provider == "anthropic" else replace(
        PROFILES["google"], reasoning_effort=settings.gemini_reasoning_effort,
        thinking_headroom=settings.gemini_thinking_headroom))
    transport = getattr(settings, _PREFIXES[provider] + "_chat_transport")
    if transport not in {"json", "sse"}:
        raise ValueError("Compatible transport must be json or sse.")
    requested_timeout = float(settings.llm_timeout_seconds if timeout is None else timeout)
    if not math.isfinite(requested_timeout) or requested_timeout <= 0:
        raise ValueError("Compatible timeout must be finite and positive.")
    return CompatibleSelection(profile, transport, max(requested_timeout, profile.min_timeout_seconds),
                               bool(transport == "sse" and settings.compatible_sse_audit_path.strip()))


def build_compatible_client(settings: Settings, provider: str, *, model_id: str, model: str | None = None,
                            base_url: str | None = None, timeout: float | None = None,
                            response_observer: Callable[[dict[str, Any]], None] | None = None) -> CompatibleChatClient:
    selected = resolve_compatible(settings, provider, timeout=timeout)
    prefix = _PREFIXES[provider]
    client_type, options = CompatibleChatClient, {}
    if selected.transport == "sse":
        from app.llm.stream_audit import jsonl_sink
        from app.llm.streaming import StreamingCompatibleChatClient

        client_type = StreamingCompatibleChatClient
        if selected.sse_audit_enabled:
            options["attempt_observer"] = jsonl_sink(settings.compatible_sse_audit_path)
    return client_type(model_id=model_id, profile=selected.profile,
        api_key=getattr(settings, prefix + "_api_key"), base_url=base_url or getattr(settings, prefix + "_base_url"),
        model=model or getattr(settings, prefix + "_model"), timeout=selected.timeout_seconds,
        response_observer=response_observer, **options)
