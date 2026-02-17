import logging
import queue
import threading
import traceback
from collections.abc import Mapping
from html import escape

import requests


class TelegramErrorHandler(logging.Handler):
    """
    A logging handler that sends error logs to a Telegram chat via a bot.
    It uses a background thread and a queue to avoid blocking the main thread.
    """

    def __init__(self, bot_token, chat_id, level=logging.ERROR, max_queue=100):
        super().__init__(level)
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        self.chat_id = chat_id
        self.queue = queue.Queue(maxsize=max_queue)

        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()

    def emit(self, record):
        try:
            safe_record = logging.makeLogRecord(record.__dict__.copy())
            safe_record.exc_info = None
            safe_record.exc_text = None
            safe_record.msg = escape(str(record.getMessage()), quote=False)
            safe_record.args = ()
            safe_record.user = escape(
                str(getattr(record, "user", "Unknown")), quote=False
            )
            safe_record.method = escape(
                str(getattr(record, "method", "-")), quote=False
            )
            safe_record.path = escape(str(getattr(record, "path", "-")), quote=False)
            safe_record.ip = escape(str(getattr(record, "ip", "-")), quote=False)
            safe_record.request_id = escape(
                str(getattr(record, "request_id", "-")), quote=False
            )
            safe_record.traceback = escape(
                str(getattr(record, "traceback", "No traceback")), quote=False
            )

            msg = self.format(safe_record)

            self.queue.put_nowait(msg)
        except queue.Full:
            pass  # drop or count dropped messages

    def _worker(self):
        session = requests.Session()
        while True:
            msg = self.queue.get()
            try:
                session.post(
                    self.api_url,
                    json={
                        "chat_id": self.chat_id,
                        "text": msg[:4000],
                        "parse_mode": "HTML",
                    },
                    timeout=5,
                )
            except Exception:
                pass
            finally:
                self.queue.task_done()


class RequestContextFilter(logging.Filter):
    """
    Adds request/user/IP/path/method/request_id + traceback info to log records.
    """

    def filter(self, record):
        request = getattr(record, "request", None)

        if self._is_request_context(request):
            user = getattr(request, "user", None)
            record.user = getattr(user, "username", "Anonymous")
            record.method = getattr(request, "method", "-")
            record.path = getattr(request, "path", "-")
            meta = getattr(request, "META", {})
            record.ip = (
                meta.get("REMOTE_ADDR", "-") if isinstance(meta, Mapping) else "-"
            )
            record.request_id = getattr(request, "request_id", "-")
        else:
            record.user = "Unknown"
            record.method = "-"
            record.path = "-"
            record.ip = "-"
            record.request_id = "-"

        if record.exc_info:
            exc_type, exc_value, exc_tb = record.exc_info
            record.traceback = "".join(
                traceback.format_exception(exc_type, exc_value, exc_tb)
            )
        else:
            record.traceback = "No traceback"

        return True

    @staticmethod
    def _is_request_context(request) -> bool:
        """
        Guard against non-HTTP objects (for example socket instances in devserver logs).
        """
        return (
            request is not None
            and hasattr(request, "method")
            and hasattr(request, "path")
            and hasattr(request, "META")
        )
