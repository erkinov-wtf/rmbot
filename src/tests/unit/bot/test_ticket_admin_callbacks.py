from types import SimpleNamespace

from bot.permissions import TicketBotPermissionSet
from bot.services.ticket_admin_support import (
    REVIEW_ACTION_ASSIGN_OPEN,
    REVIEW_ACTION_CALLBACK_PREFIX,
    REVIEW_ACTION_MANUAL_OPEN,
    REVIEW_QUEUE_ACTION_OPEN,
    REVIEW_QUEUE_ACTION_REFRESH,
    REVIEW_QUEUE_CALLBACK_PREFIX,
    _assign_keyboard,
    _create_items_keyboard,
    _parse_create_callback,
    _parse_review_action_callback,
    _parse_review_queue_callback,
    _review_queue_keyboard,
    _review_ticket_keyboard,
)
from core.utils.constants import TicketStatus


def _callback_values(markup):
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


def test_create_callback_parser_accepts_supported_payloads():
    assert _parse_create_callback(callback_data="tc:cancel") == ("cancel", [])
    assert _parse_create_callback(callback_data="tc:item:15:2") == (
        "item",
        ["15", "2"],
    )
    assert _parse_create_callback(callback_data="tc:adj:-5") == ("adj", ["-5"])


def test_create_callback_parser_rejects_invalid_payloads():
    assert _parse_create_callback(callback_data="") is None
    assert _parse_create_callback(callback_data="tc") is None
    assert _parse_create_callback(callback_data="oops:item:1") is None


def test_review_queue_callback_parser_accepts_refresh_and_open():
    assert _parse_review_queue_callback(
        callback_data=f"{REVIEW_QUEUE_CALLBACK_PREFIX}:{REVIEW_QUEUE_ACTION_REFRESH}"
    ) == (REVIEW_QUEUE_ACTION_REFRESH, None, 1)
    assert _parse_review_queue_callback(
        callback_data=f"{REVIEW_QUEUE_CALLBACK_PREFIX}:{REVIEW_QUEUE_ACTION_REFRESH}:3"
    ) == (REVIEW_QUEUE_ACTION_REFRESH, None, 3)
    assert _parse_review_queue_callback(
        callback_data=f"{REVIEW_QUEUE_CALLBACK_PREFIX}:{REVIEW_QUEUE_ACTION_OPEN}:42"
    ) == (REVIEW_QUEUE_ACTION_OPEN, 42, 1)
    assert _parse_review_queue_callback(
        callback_data=f"{REVIEW_QUEUE_CALLBACK_PREFIX}:{REVIEW_QUEUE_ACTION_OPEN}:42:4"
    ) == (REVIEW_QUEUE_ACTION_OPEN, 42, 4)


def test_review_queue_callback_parser_rejects_invalid_payloads():
    assert _parse_review_queue_callback(callback_data="trq:open:bad") is None
    assert _parse_review_queue_callback(callback_data="invalid:data") is None
    assert _parse_review_queue_callback(callback_data="trq") is None


def test_review_action_callback_parser_accepts_supported_payloads():
    assert _parse_review_action_callback(
        callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_ASSIGN_OPEN}:7"
    ) == (REVIEW_ACTION_ASSIGN_OPEN, 7, None)
    assert _parse_review_action_callback(
        callback_data=f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_OPEN}:7:green"
    ) == (REVIEW_ACTION_MANUAL_OPEN, 7, "green")


def test_review_action_callback_parser_rejects_invalid_payloads():
    assert _parse_review_action_callback(callback_data="tra:assign:not-int") is None
    assert _parse_review_action_callback(callback_data="invalid:data") is None
    assert _parse_review_action_callback(callback_data="tra") is None


