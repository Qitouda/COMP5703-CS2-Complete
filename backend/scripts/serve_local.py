"""Portable launcher for the existing single-capacity local relay runtime.

Run from any directory. Reads backend/.env without replacing process overrides;
normal ``make run`` remains available without the relay capacity layer.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=BACKEND / ".env")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--check", action="store_true",
                        help="Print non-secret configuration without starting a service or making network requests.")
    args = parser.parse_args(argv)
    env_file = args.env_file.resolve()
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))

    from dotenv import load_dotenv

    load_dotenv(env_file, override=False)
    from app.config import get_settings

    settings = get_settings()
    default_state_dir = Path(settings.upload_dir).parent / ".relay-capacity"
    state_dir = Path(os.environ.get("RELAY_CAPACITY_STATE_DIR", str(default_state_dir)))
    cooldown = float(os.environ.get("RELAY_COOLDOWN_SECONDS", "150"))
    if not 0 <= cooldown <= 3600:
        raise ValueError("RELAY_COOLDOWN_SECONDS must be between 0 and 3600.")
    if args.check:
        print(json.dumps({
            "llm_provider": settings.llm_provider,
            "parser_provider": settings.parser_provider,
            "llm_timeout_seconds": settings.llm_timeout_seconds,
            "credibility_workers": settings.credibility_workers,
            "anthropic_chat_transport": settings.anthropic_chat_transport,
            "gemini_chat_transport": settings.gemini_chat_transport,
            "gemini_model": settings.gemini_model,
            "gemini_reasoning_effort": settings.gemini_reasoning_effort,
            "gemini_thinking_headroom": settings.gemini_thinking_headroom,
            "relay_capacity": 1,
            "relay_cooldown_seconds": cooldown,
        }, indent=2))
        return

    from app.llm.network import install_network_guard
    from scripts.relay_capacity import install

    install_network_guard()
    install(state_dir=state_dir, cooldown_seconds=cooldown)
    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
