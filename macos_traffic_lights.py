from kitty.conf.utils import KeyAction
from kitty.tabs import SpecialWindow
from time import monotonic


CONTROL_ORDER = (
    "__kitty_traffic_close__",
    "__kitty_traffic_minimize__",
    "__kitty_traffic_fullscreen__",
)
CONTROL_ACTIONS = {
    CONTROL_ORDER[0]: "close",
    CONTROL_ORDER[1]: "minimize",
    CONTROL_ORDER[2]: "fullscreen",
}
CONTROL_COMMAND = ["sh", "-c", "true"]

_busy = False
_initialized_os_windows = set()
_ignore_focus_until = {}


def _title(obj):
    value = getattr(obj, "title", "")
    if callable(value):
        value = value()
    return value or ""


def _tabs(tab_manager):
    return tuple(getattr(tab_manager, "tabs", ())) or tuple(tab_manager.tabs_to_be_shown_in_tab_bar)


def _focus_first_normal_tab(tab_manager):
    tabs = tuple(tab_manager.tabs_to_be_shown_in_tab_bar)
    for tab in tabs[3:]:
        tab_manager.set_active_tab(tab)
        return True

    for tab in tabs:
        if _title(tab) not in CONTROL_ACTIONS:
            tab_manager.set_active_tab(tab)
            return True

    return False


def _has_control_tabs(tab_manager):
    tabs = _tabs(tab_manager)
    return (
        len(tabs) >= 3
        and tuple(_title(tab) for tab in tabs[:3]) == CONTROL_ORDER
        and all(getattr(tab, "active_window", None) is not None for tab in tabs[:3])
    )


def _remove_extra_control_tabs(boss, tab_manager):
    for tab in _tabs(tab_manager)[3:]:
        if _title(tab) in CONTROL_ACTIONS:
            boss.close_tab_no_confirm(tab)


def _remove_all_control_tabs(boss, tab_manager):
    for tab in _tabs(tab_manager):
        if _title(tab) in CONTROL_ACTIONS:
            boss.close_tab_no_confirm(tab)
    _initialized_os_windows.discard(tab_manager.os_window_id)


def _ensure_control_tabs(boss, tab_manager):
    if tab_manager is None:
        return

    os_window_id = tab_manager.os_window_id
    if _has_control_tabs(tab_manager):
        _initialized_os_windows.add(os_window_id)
        _remove_extra_control_tabs(boss, tab_manager)
        return

    if os_window_id in _initialized_os_windows:
        return

    normal_tab = tab_manager.active_tab
    for title in reversed(CONTROL_ORDER):
        tab = tab_manager.new_tab(
            SpecialWindow(CONTROL_COMMAND, override_title=title, hold=True),
            location="first",
        )
        tab.set_title(title)
        active_window = getattr(tab, "active_window", None)
        if active_window is not None:
            _ignore_focus_until[active_window.id] = monotonic() + 1.0

    if normal_tab is not None:
        tab_manager.set_active_tab(normal_tab)
    _initialized_os_windows.add(os_window_id)


def _run_action(boss, window, name):
    return boss.dispatch_action(KeyAction(name), window_for_dispatch=window)


def _handle_control_tab(boss, tab_manager, event_window=None, source="unknown"):
    tab = tab_manager.active_tab
    action = CONTROL_ACTIONS.get(_title(tab))
    if action is None:
        return False

    window = getattr(tab, "active_window", None) or event_window
    if window is None:
        return False

    ignore_until = _ignore_focus_until.pop(window.id, 0)
    if ignore_until >= monotonic():
        _focus_first_normal_tab(tab_manager)
        return True

    if action == "close":
        _focus_first_normal_tab(tab_manager)
        _remove_all_control_tabs(boss, tab_manager)
        boss.close_os_window()
        return True

    if action == "minimize":
        _focus_first_normal_tab(tab_manager)
        _run_action(boss, window, "minimize_macos_window")
        return True

    if action == "fullscreen":
        _focus_first_normal_tab(tab_manager)
        _run_action(boss, window, "toggle_fullscreen")
        return True

    return False


def _ensure_all_control_tabs(boss):
    for tab_manager in getattr(boss, "all_tab_managers", ()):
        _ensure_control_tabs(boss, tab_manager)


def _tab_manager_for_window(boss, window):
    active = getattr(boss, "active_tab_manager", None)
    if active is not None and active.os_window_id == window.os_window_id:
        return active

    for tab_manager in getattr(boss, "all_tab_managers", ()):
        if tab_manager.os_window_id == window.os_window_id:
            return tab_manager

    return active


def on_load(boss, data):
    global _busy

    if _busy:
        return
    _busy = True
    try:
        _ensure_all_control_tabs(boss)
    finally:
        _busy = False


def _ensure_for_window(boss, window):
    global _busy

    if _busy:
        return
    _busy = True
    try:
        _ensure_control_tabs(boss, _tab_manager_for_window(boss, window))
    finally:
        _busy = False


def on_resize(boss, window, data):
    _ensure_for_window(boss, window)


def on_title_change(boss, window, data):
    _ensure_for_window(boss, window)


def on_cmd_startstop(boss, window, data):
    _ensure_for_window(boss, window)


def on_tab_bar_dirty(boss, window, data):
    global _busy

    if _busy:
        return

    _busy = True
    try:
        tab_manager = data.get("tab_manager") or _tab_manager_for_window(boss, window)
        if tab_manager is None:
            return
        _ensure_control_tabs(boss, tab_manager)
        _handle_control_tab(boss, tab_manager, window, "tab_bar_dirty")
    finally:
        _busy = False


def on_focus_change(boss, window, data):
    global _busy

    if _busy or not data.get("focused"):
        return

    _busy = True
    try:
        tab_manager = _tab_manager_for_window(boss, window)
        if tab_manager is None:
            return
        _ensure_control_tabs(boss, tab_manager)
        _handle_control_tab(boss, tab_manager, window, "focus_change")
    finally:
        _busy = False
