from bot.services.ticket_qc_actions import TicketQCActionService
from bot.services.ticket_qc_queue import QCTicketQueueItem, QCTicketQueueService
from core.utils.constants import TicketStatus


def test_qc_callback_data_roundtrip():
    payload = TicketQCActionService.build_callback_data(
        ticket_id=17,
        action=TicketQCActionService.ACTION_PASS,
    )
    assert TicketQCActionService.parse_callback_data(callback_data=payload) == (
        17,
        TicketQCActionService.ACTION_PASS,
    )


def test_qc_callback_parser_rejects_invalid_payloads():
    assert TicketQCActionService.parse_callback_data(callback_data="") is None
    assert (
        TicketQCActionService.parse_callback_data(callback_data="oops:1:pass") is None
    )
    assert (
        TicketQCActionService.parse_callback_data(callback_data="tqc:not-int:pass")
        is None
    )
    assert (
        TicketQCActionService.parse_callback_data(callback_data="tqc:1:unknown") is None
    )


def test_qc_keyboard_for_waiting_qc_ticket_has_pass_fail_and_refresh():
    markup = TicketQCActionService.build_action_keyboard(
        ticket_id=22,
        ticket_status=TicketStatus.WAITING_QC,
    )
    assert markup is not None
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert f"tqc:22:{TicketQCActionService.ACTION_PASS}" in callbacks
    assert f"tqc:22:{TicketQCActionService.ACTION_FAIL}" in callbacks
    assert f"tqc:22:{TicketQCActionService.ACTION_REFRESH}" in callbacks


def test_qc_keyboard_for_non_waiting_ticket_has_only_refresh():
    markup = TicketQCActionService.build_action_keyboard(
        ticket_id=31,
        ticket_status=TicketStatus.DONE,
    )
    assert markup is not None
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert callbacks == [f"tqc:31:{TicketQCActionService.ACTION_REFRESH}"]


def test_qc_transition_metadata_has_telegram_source_for_decisions():
    pass_metadata = TicketQCActionService.transition_metadata(
        action=TicketQCActionService.ACTION_PASS,
    )
    fail_metadata = TicketQCActionService.transition_metadata(
        action=TicketQCActionService.ACTION_FAIL,
    )

    assert pass_metadata == {
        "source": "telegram_bot",
        "channel": "qc_callback",
        "telegram_action": TicketQCActionService.ACTION_PASS,
    }
    assert fail_metadata == {
        "source": "telegram_bot",
        "channel": "qc_callback",
        "telegram_action": TicketQCActionService.ACTION_FAIL,
    }


def test_qc_queue_callback_roundtrip_for_open_and_refresh():
    open_payload = QCTicketQueueService.build_queue_callback_data(
        action=QCTicketQueueService.QUEUE_ACTION_OPEN,
        ticket_id=44,
        page=3,
    )
    assert QCTicketQueueService.parse_queue_callback_data(
        callback_data=open_payload
    ) == (
        QCTicketQueueService.QUEUE_ACTION_OPEN,
        44,
        3,
    )

    refresh_payload = QCTicketQueueService.build_queue_callback_data(
        action=QCTicketQueueService.QUEUE_ACTION_REFRESH,
        page=2,
    )
    assert QCTicketQueueService.parse_queue_callback_data(
        callback_data=refresh_payload
    ) == (
        QCTicketQueueService.QUEUE_ACTION_REFRESH,
        None,
        2,
    )


def test_qc_queue_keyboard_keeps_pagination_row_even_when_empty():
    markup = QCTicketQueueService.build_queue_keyboard(
        items=[],
        page=1,
        page_count=1,
    )
    assert markup is not None
    assert len(markup.inline_keyboard) == 1
    texts = [button.text for button in markup.inline_keyboard[0]]
    assert texts == ["<", "1/1", ">"]


def test_qc_queue_keyboard_includes_open_callbacks_for_items():
    markup = QCTicketQueueService.build_queue_keyboard(
        items=[
            QCTicketQueueItem(
                ticket_id=7, serial_number="RM-7", technician_label="Tech"
            ),
            QCTicketQueueItem(
                ticket_id=9, serial_number="RM-9", technician_label="Lead"
            ),
        ],
        page=2,
        page_count=4,
    )
    callbacks = [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]
    assert "tqq:open:7:2" in callbacks
    assert "tqq:open:9:2" in callbacks
    assert "tqq:refresh:1" in callbacks
    assert "tqq:refresh:2" in callbacks
    assert "tqq:refresh:3" in callbacks
