"""Cross-process relay model capacity gate; importing performs no network I/O.

Explicitly call ``install()`` in every runner process. The default directory is
shared across the experiment; queued time is additional wall time and can use a
caller's existing deadline. Payloads, provider timeouts and responses are untouched.
"""
from __future__ import annotations

import asyncio
import fcntl
import json
import os
import threading
import time
import uuid
from pathlib import Path

import httpx

DEFAULT_STATE_DIR = Path(__file__).resolve().parents[1] / "data" / ".relay-capacity"
DEFAULT_HOSTS = ("www.yunzhuhub.com", "yunzhuhub.com")
DEFAULT_PATHS = ("/v1/responses", "/v1/chat/completions", "/v1/messages")
_REGISTRY = "_cs2_relay_capacity_installation_v1"
_INSTALL_LOCK = "_cs2_relay_capacity_install_lock_v1"
if not hasattr(httpx, _INSTALL_LOCK):
    setattr(httpx, _INSTALL_LOCK, threading.Lock())


class CapacityGate:
    def __init__(self, state_dir, cooldown_seconds, poll_seconds, hosts, paths):
        self.state_dir = Path(state_dir).resolve()
        self.cooldown_seconds = float(cooldown_seconds)
        self.poll_seconds = float(poll_seconds)
        if not 0 <= self.cooldown_seconds <= 3600 or not 0.001 <= self.poll_seconds <= 10:
            raise ValueError("Invalid capacity cooldown/poll duration")
        self.hosts = tuple(sorted({str(h).casefold().rstrip(".") for h in hosts}))
        self.paths = tuple(sorted({str(p).rstrip("/") for p in paths}))
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock_path = self.state_dir / "capacity.lock"
        self.cooldown_path = self.state_dir / "cooldown.json"
        self.audit_path = self.state_dir / "audit.jsonl"
        self.active = True
        self.original_sync = self.original_async = None
        self.sync_wrapper = self.async_wrapper = None

    def configuration(self):
        return {"version": "relay-capacity-1", "capacity": 1, "state_dir": str(self.state_dir),
                "cooldown_seconds": self.cooldown_seconds, "poll_seconds": self.poll_seconds,
                "hosts": list(self.hosts), "model_post_paths": list(self.paths),
                "queue_wait_affects_existing_deadlines": True,
                "stream_release": "body_complete_or_closed", "payload_or_timeout_modified": False}

    def matches(self, request):
        return (request.method == "POST" and request.url.host.casefold().rstrip(".") in self.hosts
                and request.url.path.rstrip("/") in self.paths)

    def _audit(self, event, **facts):
        # No URL, query string, headers, request/response body or exception prose.
        row = {"at": time.time(), "pid": os.getpid(), "event": event, **facts}
        fd = os.open(self.audit_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            data = (json.dumps(row, sort_keys=True) + "\n").encode()
            with os.fdopen(fd, "ab", closefd=False) as stream:
                stream.write(data)
                stream.flush()
        finally:
            os.close(fd)

    def _remaining_cooldown(self):
        if not self.cooldown_path.exists():
            return 0.0
        state = json.loads(self.cooldown_path.read_text())
        not_before = state.get("not_before")
        if type(not_before) not in (int, float) or not 0 <= not_before < float("inf"):
            raise RuntimeError("Invalid shared relay cooldown state; refusing model request")
        return max(0.0, not_before - time.time())

    def _extend_cooldown(self, reason):
        # Caller owns capacity.lock. Atomic replacement also keeps readers fail-closed.
        not_before = time.time() + self.cooldown_seconds
        if self.cooldown_path.exists():
            not_before = max(not_before, time.time() + self._remaining_cooldown())
        temporary = self.state_dir / (".cooldown-" + uuid.uuid4().hex)
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump({"not_before": not_before, "reason": reason}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.cooldown_path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return not_before

    def _try_acquire(self, fd):
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False, self.poll_seconds, False
        try:
            remaining = self._remaining_cooldown()
        except BaseException:
            fcntl.flock(fd, fcntl.LOCK_UN)
            raise
        if remaining:
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False, min(remaining, self.poll_seconds), True
        return True, 0.0, False

    def acquire(self):
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        queued = time.monotonic()
        cooldown_wait = 0.0
        try:
            while True:
                acquired, delay, cooling = self._try_acquire(fd)
                if acquired:
                    return _Lease(self, fd, queued, cooldown_wait)
                start = time.monotonic()
                time.sleep(delay)
                if cooling:
                    cooldown_wait += time.monotonic() - start
        except BaseException:
            os.close(fd)
            raise

    async def acquire_async(self):
        # Do not use to_thread: a cancelled waiter must never acquire a forgotten lock.
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        queued = time.monotonic()
        cooldown_wait = 0.0
        try:
            while True:
                acquired, delay, cooling = self._try_acquire(fd)
                if acquired:
                    return _Lease(self, fd, queued, cooldown_wait)
                start = time.monotonic()
                await asyncio.sleep(delay)
                if cooling:
                    cooldown_wait += time.monotonic() - start
        except BaseException:
            os.close(fd)
            raise

    def restore(self):
        """Deactivate this layer without overwriting any subsequently installed guard."""
        with getattr(httpx, _INSTALL_LOCK):
            self.active = False
            if httpx.Client.send is self.sync_wrapper:
                httpx.Client.send = self.original_sync
            if httpx.AsyncClient.send is self.async_wrapper:
                httpx.AsyncClient.send = self.original_async
            if getattr(httpx, _REGISTRY, None) is self:
                delattr(httpx, _REGISTRY)


class _Lease:
    def __init__(self, gate, fd, queued, cooldown_wait):
        self.gate, self.fd = gate, fd
        self.queued, self.started = queued, time.monotonic()
        self.request_id = uuid.uuid4().hex
        self.status = None
        self._finished = False
        self._finish_lock = threading.Lock()
        gate._audit("request_started", request_id=self.request_id,
                    queue_wait_seconds=self.started - queued, cooldown_wait_seconds=cooldown_wait)

    def finish(self, error=None, *, body_complete=True, close_error=None):
        with self._finish_lock:
            if self._finished:
                return
            self._finished = True
            errors = (error, close_error)
            reason = ("timeout" if any(isinstance(e, httpx.TimeoutException) for e in errors)
                      else "cancelled_after_dispatch" if any(isinstance(e, asyncio.CancelledError) for e in errors)
                      else "stream_abandoned" if any(isinstance(e, GeneratorExit) for e in errors)
                      else f"http_{self.status}" if self.status in {429, 524}
                      else "stream_closed_early" if error is None and not body_complete else None)
            try:
                not_before = self.gate._extend_cooldown(reason) if reason else None
                self.gate._audit("request_finished", request_id=self.request_id,
                                 http_status=self.status, error_type=type(error).__name__ if error else None,
                                 close_error_type=type(close_error).__name__ if close_error else None,
                                 body_complete=body_complete, network_elapsed_seconds=time.monotonic()-self.started,
                                 total_elapsed_seconds=time.monotonic()-self.queued,
                                 cooldown_reason=reason, not_before=not_before)
            finally:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
                os.close(self.fd)


class _SyncBody(httpx.SyncByteStream):
    def __init__(self, stream, lease):
        self.stream, self.lease = stream, lease

    def __iter__(self):
        error = None
        close_error = None
        complete = False
        try:
            yield from self.stream
            complete = True
        except BaseException as exc:
            error = exc
            raise
        finally:
            try:
                self.stream.close()
            except BaseException as exc:
                close_error = exc
                if error is None:
                    error = exc
                    raise
            finally:
                self.lease.finish(error, body_complete=complete, close_error=close_error)

    def close(self):
        error = None
        try:
            self.stream.close()
        except BaseException as exc:
            error = exc
            raise
        finally:
            self.lease.finish(error, body_complete=False)


class _AsyncBody(httpx.AsyncByteStream):
    def __init__(self, stream, lease):
        self.stream, self.lease = stream, lease

    async def __aiter__(self):
        error = None
        close_error = None
        complete = False
        try:
            async for chunk in self.stream:
                yield chunk
            complete = True
        except BaseException as exc:
            error = exc
            raise
        finally:
            try:
                await self.stream.aclose()
            except BaseException as exc:
                close_error = exc
                if error is None:
                    error = exc
                    raise
            finally:
                self.lease.finish(error, body_complete=complete, close_error=close_error)

    async def aclose(self):
        error = None
        try:
            await self.stream.aclose()
        except BaseException as exc:
            error = exc
            raise
        finally:
            self.lease.finish(error, body_complete=False)


def install(*, state_dir=DEFAULT_STATE_DIR, cooldown_seconds=150, poll_seconds=0.1,
            hosts=DEFAULT_HOSTS, paths=DEFAULT_PATHS):
    """Install once per process; all runners must use the same state directory.

    Also cool down when an already-dispatched async request is cancelled, because
    cancellation need not cancel upstream work. Closing an incomplete streamed body
    also cools down for this reason. Cancellation while queued dispatches nothing
    and leaves no capacity lease. No automatic model retries are introduced.
    """
    with getattr(httpx, _INSTALL_LOCK):
        candidate = CapacityGate(state_dir, cooldown_seconds, poll_seconds, hosts, paths)
        existing = getattr(httpx, _REGISTRY, None)
        if existing is not None and existing.active:
            if existing.configuration() != candidate.configuration():
                raise RuntimeError("Relay capacity gate already installed with different configuration")
            return existing
        gate = candidate
        gate.original_sync, gate.original_async = httpx.Client.send, httpx.AsyncClient.send

        def sync_send(client, request, *args, **kwargs):
            if not gate.active or not gate.matches(request):
                return gate.original_sync(client, request, *args, **kwargs)
            lease = gate.acquire()
            try:
                response = gate.original_sync(client, request, *args, **kwargs)
                lease.status = response.status_code
                if response.is_closed:
                    lease.finish()
                else:
                    response.stream = _SyncBody(response.stream, lease)
                return response
            except BaseException as exc:
                lease.finish(exc, body_complete=False)
                raise

        async def async_send(client, request, *args, **kwargs):
            if not gate.active or not gate.matches(request):
                return await gate.original_async(client, request, *args, **kwargs)
            lease = await gate.acquire_async()
            try:
                response = await gate.original_async(client, request, *args, **kwargs)
                lease.status = response.status_code
                if response.is_closed:
                    lease.finish()
                else:
                    response.stream = _AsyncBody(response.stream, lease)
                return response
            except BaseException as exc:
                lease.finish(exc, body_complete=False)
                raise

        gate.sync_wrapper, gate.async_wrapper = sync_send, async_send
        httpx.Client.send, httpx.AsyncClient.send = sync_send, async_send
        setattr(httpx, _REGISTRY, gate)
        gate._audit("installed", configuration=gate.configuration())
        return gate
