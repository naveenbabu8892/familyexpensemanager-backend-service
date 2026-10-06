import logging
import sys
from app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """Custom formatter providing structured log messages."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z")
        log_entry = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include extra fields if available
        for key in ("request_id", "method", "path", "status_code", "duration_ms", "client_ip"):
            if hasattr(record, key):
                log_entry[key] = getattr(record, key)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Standard structured string format
        parts = [f"[{log_entry['timestamp']}]", f"[{log_entry['level']}]", f"[{log_entry['logger']}]:", log_entry['message']]
        context = {k: v for k, v in log_entry.items() if k not in ("timestamp", "level", "logger", "message", "exception")}
        if context:
            parts.append(f"| context={context}")
        if "exception" in log_entry:
            parts.append(f"\n{log_entry['exception']}")

        return " ".join(parts)


def setup_logging() -> None:
    """Configure application-wide structured logging."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if re-initialized
    if not root_logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(console_handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(StructuredFormatter())

    # Quiet overly chatty third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


logger = logging.getLogger("app")
