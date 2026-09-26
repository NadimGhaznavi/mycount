"""Keep request content out of Gunicorn diagnostics."""

import sys
import traceback

from gunicorn.glogging import Logger


class ServiceLogger(Logger):
    def warning(self, message, *args, **kwargs):
        # Gunicorn includes peer addresses and raw headers in parser warnings.
        if isinstance(message, str) and message.startswith("Invalid request from ip="):
            message, args = "Rejected malformed HTTP request.", ()
        super().warning(message, *args, **kwargs)

    def exception(self, message, *args, **kwargs):
        # Preserve error type and stack locations, never exception values or URLs.
        error_type, _, stack = sys.exc_info()
        locations = "\n".join(
            f"  {frame.filename}:{frame.lineno} in {frame.name}"
            for frame in traceback.extract_tb(stack)
        )
        self.error("Unhandled %s\n%s", error_type.__name__ if error_type else "error", locations)
