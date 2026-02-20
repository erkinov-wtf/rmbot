from django.db.models.deletion import ProtectedError
from rest_framework.status import HTTP_400_BAD_REQUEST

from core.api.exceptions import DomainValidationError, custom_exception_handler


def test_custom_exception_handler_returns_400_for_domain_validation_error():
    response = custom_exception_handler(DomainValidationError("broken rule"), {})

    assert response is not None
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.data == {
        "success": False,
        "message": "broken rule",
        "error": "validation_error",
    }


def test_custom_exception_handler_returns_400_for_protected_error():
    protected_error = ProtectedError(
        "Cannot delete referenced object.",
        protected_objects=[],
    )

    response = custom_exception_handler(protected_error, {})

    assert response is not None
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.data == {
        "success": False,
        "message": "Cannot delete referenced object.",
        "error": "protected_error",
    }
