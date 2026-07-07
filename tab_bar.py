from kitty.fast_data_types import background_opacity_of, get_boss, get_options
from kitty.tab_bar import TabAccessor, wcswidth


def _rgb(color):
    return (color << 8) | 2


CATPPUCCIN = {
    "background": 0x1E1E2E,
    "foreground": 0xCDD6F4,
    "bblack": 0x181825,
    "blue": 0x89B4FA,
    "green": 0xA6E3A1,
    "yellow": 0xF9E2AF,
    "dim": 0x7F849C,
}

CONTROL_TITLES = (
    "__kitty_traffic_close__",
    "__kitty_traffic_minimize__",
    "__kitty_traffic_fullscreen__",
)
CONTROL_TABS = {
    CONTROL_TITLES[0]: (0xFF5F57, "●"),
    CONTROL_TITLES[1]: (0xFFBD2E, "●"),
    CONTROL_TITLES[2]: (0x28C840, "●"),
}
CONTROL_TABS_BY_INDEX = (
    CONTROL_TABS[CONTROL_TITLES[0]],
    CONTROL_TABS[CONTROL_TITLES[1]],
    CONTROL_TABS[CONTROL_TITLES[2]],
)

FSQUARE_DIGITS = "󰎡󰎤󰎧󰎪󰎭󰎱󰎳󰎶󰎹󰎼"
ACTIVE_ICON = ""
INACTIVE_ICON = ""
NEOVIM_ICON = ""
ACTIVE_MIN_TITLE_CELLS = 12
NEOVIM_OPACITY = 1
OPACITY_EPSILON = 0.0001
_opacity_by_os_window = {}


def _data_get(data, key, default=None):
    if isinstance(data, dict):
        return data.get(key, default)
    return getattr(data, key, default)


def draw_title(data):
    title = _data_get(data, "title", "")
    if title in CONTROL_TITLES:
        return title

    num_windows = _data_get(data, "num_windows", 1)
    return f"{title} :{num_windows}:" if num_windows > 1 else title


def _draw_control_tab(draw_data, screen, control_index):
    fg, bg = screen.cursor.fg, screen.cursor.bg
    bold, italic = screen.cursor.bold, screen.cursor.italic

    color, char = CONTROL_TABS_BY_INDEX[control_index]
    screen.cursor.bold = False
    screen.cursor.italic = False
    screen.cursor.bg = _rgb(int(draw_data.default_bg))
    screen.cursor.fg = _rgb(color)
    screen.draw(" ")
    screen.draw(char)
    if control_index == 2:
        screen.draw(" ")

    screen.cursor.fg = fg
    screen.cursor.bg = bg
    screen.cursor.bold = bold
    screen.cursor.italic = italic
    return screen.cursor.x


def _index_text(index):
    return "".join(FSQUARE_DIGITS[int(digit)] for digit in str(index))


def _short_title(tab, max_cells):
    title = tab.title.strip() or "kitty"
    if max_cells <= 0:
        return ""
    if wcswidth(title) <= max_cells:
        return title

    ellipsis = "…"
    ellipsis_width = max(1, wcswidth(ellipsis))
    if max_cells <= ellipsis_width:
        return ellipsis

    budget = max_cells - ellipsis_width
    used = 0
    chars = []
    for char in title:
        width = max(0, wcswidth(char))
        if used + width > budget:
            break
        chars.append(char)
        used += width

    return "".join(chars) + ellipsis


def _active_exe(tab):
    try:
        return str(TabAccessor(tab.tab_id).active_exe or "").rsplit("/", 1)[-1].lower()
    except Exception:
        return ""


def _is_neovim_tab(tab):
    exe = _active_exe(tab)
    title = tab.title.lower()
    return exe in {"nvim", "neovim"} or "nvim" in title or "neovim" in title


def _tab_icon(is_neovim):
    if is_neovim:
        return NEOVIM_ICON
    return ACTIVE_ICON


def _sync_active_tab_opacity(tab, is_neovim):
    if not tab.is_active:
        return

    try:
        opts = get_options()
        if not opts.dynamic_background_opacity:
            return

        os_window_id = tab.os_window_id
        opacity = NEOVIM_OPACITY if is_neovim else float(opts.background_opacity)
        cached = _opacity_by_os_window.get(os_window_id)
        if cached is not None and abs(cached - opacity) <= OPACITY_EPSILON:
            return

        current = background_opacity_of(os_window_id)
        if current is not None and abs(current - opacity) <= OPACITY_EPSILON:
            _opacity_by_os_window[os_window_id] = opacity
            return

        boss = get_boss()
        if boss is not None:
            _opacity_by_os_window[os_window_id] = opacity
            boss._set_os_window_background_opacity(os_window_id, opacity)
    except Exception:
        pass


def _draw_tmux_tab(draw_data, screen, tab, max_tab_length, index):
    fg, bg = screen.cursor.fg, screen.cursor.bg
    bold, italic = screen.cursor.bold, screen.cursor.italic

    active = tab.is_active
    is_neovim = _is_neovim_tab(tab)
    _sync_active_tab_opacity(tab, is_neovim)
    screen.cursor.bg = _rgb(
        CATPPUCCIN["bblack"] if active else int(draw_data.default_bg)
    )
    screen.cursor.bold = active
    screen.cursor.italic = False

    # Shape mirrors tmux-tabsbar:
    # current: blue fsquare id, foreground terminal icon/title on bblack
    # inactive: transparent background, dim foreground.
    index_text = _index_text(max(1, index - len(CONTROL_TITLES)))
    icon = _tab_icon(is_neovim)

    screen.draw(" ")
    screen.cursor.fg = _rgb(CATPPUCCIN["blue"] if active else CATPPUCCIN["dim"])
    screen.draw(index_text)
    screen.draw(" ")

    screen.cursor.fg = _rgb(CATPPUCCIN["foreground"] if active else CATPPUCCIN["dim"])
    screen.draw(icon)
    screen.draw(" ")
    prefix_cells = wcswidth(f" {index_text} {icon} ")
    title_budget = max(1, max_tab_length - prefix_cells - 1)
    if active:
        title_budget = max(
            title_budget,
            min(wcswidth(tab.title.strip() or "kitty"), ACTIVE_MIN_TITLE_CELLS),
        )
    screen.draw(_short_title(tab, title_budget))
    screen.draw(" ")

    screen.cursor.fg = fg
    screen.cursor.bg = bg
    screen.cursor.bold = bold
    screen.cursor.italic = italic
    return screen.cursor.x


def draw_tab(
    draw_data,
    screen,
    tab,
    before,
    max_tab_length,
    index,
    is_last,
    extra_data,
):
    if index <= len(CONTROL_TITLES):
        return _draw_control_tab(draw_data, screen, index - 1)

    return _draw_tmux_tab(draw_data, screen, tab, max_tab_length, index)
