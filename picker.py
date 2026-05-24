#!/usr/bin/env python3
from __future__ import annotations

import argparse
import curses
import os
import sys
from pathlib import Path


def load_history(path: Path) -> list[str]:
    if not path.exists():
        return []
    raw = path.read_text(errors="replace").splitlines()
    cmds: list[str] = []
    for line in raw:
        line = line.rstrip("\n")
        if not line or line.startswith("#"):
            continue
        cmds.append(line)
    seen: set[str] = set()
    dedup: list[str] = []
    for cmd in reversed(cmds):
        if cmd in seen:
            continue
        seen.add(cmd)
        dedup.append(cmd)
    return dedup


def fuzzy_match(query: str, cmd: str) -> bool:
    if not query:
        return True
    cmd_l = cmd.lower()
    for token in query.lower().split():
        if token not in cmd_l:
            return False
    return True


def filter_history(history: list[str], query: str) -> list[str]:
    return [c for c in history if fuzzy_match(query, c)]


def highlight_spans(cmd: str, query: str) -> list[tuple[int, int]]:
    if not query:
        return []
    spans: list[tuple[int, int]] = []
    cmd_l = cmd.lower()
    for token in query.lower().split():
        start = 0
        while True:
            i = cmd_l.find(token, start)
            if i < 0:
                break
            spans.append((i, i + len(token)))
            start = i + len(token)
    return spans


C_HIGHLIGHT = 1   # yellow on default  — query matches in normal rows
C_SELECTED  = 2   # black on cyan      — selected row background
C_SEL_HI    = 3   # yellow on cyan     — query matches in selected row
C_STATUSBAR = 4   # black on white     — status bar
C_ARROW     = 5   # green on default   — prompt ">" arrow


def draw(stdscr, query: str, matches: list[str], cursor: int, scroll: int) -> None:
    stdscr.erase()
    max_y, max_x = stdscr.getmaxyx()
    if max_y < 3 or max_x < 10:
        try:
            stdscr.addstr(0, 0, "terminal too small")
        except curses.error:
            pass
        stdscr.refresh()
        return

    list_height = max_y - 2
    visible = matches[scroll:scroll + list_height]
    for i, cmd in enumerate(visible):
        y = i
        is_sel = (scroll + i) == cursor
        prefix = "> " if is_sel else "  "
        line = (prefix + cmd)[:max_x - 1]

        if is_sel:
            row_attr = curses.color_pair(C_SELECTED) | curses.A_BOLD
            hi_attr  = curses.color_pair(C_SEL_HI)  | curses.A_BOLD
        else:
            row_attr = curses.A_NORMAL
            hi_attr  = curses.color_pair(C_HIGHLIGHT) | curses.A_BOLD

        try:
            stdscr.addstr(y, 0, line.ljust(max_x - 1), row_attr)
        except curses.error:
            pass
        for s, e in highlight_spans(cmd, query):
            s2 = s + len(prefix)
            e2 = e + len(prefix)
            if s2 >= max_x - 1:
                continue
            e2 = min(e2, max_x - 1)
            try:
                stdscr.chgat(y, s2, e2 - s2, hi_attr)
            except curses.error:
                pass

    status = f"  {len(matches)} matches    ↑↓ / Ctrl-P/N  ⏎ select  Esc cancel"
    try:
        stdscr.addstr(max_y - 2, 0, status[:max_x - 1].ljust(max_x - 1),
                      curses.color_pair(C_STATUSBAR))
    except curses.error:
        pass

    try:
        stdscr.addstr(max_y - 1, 0, "> ", curses.color_pair(C_ARROW) | curses.A_BOLD)
        stdscr.addstr(max_y - 1, 2, query[:max_x - 3], curses.A_BOLD)
        stdscr.move(max_y - 1, min(2 + len(query), max_x - 1))
    except curses.error:
        pass

    stdscr.refresh()


def run(stdscr, history: list[str], initial_query: str) -> str | None:
    curses.use_default_colors()
    try:
        curses.init_pair(C_HIGHLIGHT, curses.COLOR_YELLOW, -1)
        curses.init_pair(C_SELECTED,  curses.COLOR_BLACK,  curses.COLOR_CYAN)
        curses.init_pair(C_SEL_HI,    curses.COLOR_YELLOW, curses.COLOR_CYAN)
        curses.init_pair(C_STATUSBAR, curses.COLOR_BLACK,  curses.COLOR_WHITE)
        curses.init_pair(C_ARROW,     curses.COLOR_GREEN,  -1)
    except curses.error:
        pass
    curses.curs_set(1)
    stdscr.keypad(True)

    query = initial_query
    matches = filter_history(history, query)
    cursor = 0
    scroll = 0

    while True:
        max_y, _ = stdscr.getmaxyx()
        list_height = max(1, max_y - 2)
        if cursor < scroll:
            scroll = cursor
        elif cursor >= scroll + list_height:
            scroll = cursor - list_height + 1

        draw(stdscr, query, matches, cursor, scroll)

        try:
            ch = stdscr.get_wch()
        except KeyboardInterrupt:
            return None
        except curses.error:
            continue

        if ch in ("\x1b", "\x07"):  # Esc, Ctrl-G
            return None
        if ch in ("\n", "\r"):
            if matches:
                return matches[cursor]
            return None
        if ch in ("\x7f", "\b", curses.KEY_BACKSPACE):
            query = query[:-1]
            matches = filter_history(history, query)
            cursor = 0
            scroll = 0
            continue
        if ch == "\x15":  # Ctrl-U
            query = ""
            matches = filter_history(history, query)
            cursor = 0
            scroll = 0
            continue
        if ch == "\x17":  # Ctrl-W: delete previous word
            stripped = query.rstrip()
            i = stripped.rfind(" ")
            query = stripped[:i + 1] if i >= 0 else ""
            matches = filter_history(history, query)
            cursor = 0
            scroll = 0
            continue
        if ch in (curses.KEY_UP, "\x10"):  # Up or Ctrl-P
            if matches:
                cursor = (cursor - 1) % len(matches)
            continue
        if ch in (curses.KEY_DOWN, "\x0e"):  # Down or Ctrl-N
            if matches:
                cursor = (cursor + 1) % len(matches)
            continue
        if ch == curses.KEY_PPAGE:
            cursor = max(0, cursor - list_height)
            continue
        if ch == curses.KEY_NPAGE:
            if matches:
                cursor = min(len(matches) - 1, cursor + list_height)
            continue
        if isinstance(ch, str) and ch.isprintable():
            query += ch
            matches = filter_history(history, query)
            cursor = 0
            scroll = 0
            continue


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="")
    parser.add_argument("--output", required=True, help="file to write selection to")
    parser.add_argument(
        "--history",
        default=os.environ.get("HISTFILE", str(Path.home() / ".bash_history")),
    )
    args = parser.parse_args()

    history = load_history(Path(args.history))
    if not history:
        sys.stderr.write("history is empty\n")
        return 1

    # Force curses to use the controlling terminal so the picker still works
    # when stdout/stderr are redirected by the caller.
    tty_in = open("/dev/tty", "rb")
    tty_out = open("/dev/tty", "wb")
    os.dup2(tty_in.fileno(), 0)
    os.dup2(tty_out.fileno(), 1)

    selection = curses.wrapper(run, history, args.query)

    if selection is None:
        return 1
    Path(args.output).write_text(selection)
    return 0


if __name__ == "__main__":
    sys.exit(main())
