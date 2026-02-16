from bot.routers.start import (
    MENU_BUTTON_ACTIVE_TICKETS,
    MENU_BUTTON_HELP,
    MENU_BUTTON_MY_STATUS,
    MENU_BUTTON_MY_XP,
    MENU_BUTTON_PAST_TICKETS,
    MENU_BUTTON_START_ACCESS,
    MENU_BUTTON_UNDER_QC_TICKETS,
    MENU_BUTTON_XP_HISTORY,
    build_main_menu_keyboard,
)


def _keyboard_text_rows(markup):
    return [[button.text for button in row] for row in markup.keyboard]


def test_technician_menu_contains_full_technician_controls():
    markup = build_main_menu_keyboard(
        is_technician=True,
        include_start_access=False,
    )
    assert _keyboard_text_rows(markup) == [
        [MENU_BUTTON_ACTIVE_TICKETS, MENU_BUTTON_UNDER_QC_TICKETS],
        [MENU_BUTTON_PAST_TICKETS, MENU_BUTTON_MY_XP],
        [MENU_BUTTON_XP_HISTORY, MENU_BUTTON_MY_STATUS],
        [MENU_BUTTON_HELP],
    ]


def test_non_technician_menu_can_offer_start_access():
    markup = build_main_menu_keyboard(
        is_technician=False,
        include_start_access=True,
    )
    assert _keyboard_text_rows(markup) == [
        [MENU_BUTTON_MY_STATUS, MENU_BUTTON_HELP],
        [MENU_BUTTON_START_ACCESS],
    ]
