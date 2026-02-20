from django.db.models.deletion import ProtectedError
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST
from rest_framework.views import exception_handler


class DomainValidationError(Exception):
    """
    Raised when business logic validation fails.
    Caught by custom_exception_handler and returns HTTP 400 Bad Request.
    """

    pass


def custom_exception_handler(exc, context):
    # Handle DomainValidationError (business logic validation failures) → 400
    if isinstance(exc, DomainValidationError):
        return Response(
            {
                "success": False,
                "message": str(exc),
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
                "message": message,
                "error": "protected_error",
            },
            status=HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)

    def _get_error_code(exc):
        return getattr(exc, "code", getattr(exc, "default_code", "error"))

    if response is not None:
        error_messages = []

        if isinstance(response.data, dict):
            for field, messages in response.data.items():
                if isinstance(messages, list):
                    # Simple field errors
                    joined = ", ".join(str(msg) for msg in messages)
                    error_messages.append(f"{field}: {joined}")
                elif isinstance(messages, dict):
                    # Nested serializer errors
                    for sub_field, sub_messages in messages.items():
                        joined = ", ".join(str(msg) for msg in sub_messages)
                        error_messages.append(f"{field}.{sub_field}: {joined}")
                else:
                    # General (non-field) errors, e.g. 'detail'
                    error_messages.append(str(messages))
        elif isinstance(response.data, list):
            # Non-field errors as a list
            for message in response.data:
                error_messages.append(str(message))

        final_message = "; ".join(error_messages).strip()

        response.data = {
            "success": False,
            "message": final_message or "An unexpected error occurred.",
            "error": _get_error_code(exc),
        }

    return response