def test_review_ticket_keyboard_hides_buttons_without_permissions():
    markup = _review_ticket_keyboard(
        ticket_id=17,
        page=1,
        permissions=TicketBotPermissionSet(),
    )
    callbacks = _callback_values(markup)

    assert (
        f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_ASSIGN_OPEN}:17"
        not in callbacks
    )
    assert (
        f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_OPEN}:17"
        not in callbacks
    )
    assert (
        f"{REVIEW_QUEUE_CALLBACK_PREFIX}:{REVIEW_QUEUE_ACTION_OPEN}:17:1" in callbacks
    )
    assert (
        f"{REVIEW_QUEUE_CALLBACK_PREFIX}:{REVIEW_QUEUE_ACTION_REFRESH}:1" in callbacks
    )


def test_review_ticket_keyboard_shows_only_permitted_actions():
    assign_only_markup = _review_ticket_keyboard(
        ticket_id=21,
        page=2,
        permissions=TicketBotPermissionSet(
            can_review=True,
            can_assign=True,
            can_manual_metrics=False,
        ),
    )
    assign_only_callbacks = _callback_values(assign_only_markup)
    assert (
        f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_ASSIGN_OPEN}:21"
        in assign_only_callbacks
    )
    assert (
        f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_OPEN}:21"
        not in assign_only_callbacks
    )

    manual_only_markup = _review_ticket_keyboard(
        ticket_id=22,
        page=3,
        permissions=TicketBotPermissionSet(
            can_review=False,
            can_assign=False,
            can_manual_metrics=True,
        ),
    )
    manual_only_callbacks = _callback_values(manual_only_markup)
    assert (
        f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_ASSIGN_OPEN}:22"
        not in manual_only_callbacks
    )
    assert (
        f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_OPEN}:22"
        in manual_only_callbacks
    )


def test_review_ticket_keyboard_hides_assign_for_non_assignable_status():
    markup = _review_ticket_keyboard(
        ticket_id=33,
        page=1,
        permissions=TicketBotPermissionSet(
            can_review=True,
            can_assign=True,
            can_manual_metrics=True,
        ),
        ticket_status=TicketStatus.DONE,
    )
    callbacks = _callback_values(markup)

    assert (
        f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_ASSIGN_OPEN}:33"
        not in callbacks
    )
    assert (
        f"{REVIEW_ACTION_CALLBACK_PREFIX}:{REVIEW_ACTION_MANUAL_OPEN}:33" in callbacks
    )


def test_create_items_keyboard_has_always_visible_pagination_controls():
    items = [
        SimpleNamespace(id=1, serial_number="RM-1"),
        SimpleNamespace(id=2, serial_number="RM-2"),
    ]
    markup = _create_items_keyboard(
        page=1,
        page_count=3,
        items=items,
    )

    assert [button.text for button in markup.inline_keyboard[-2]] == ["<", "1/3", ">"]
    assert [button.callback_data for button in markup.inline_keyboard[-2]] == [
        "tc:list:1",
        "tc:list:1",
        "tc:list:2",
    ]


def test_review_queue_keyboard_has_always_visible_pagination_controls():
    ticket = SimpleNamespace(
        id=17,
        inventory_item=SimpleNamespace(serial_number="RM-Q-17"),
    )
    markup = _review_queue_keyboard(
        tickets=[ticket],
        page=1,
        page_count=1,
    )

    assert [button.text for button in markup.inline_keyboard[-1]] == ["<", "1/1", ">"]
    assert [button.callback_data for button in markup.inline_keyboard[-1]] == [
        "trq:refresh:1",
        "trq:refresh:1",
        "trq:refresh:1",
    ]


def test_assign_keyboard_has_always_visible_pagination_controls():
    markup = _assign_keyboard(
        ticket_id=11,
        technician_options=[(101, "Tech One")],
        page=2,
        page_count=4,
    )

    assert [button.text for button in markup.inline_keyboard[-2]] == ["<", "2/4", ">"]
    assert [button.callback_data for button in markup.inline_keyboard[-2]] == [
        "tra:ap:11:1",
        "tra:ap:11:2",
        "tra:ap:11:3",
    ]
