"""Copy visible audit data without persisting opaque model reasoning or signatures.

Never replace the in-memory assistant message or outgoing tool history with this
projection: compatible tool protocols may require those original opaque fields.
"""
from __future__ import annotations

_OPAQUE_KEYS = {
    "reasoning", "reasoning_content", "thinking", "thought", "thoughts",
    "thought_signature", "signature", "extra_content", "encrypted_content",
}


def redact_opaque(value):
    """Return a recursive audit copy; preserve numeric usage such as reasoning_tokens."""
    if isinstance(value, dict):
        return {key: redact_opaque(item) for key, item in value.items()
                if not isinstance(key, str) or (
                    key.casefold() not in _OPAQUE_KEYS and not key.casefold().endswith("_signature"))}
    if isinstance(value, list):
        return [redact_opaque(item) for item in value]
    return value
