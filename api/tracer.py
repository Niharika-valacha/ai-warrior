"""Records what the system does, step by step, for X-ray mode (this is tracing / observability)."""
from __future__ import annotations

import contextvars
import inspect
import json
from contextlib import contextmanager
from types import ModuleType
from typing import Any, Callable, Optional

_steps: contextvars.ContextVar[Optional[list]] = contextvars.ContextVar("steps", default=None)

MAX_TEXT = 400


def trace(label: str, **values: Any) -> None:
    """Record one step: where it happened (function + line) and the values at that moment."""
    steps = _steps.get()
    if steps is None:
        return
    caller = inspect.currentframe().f_back  # type: ignore[union-attr]
    steps.append({"fn": caller.f_code.co_name, "line": caller.f_lineno, "label": label, "values": _jsonable(values)})


def capture(fn: Callable[[], Any]) -> tuple[Any, list]:
    """Run `fn` and return (its result, every step it traced)."""
    token = _steps.set([])
    try:
        result = fn()
        return _jsonable(result), _steps.get() or []
    finally:
        _steps.reset(token)


@contextmanager
def quiet():
    """Pause tracing, e.g. while an eval runs hundreds of cases."""
    token = _steps.set(None)
    try:
        yield
    finally:
        _steps.reset(token)


def sources(steps: list, module: ModuleType) -> dict:
    """Source code of every function that appears in the trace, keyed by name."""
    out = {}
    for name in dict.fromkeys(s["fn"] for s in steps):
        fn = getattr(module, name, None)
        if callable(fn):
            lines, start = inspect.getsourcelines(fn)
            out[name] = {"start": start, "code": "".join(lines)}
    return out


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        value = value.model_dump()
    data = json.loads(json.dumps(value, default=str, ensure_ascii=False))
    return _truncate(data)


def _truncate(v: Any) -> Any:
    if isinstance(v, str) and len(v) > MAX_TEXT:
        return v[:MAX_TEXT] + "…"
    if isinstance(v, list):
        return [_truncate(x) for x in v]
    if isinstance(v, dict):
        return {k: _truncate(x) for k, x in v.items()}
    return v
