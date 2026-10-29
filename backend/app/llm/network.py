"""Explicit host denylist checked before transport, including redirect hops."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import httpx

DENYLIST_PATH = Path(__file__).resolve().parents[2] / "config" / "network-denylist.json"


@lru_cache
def load_denied_hosts() -> tuple[str, ...]:
    data = json.loads(DENYLIST_PATH.read_text())
    hosts = data.get("denied_hosts")
    if (not isinstance(hosts, list) or not hosts or any(
            not isinstance(host, str) or not host or "/" in host or ":" in host for host in hosts)):
        raise ValueError("Invalid network denylist; refusing model transport")
    return tuple(host.casefold().rstrip(".") for host in hosts)


def check_target(url) -> None:
    host = (httpx.URL(url).host or "").casefold().rstrip(".")
    if any(host == denied or host.endswith("." + denied) for denied in load_denied_hosts()):
        raise RuntimeError("Requests to the disabled model provider are forbidden.")


def install_network_guard():
    """Wrap both public sends and each redirect hop; return a scoped restorer."""
    originals = (httpx.Client.send, httpx.AsyncClient.send,
                 httpx.Client._send_single_request, httpx.AsyncClient._send_single_request)
    active = True

    def send(client, request, *args, **kwargs):
        if active:
            check_target(request.url)
        return originals[0](client, request, *args, **kwargs)

    async def async_send(client, request, *args, **kwargs):
        if active:
            check_target(request.url)
        return await originals[1](client, request, *args, **kwargs)

    def single(client, request):
        if active:
            check_target(request.url)
        return originals[2](client, request)

    async def async_single(client, request):
        if active:
            check_target(request.url)
        return await originals[3](client, request)

    httpx.Client.send, httpx.AsyncClient.send = send, async_send
    httpx.Client._send_single_request, httpx.AsyncClient._send_single_request = single, async_single

    def restore():
        nonlocal active
        active = False
        for owner, name, wrapper, original in (
                (httpx.Client, "send", send, originals[0]),
                (httpx.AsyncClient, "send", async_send, originals[1]),
                (httpx.Client, "_send_single_request", single, originals[2]),
                (httpx.AsyncClient, "_send_single_request", async_single, originals[3])):
            if getattr(owner, name) is wrapper:
                setattr(owner, name, original)

    return restore
