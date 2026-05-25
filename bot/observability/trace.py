"""
UUIDv7 (time-sortable) trace IDs + structlog context vars.
Every `leader_trade_detected` event creates a new trace_id that threads
through all downstream events — detection → signal → order → fill.
"""
from __future__ import annotations

import time
import uuid
from contextvars import ContextVar

import structlog

_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
_span_id_var: ContextVar[str] = ContextVar("span_id", default="")


def _uuid7() -> str:
    """Generate a UUIDv7: 48-bit ms timestamp + random. Time-sortable."""
    ms = int(time.time() * 1000)
    rand = uuid.uuid4().int & ((1 << 74) - 1)
    # Layout: 48b unix_ms | 4b ver=7 | 12b rand_a | 2b var | 62b rand_b
    val = (ms << 80) | (0x7 << 76) | ((rand >> 62) << 64) | (0b10 << 62) | (rand & ((1 << 62) - 1))
    return str(uuid.UUID(int=val))


def new_trace() -> str:
    tid = _uuid7()
    _trace_id_var.set(tid)
    _span_id_var.set(_uuid7())
    return tid


def new_span() -> str:
    sid = _uuid7()
    _span_id_var.set(sid)
    return sid


def current_trace() -> str:
    return _trace_id_var.get()


def current_span() -> str:
    return _span_id_var.get()


def inject_trace_context(logger, method_name, event_dict):
    """structlog processor: adds trace_id and span_id to every log record."""
    tid = _trace_id_var.get()
    sid = _span_id_var.get()
    if tid:
        event_dict["trace_id"] = tid
    if sid:
        event_dict["span_id"] = sid
    return event_dict
