import logging
import time
import uuid

logger = logging.getLogger(__name__)


def request_id():
    return uuid.uuid4().hex


class RequestTimer:
    def __enter__(self):
        self.started_at = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.latency_ms = round((time.perf_counter() - self.started_at) * 1000, 2)


def record_request(details):
    logger.info('LLM gateway request: %s', details)