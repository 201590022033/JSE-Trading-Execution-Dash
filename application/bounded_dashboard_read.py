"""Bound concurrent retained reads and reuse briefly completed responses."""
from concurrent.futures import ThreadPoolExecutor, wait
from functools import wraps
from threading import RLock
from time import monotonic

from flask import copy_current_request_context, current_app, jsonify, request


def retained_read(*, workers=2, wait_seconds=8, ttl=60):
    """One in-flight task per query. No unbounded worker queue or persistent cache."""
    pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='dashboard-read')
    lock = RLock()
    pending, cached = {}, {}

    def remember(key, future):
        with lock:
            del pending[key]
            if not future.exception():
                result = future.result()
                if result[1] == 200:
                    if len(cached) >= 32:
                        del cached[next(iter(cached))]
                    cached[key] = (monotonic() + ttl, result)

    def decorate(view):
        @wraps(view)
        def read(*args, **kwargs):
            key = (current_app._get_current_object(), request.path, request.query_string)
            with lock:
                now = monotonic()
                for old_key in tuple(cached):
                    if cached[old_key][0] <= now:
                        del cached[old_key]
                if key in cached:
                    return cached[key][1]
                future = pending.get(key)
                if future is None and len(pending) < workers:
                    @copy_current_request_context
                    def load():
                        result = current_app.make_response(view(*args, **kwargs))
                        return result.get_data(), result.status_code, list(result.headers.items())

                    future = pool.submit(load)
                    pending[key] = future
                    future.add_done_callback(lambda completed: remember(key, completed))
            if future is None or not wait((future,), timeout=wait_seconds).done:
                return jsonify(state='READ_TIMED_OUT'), 503
            return future.result()
        return read
    return decorate
