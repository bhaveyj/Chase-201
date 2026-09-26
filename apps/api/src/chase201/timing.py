from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter

request_timings: ContextVar[dict[str, float] | None] = ContextVar("request_timings", default=None)


@contextmanager
def timed(name: str) -> Iterator[None]:
    started = perf_counter()
    try:
        yield
    finally:
        timings = request_timings.get()
        if timings is not None:
            timings[name] = timings.get(name, 0.0) + (perf_counter() - started) * 1000
