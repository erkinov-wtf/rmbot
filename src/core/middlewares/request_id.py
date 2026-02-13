from __future__ import annotations

import uuid


class RequestIDMiddleware:
    """
    Ensures every request has a correlation ID and echoes it in response headers.
    """

    REQUEST_META_HEADER = "HTTP_X_REQUEST_ID"
    RESPONSE_HEADER = "X-Request-ID"
    REQUEST_ATTR = "request_id"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming_request_id = request.META.get(self.REQUEST_META_HEADER)
        request_id = self._normalize_request_id(incoming_request_id)
        setattr(request, self.REQUEST_ATTR, request_id)

        response = self.get_response(request)
        response[self.RESPONSE_HEADER] = request_id
        return response

    @staticmethod
    def _normalize_request_id(raw_value) -> str:
        if isinstance(raw_value, str):
            value = raw_value.strip()
            if value:
                return value[:128]
        return uuid.uuid4().hex
