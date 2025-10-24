import logging
import logging.config
import os
import sys
import contextvars
from settings import settings

# Context vars untuk memperkaya log
request_id_ctx = contextvars.ContextVar("request_id", default="-")
user_id_ctx = contextvars.ContextVar("user_id", default="-")

class ContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get("-")
        record.user_id = user_id_ctx.get("-")
        return True

def setup_logging(level: str | None = None) -> None:
    log_level = (level or settings.LOG_LEVEL or os.getenv("LOG_LEVEL") or "INFO").upper()
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "context": {"()": ContextFilter}
        },
        "formatters": {
            "default": {
                "format": "[%(asctime)s] [%(levelname)s] [req:%(request_id)s usr:%(user_id)s] %(name)s - %(message)s"
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "stream": sys.stdout,
                "filters": ["context"],
                "formatter": "default",
            },
        },
        "root": {"level": log_level, "handlers": ["console"]},
        "loggers": {
            # Samakan format uvicorn; hindari duplikasi access log
            "uvicorn": {"level": log_level, "handlers": ["console"], "propagate": False},
            "uvicorn.error": {"level": log_level, "handlers": ["console"], "propagate": False},
            "uvicorn.access": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        },
    }
    logging.config.dictConfig(config)

def get_logger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name or "app")