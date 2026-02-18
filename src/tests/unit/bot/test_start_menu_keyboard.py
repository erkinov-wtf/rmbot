from bot.services.menu import (
    MENU_BUTTON_ACTIVE_TICKETS,
    MENU_BUTTON_HELP,
    MENU_BUTTON_MY_STATUS,
    MENU_BUTTON_MY_XP,
    MENU_BUTTON_PAST_TICKETS,
    MENU_BUTTON_START_ACCESS,
    MENU_BUTTON_UNDER_QC_TICKETS,
    MENU_BUTTON_XP_HISTORY,
    BotMenuService,
)


def _keyboard_text_rows(markup):
    return [[button.text for button in row] for row in markup.keyboard]


def test_technician_menu_contains_full_technician_controls():
    markup = BotMenuService.build_main_menu_keyboard(
        is_technician=True,
        can_create_ticket=False,
        can_review_ticket=False,
        include_start_access=False,
    )
    assert _keyboard_text_rows(markup) == [
        [MENU_BUTTON_ACTIVE_TICKETS, MENU_BUTTON_UNDER_QC_TICKETS],
        [MENU_BUTTON_PAST_TICKETS, MENU_BUTTON_MY_XP],
        [MENU_BUTTON_XP_HISTORY, MENU_BUTTON_MY_STATUS],
        [MENU_BUTTON_HELP],
    ]


def test_technician_menu_hides_ticket_admin_buttons_when_permitted():
    markup = BotMenuService.build_main_menu_keyboard(
        is_technician=True,
        can_create_ticket=True,
        can_review_ticket=True,
        can_qc_checks=True,
        include_start_access=False,
    )
    assert _keyboard_text_rows(markup) == [
        [MENU_BUTTON_ACTIVE_TICKETS, MENU_BUTTON_UNDER_QC_TICKETS],
        [MENU_BUTTON_PAST_TICKETS, MENU_BUTTON_MY_XP],
        [MENU_BUTTON_XP_HISTORY, MENU_BUTTON_MY_STATUS],
        [MENU_BUTTON_HELP],
    ]


def test_non_technician_menu_hides_ticket_admin_buttons_when_permitted():
    markup = BotMenuService.build_main_menu_keyboard(
        is_technician=False,
        can_create_ticket=True,
        can_review_ticket=True,
        can_qc_checks=True,
        include_start_access=False,
    )
    assert _keyboard_text_rows(markup) == [
        [MENU_BUTTON_MY_STATUS, MENU_BUTTON_HELP],
    ]


def test_non_technician_menu_can_offer_start_access():
    markup = BotMenuService.build_main_menu_keyboard(
        is_technician=False,
        can_create_ticket=False,
        can_review_ticket=False,
        include_start_access=True,
    )
    assert _keyboard_text_rows(markup) == [
        [MENU_BUTTON_MY_STATUS, MENU_BUTTON_HELP],
        [MENU_BUTTON_START_ACCESS],
    ]


def test_non_technician_menu_ignores_qc_checks_button_flag():
    markup = BotMenuService.build_main_menu_keyboard(
        is_technician=False,
        can_create_ticket=False,
        can_review_ticket=False,
        can_qc_checks=True,
        include_start_access=False,
    )
    assert _keyboard_text_rows(markup) == [
        [MENU_BUTTON_MY_STATUS, MENU_BUTTON_HELP],
    ]


def test_technician_menu_ignores_qc_checks_button_flag():
    markup = BotMenuService.build_main_menu_keyboard(
        is_technician=True,
        can_create_ticket=False,
        can_review_ticket=False,
        can_qc_checks=True,
        include_start_access=False,
    )
    assert _keyboard_text_rows(markup) == [
        [MENU_BUTTON_ACTIVE_TICKETS, MENU_BUTTON_UNDER_QC_TICKETS],
        [MENU_BUTTON_PAST_TICKETS, MENU_BUTTON_MY_XP],
        [MENU_BUTTON_XP_HISTORY, MENU_BUTTON_MY_STATUS],
        [MENU_BUTTON_HELP],
    ]
