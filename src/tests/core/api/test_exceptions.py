from django.db.models.deletion import ProtectedError
from django.utils.translation import override
from rest_framework.exceptions import ValidationError
from rest_framework.status import HTTP_400_BAD_REQUEST

from core.api.exceptions import (
    DomainValidationError,
    PROTECTED_REFERENCE_ERROR_MESSAGE,
    custom_exception_handler,
)


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
        "message": PROTECTED_REFERENCE_ERROR_MESSAGE,
        "error": "protected_error",
    }


def test_custom_exception_handler_localizes_protected_error_for_ru_locale():
    protected_error = ProtectedError(
        "Cannot delete some instances of model 'InventoryItem' because they are referenced through protected foreign keys: 'Ticket.inventory_item'.",
        protected_objects=[],
    )

    with override("ru"):
        response = custom_exception_handler(protected_error, {})

    assert response is not None
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.data == {
        "success": False,
        "message": "Нельзя удалить эту запись, потому что на неё ссылаются связанные записи.",
        "error": "protected_error",
    }


def test_custom_exception_handler_returns_localized_generic_for_unknown_ru_message():
    with override("ru"):
        response = custom_exception_handler(
            DomainValidationError("raw backend english error that is not translated"),
            {},
        )

    assert response is not None
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.data == {
        "success": False,
        "message": "Произошла непредвиденная ошибка.",
        "error": "validation_error",
    }


def test_custom_exception_handler_keeps_localized_validation_detail_for_ru_locale():
    with override("ru"):
        response = custom_exception_handler(
            ValidationError(
                {
                    "serial_number": ["Inventory item 'TEST' was not found."]
                }
            ),
            {},
        )

    assert response is not None
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.data == {
        "success": False,
        "message": (
            "Серийный номер: "
            "Inventory item 'TEST' was not found."
        ),
        "error": "invalid",
    }
