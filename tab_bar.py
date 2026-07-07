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


def _tab_icon(tab, active):
    exe = _active_exe(tab)
    title = tab.title.lower()
    if exe in {"nvim", "neovim"} or "nvim" in title or "neovim" in title:
        return NEOVIM_ICON
    return ACTIVE_ICON


def _draw_tmux_tab(draw_data, screen, tab, max_tab_length, index):
    fg, bg = screen.cursor.fg, screen.cursor.bg
    bold, italic = screen.cursor.bold, screen.cursor.italic

    active = tab.is_active
    screen.cursor.bg = _rgb(CATPPUCCIN["bblack"] if active else int(draw_data.default_bg))
    screen.cursor.bold = active
    screen.cursor.italic = False

    # Shape mirrors tmux-tabsbar:
    # current: blue fsquare id, foreground terminal icon/title on bblack
    # inactive: transparent background, dim foreground.
    index_text = _index_text(max(1, index - len(CONTROL_TITLES)))
    icon = _tab_icon(tab, active)

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
        title_budget = max(title_budget, min(wcswidth(tab.title.strip() or "kitty"), ACTIVE_MIN_TITLE_CELLS))
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
