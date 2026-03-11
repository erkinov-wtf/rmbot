from django.db.models.deletion import ProtectedError
from django.utils.translation import gettext as translate
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST
from rest_framework.views import exception_handler


class DomainValidationError(Exception):
    """
    Raised when business logic validation fails.
    Caught by custom_exception_handler and returns HTTP 400 Bad Request.
    """

    pass


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _translate_text(value: object) -> str:
    normalized = _normalize_text(value)
    if not normalized:
        return ""
    return str(translate(normalized))


def _collect_error_messages(payload: object) -> list[str]:
    if isinstance(payload, dict):
        messages: list[str] = []
        for field, raw_value in payload.items():
            nested_messages = _collect_error_messages(raw_value)
            if not nested_messages:
                continue
            if field in {"detail", "non_field_errors"}:
                messages.extend(nested_messages)
                continue
            field_label = _translate_text(field)
            if not field_label:
                messages.extend(nested_messages)
                continue
            messages.extend(f"{field_label}: {entry}" for entry in nested_messages)
        return messages

    if isinstance(payload, (list, tuple)):
        messages: list[str] = []
        for raw_item in payload:
            messages.extend(_collect_error_messages(raw_item))
        return messages

    translated = _translate_text(payload)
    return [translated] if translated else []


def custom_exception_handler(exc, context):
    # Handle DomainValidationError (business logic validation failures) → 400
    if isinstance(exc, DomainValidationError):
        return Response(
            {
                "success": False,
                "message": _translate_text(exc)
                or str(translate("An unexpected error occurred.")),
                "error": "validation_error",
            },
            status=HTTP_400_BAD_REQUEST,
        )

    # Handle protected FK/soft-delete guard violations → 400
    if isinstance(exc, ProtectedError):
        message = (
            str(exc.args[0]).strip()
            if exc.args and str(exc.args[0]).strip()
            else "Cannot delete this record because it is referenced by related records."
        )
        return Response(
            {
                "success": False,
                "message": _translate_text(message)
                or str(translate("An unexpected error occurred.")),
                "error": "protected_error",
            },
            status=HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)

    def _get_error_code(exc):
        return getattr(exc, "code", getattr(exc, "default_code", "error"))

    if response is not None:
        error_messages = _collect_error_messages(response.data)
        final_message = "; ".join(error_messages).strip()

        response.data = {
            "success": False,
            "message": final_message
            or str(translate("An unexpected error occurred.")),
            "error": _get_error_code(exc),
        }

    return response
