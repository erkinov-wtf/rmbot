import re

from django.db.models.deletion import ProtectedError
from django.utils.translation import get_language
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


GENERIC_ERROR_MESSAGE = "An unexpected error occurred."
PROTECTED_REFERENCE_ERROR_MESSAGE = (
    "Cannot delete this record because it is referenced by related records."
)

_PROTECTED_ERROR_PATTERNS = (
    re.compile(
        r"^Cannot delete some instances of model '.+' because they are referenced through protected foreign keys: .+\.$"
    ),
    re.compile(
        r"^Cannot delete some instances of model '.+' because they are referenced through restricted foreign keys: .+\.$"
    ),
    re.compile(r"^Cannot delete referenced object\.?$"),
)

_ENGLISH_HINT_WORDS = {
    "a",
    "an",
    "already",
    "and",
    "are",
    "because",
    "before",
    "be",
    "by",
    "cannot",
    "check",
    "delete",
    "details",
    "does",
    "error",
    "exist",
    "failed",
    "field",
    "for",
    "foreign",
    "from",
    "in",
    "instances",
    "invalid",
    "is",
    "keys",
    "model",
    "must",
    "not",
    "number",
    "of",
    "only",
    "or",
    "record",
    "referenced",
    "related",
    "required",
    "review",
    "some",
    "status",
    "the",
    "this",
    "ticket",
    "through",
    "user",
    "was",
    "with",
}

_FALLBACK_ERROR_TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": {
        GENERIC_ERROR_MESSAGE: "Произошла непредвиденная ошибка.",
        PROTECTED_REFERENCE_ERROR_MESSAGE: (
            "Нельзя удалить эту запись, потому что на неё ссылаются связанные записи."
        ),
        "Unknown error.": "Неизвестная ошибка.",
        "You are already registered and linked.": "Вы уже зарегистрированы и привязаны.",
        "Your access request was already approved.": "Ваша заявка на доступ уже была одобрена.",
        "Phone number is already used by another account.": (
            "Этот номер телефона уже используется другим аккаунтом."
        ),
    },
    "uz": {
        GENERIC_ERROR_MESSAGE: "Kutilmagan xatolik yuz berdi.",
        PROTECTED_REFERENCE_ERROR_MESSAGE: (
            "Bu yozuvni o'chirib bo'lmaydi, chunki unga bog'liq yozuvlar murojaat qilmoqda."
        ),
        "Unknown error.": "Noma'lum xatolik.",
        "You are already registered and linked.": (
            "Siz allaqachon ro'yxatdan o'tgansiz va bog'langansiz."
        ),
        "Your access request was already approved.": (
            "Kirish so'rovingiz allaqachon tasdiqlangan."
        ),
        "Phone number is already used by another account.": (
            "Bu telefon raqami boshqa akkaunt tomonidan allaqachon ishlatilgan."
        ),
    },
}


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _normalize_language_code(raw_language: str | None) -> str:
    language = str(raw_language or "").strip().lower()
    if not language:
        return "en"
    return language.split("-", 1)[0]


def _active_language_code() -> str:
    return _normalize_language_code(get_language())


def _is_non_english_language() -> bool:
    return _active_language_code() != "en"


def _fallback_translate_message(message: str) -> str | None:
    return _FALLBACK_ERROR_TRANSLATIONS.get(_active_language_code(), {}).get(message)


def _normalize_message_key(text: str) -> str:
    for pattern in _PROTECTED_ERROR_PATTERNS:
        if pattern.match(text):
            return PROTECTED_REFERENCE_ERROR_MESSAGE
    return text


def _looks_like_english_message(text: str) -> bool:
    words = re.findall(r"[A-Za-z]+", text.lower())
    if not words:
        return False
    hits = sum(1 for word in words if word in _ENGLISH_HINT_WORDS)
    return hits >= max(1, len(words) // 4)


def _localized_generic_error() -> str:
    translated = _normalize_text(translate(GENERIC_ERROR_MESSAGE))
    if translated and translated != GENERIC_ERROR_MESSAGE:
        return translated
    fallback = _fallback_translate_message(GENERIC_ERROR_MESSAGE)
    if fallback:
        return fallback
    return GENERIC_ERROR_MESSAGE


def _translate_text(value: object, *, allow_generic_fallback: bool = False) -> str:
    normalized = _normalize_text(value)
    if not normalized:
        return ""
    message_key = _normalize_message_key(normalized)

    translated = _normalize_text(translate(message_key))
    if translated and translated != message_key:
        return translated

    fallback = _fallback_translate_message(message_key)
    if fallback:
        return fallback

    if (
        allow_generic_fallback
        and _is_non_english_language()
        and _looks_like_english_message(message_key)
    ):
        return _localized_generic_error()

    return message_key


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
                "message": _translate_text(exc, allow_generic_fallback=True)
                or _localized_generic_error(),
                "error": "validation_error",
            },
            status=HTTP_400_BAD_REQUEST,
        )

    # Handle protected FK/soft-delete guard violations → 400
    if isinstance(exc, ProtectedError):
        return Response(
            {
                "success": False,
                "message": _translate_text(
                    PROTECTED_REFERENCE_ERROR_MESSAGE,
                    allow_generic_fallback=True,
                )
                or _localized_generic_error(),
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
            "message": _translate_text(final_message, allow_generic_fallback=True)
            or _localized_generic_error(),
            "error": _get_error_code(exc),
        }

    return response
