"""
structlog configuration: structured JSON to stdout + daily-rotating file + SQLite events table.
"""
from __future__ import annotations

import logging
import logging.handlers
import re
from pathlib import Path

import structlog

from bot.observability.trace import inject_trace_context

_REDACT_PATTERN = re.compile(
    r"(private_key|key|secret|passphrase|mnemonic|api_key)", re.IGNORECASE
)
_INITIALIZED = False


def _redact(logger, method_name, event_dict: dict) -> dict:
    """Strip sensitive substrings from log payloads."""
    for k in list(event_dict.keys()):
        if _REDACT_PATTERN.search(k):
            event_dict[k] = "***REDACTED***"
    return event_dict


def configure_logging(log_dir: Path | None = None, level: str = "INFO") -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_dir / "bot.log",
            when="midnight",
            utc=True,
            backupCount=30,
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        handlers=handlers,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            inject_trace_context,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.ExceptionRenderer(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)
