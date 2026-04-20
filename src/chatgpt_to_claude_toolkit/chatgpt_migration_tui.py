#!/usr/bin/env python3
from __future__ import annotations

import curses
import json
import textwrap
from pathlib import Path
from typing import Any

from .migration_core import collect_memory_candidates, conversation_to_markdown, dedupe_memory_items, estimate_tokens, infer_topics, parse_conversations, read_conversations_json, search_conversations, summarise_conversation, ts_to_iso

HELP_TEXT = [
    "Tab pane | ↑↓ / jk move | Space toggle | / search | a all | n none | s save | q quit",
    "e edit memory item | t cycle sort | g jump to index | p preview final export | mouse click toggle",
]


class PaneItem:
    def __init__(self, key: str, label: str, preview: str, selected: bool = True, meta: dict[str, Any] | None = None):
        self.key = key
        self.label = label
        self.preview = preview
        self.selected = selected
        self.meta = meta or {}


class Pane:
    def __init__(self, name: str, items: list[PaneItem]):
        self.name = name
        self.items = items
        self.filtered = list(range(len(items)))
        self.cursor = 0
        self.scroll = 0
        self.query = ""
        self.sort_mode = "default"

    def apply_filter(self) -> None:
        q = self.query.lower().strip()
        if not q:
            self.filtered = list(range(len(self.items)))
        else:
            self.filtered = [i for i, item in enumerate(self.items) if q in item.label.lower() or q in item.preview.lower()]
        self.cursor = min(self.cursor, max(0, len(self.filtered) - 1))
        self.scroll = 0

    def cycle_sort(self) -> None:
        order = ["default", "selected", "alpha", "size"]
        self.sort_mode = order[(order.index(self.sort_mode) + 1) % len(order)]
        if self.sort_mode == "default":
            self.items.sort(key=lambda i: int(i.key) if str(i.key).isdigit() else str(i.key))
        elif self.sort_mode == "selected":
            self.items.sort(key=lambda i: (not i.selected, i.label.lower()))
        elif self.sort_mode == "alpha":
            self.items.sort(key=lambda i: i.label.lower())
        else:
            self.items.sort(key=lambda i: -(i.meta.get("sort_size") or len(i.preview)))
        self.apply_filter()

    def current_item(self) -> PaneItem | None:
        if not self.filtered:
            return None
        return self.items[self.filtered[self.cursor]]


class App:
    def __init__(self, export_zip: Path, output_file: Path):
        raw = read_conversations_json(export_zip)
        convs = parse_conversations(raw)
        memories = dedupe_memory_items(collect_memory_candidates(convs))
        topics = infer_topics(convs)
        self.export_zip = export_zip
        self.output_file = output_file
        self.preview_final = False
        self.status = "Ready"

        conv_items = []
        for i, conv in enumerate(convs, start=1):
            final_md = conversation_to_markdown(conv)
            conv_items.append(PaneItem(str(conv.source_index), f"[{ts_to_iso(conv.create_time) or 'unknown'}] {conv.title} ({len(conv.messages)} msgs)", summarise_conversation(conv), True, {"final": final_md, "sort_size": estimate_tokens(final_md)}))

        mem_items = []
        for i, mem in enumerate(memories, start=1):
            raw_preview = "\n\n".join(mem.examples) if mem.examples else mem.text
            final = f"[{mem.first_seen or 'unknown-date'}] - {mem.text}"
            flags = f" flags={','.join(mem.sensitivity_flags)}" if mem.sensitivity_flags else ""
            label = f"[{mem.category}] conf={mem.confidence} x{mem.count}{flags} {mem.text}"
            meta = {"memory_text": mem.text, "examples": mem.examples, "final": final, "sort_size": mem.count, "confidence": mem.confidence, "contradictions": mem.contradictions, "rationale": mem.rationale}
            mem_items.append(PaneItem(str(i), label, raw_preview, True, meta))

        topic_items = []
        for name in sorted(topics):
            preview = "\n".join(f"- {c.title}" for c in topics[name][:25])
            topic_items.append(PaneItem(name, f"{name} ({len(topics[name])} conversations)", preview, True, {"final": preview, "sort_size": len(topics[name])}))

        self.panes = [Pane("Conversations", conv_items), Pane("Memory", mem_items), Pane("Topics", topic_items)]
        self.active = 0
        for pane in self.panes:
            pane.apply_filter()

    def active_pane(self) -> Pane:
        return self.panes[self.active]

    def prompt(self, stdscr, label: str) -> str:
        curses.echo()
        h, w = stdscr.getmaxyx()
        stdscr.addstr(h - 2, 0, " " * (w - 1))
        stdscr.addstr(h - 2, 0, label[:w - 1])
        stdscr.refresh()
        raw = stdscr.getstr(h - 2, min(len(label), w - 2), max(1, w - len(label) - 2))
        curses.noecho()
        return raw.decode("utf-8", errors="ignore")

    def save(self) -> None:
        data = {
            "selected_conversations": [item.key for item in self.panes[0].items if item.selected],
            "selected_memory_items": [item.key for item in self.panes[1].items if item.selected],
            "selected_topics": [item.key for item in self.panes[2].items if item.selected],
            "edited_memory_items": {item.key: item.meta.get("memory_text") for item in self.panes[1].items if item.meta.get("edited")},
        }
        self.output_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self.status = f"Saved {self.output_file}"

    def wrap(self, text: str, width: int) -> list[str]:
        out = []
        for line in text.splitlines() or [""]:
            out.extend(textwrap.wrap(line, width=max(10, width), replace_whitespace=False) or [""])
        return out

    def draw_help(self, stdscr, y: int, w: int) -> None:
        for i, line in enumerate(HELP_TEXT):
            if y + i < curses.LINES:
                stdscr.addstr(y + i, 0, line[:w - 1])

    def draw(self, stdscr) -> None:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        left_w = max(34, min(64, w // 2))
        pane = self.active_pane()
        x = 0
        for i, p in enumerate(self.panes):
            title = f" {p.name} ({sum(1 for it in p.items if it.selected)}/{len(p.items)})[{p.sort_mode}] "
            stdscr.addstr(0, x, title[: max(1, w - x - 1)], curses.A_REVERSE if i == self.active else curses.A_NORMAL)
            x += len(title)
        stdscr.addstr(1, 0, f"Search: {pane.query or '/'}   Preview: {'final export' if self.preview_final else 'review'}"[:w - 1])
        stdscr.hline(2, 0, ord('-'), w - 1)
        stdscr.vline(3, left_w, ord('|'), max(1, h - 7))

        visible_h = max(1, h - 8)
        if pane.cursor < pane.scroll:
            pane.scroll = pane.cursor
        if pane.cursor >= pane.scroll + visible_h:
            pane.scroll = pane.cursor - visible_h + 1
        visible = pane.filtered[pane.scroll:pane.scroll + visible_h]
        for row, idx in enumerate(visible, start=3):
            item = pane.items[idx]
            text = f"[{'x' if item.selected else ' '}] {item.label}"
            stdscr.addstr(row, 0, text[:left_w - 1], curses.A_REVERSE if idx == pane.filtered[pane.cursor] else curses.A_NORMAL)

        current_item = pane.current_item()
        if current_item:
            rx = left_w + 2
            rw = max(10, w - rx - 1)
            if pane.name == "Memory" and not self.preview_final:
                half = max(10, rw // 2 - 1)
                stdscr.addstr(2, rx, "Source example(s)"[:half])
                stdscr.addstr(2, rx + half + 2, "Generated memory"[:half])
                stdscr.vline(3, rx + half, ord('|'), visible_h)
                left_lines = self.wrap(current_item.preview, half - 1)
                right_text = str(current_item.meta.get("memory_text", current_item.label))
                extras = []
                if current_item.meta.get("rationale"):
                    extras.append(f"rationale: {current_item.meta['rationale']}")
                if current_item.meta.get("contradictions"):
                    extras.append("possible contradictions:")
                    extras.extend(f"- {x}" for x in current_item.meta["contradictions"])
                right_lines = self.wrap(right_text + ("\n\n" + "\n".join(extras) if extras else ""), half - 1)
                for i in range(min(visible_h, max(len(left_lines), len(right_lines)))):
                    if i < len(left_lines):
                        stdscr.addstr(3 + i, rx, left_lines[i][:half - 1])
                    if i < len(right_lines):
                        stdscr.addstr(3 + i, rx + half + 2, right_lines[i][:half - 1])
            else:
                body = str(current_item.meta.get("final", current_item.preview)) if self.preview_final else current_item.preview
                for i, line in enumerate(self.wrap(body, rw)[:visible_h]):
                    stdscr.addstr(3 + i, rx, line[:rw])

        stdscr.hline(h - 4, 0, ord('-'), w - 1)
        self.draw_help(stdscr, h - 3, w)
        stdscr.addstr(h - 1, 0, self.status[:w - 1])
        stdscr.refresh()

    def handle_click(self, my: int, h: int) -> None:
        pane = self.active_pane()
        visible_h = max(1, h - 8)
        if my < 3 or my >= 3 + visible_h:
            return
        row = my - 3
        idx = pane.scroll + row
        if 0 <= idx < len(pane.filtered):
            pane.cursor = idx
            current = pane.current_item()
            if current is not None:
                current.selected = not current.selected

    def run(self, stdscr) -> int:
        curses.curs_set(0)
        stdscr.keypad(True)
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        while True:
            self.draw(stdscr)
            ch = stdscr.getch()
            pane = self.active_pane()
            if ch in (ord('q'), 27):
                return 0
            elif ch == 9:
                self.active = (self.active + 1) % len(self.panes)
            elif ch in (curses.KEY_UP, ord('k')):
                pane.cursor = max(0, pane.cursor - 1)
            elif ch in (curses.KEY_DOWN, ord('j')):
                pane.cursor = min(max(0, len(pane.filtered) - 1), pane.cursor + 1)
            elif ch == ord(' '):
                current = pane.current_item()
                if current is not None:
                    current.selected = not current.selected
            elif ch == ord('a'):
                for idx in (pane.filtered if pane.query else range(len(pane.items))):
                    pane.items[idx].selected = True
            elif ch == ord('n'):
                for idx in (pane.filtered if pane.query else range(len(pane.items))):
                    pane.items[idx].selected = False
            elif ch == ord('/'):
                pane.query = self.prompt(stdscr, "Search: ")
                if pane.name == "Conversations" and pane.query.strip() and not any(pane.query.lower() in it.label.lower() for it in pane.items):
                    # semantic/fuzzy refill for conversation pane
                    raw = read_conversations_json(self.export_zip)
                    convs = search_conversations(parse_conversations(raw), pane.query, limit=50)
                    pane.items = [PaneItem(str(c.source_index), f"[{ts_to_iso(c.create_time) or 'unknown'}] {c.title} ({len(c.messages)} msgs)", summarise_conversation(c), True, {"final": conversation_to_markdown(c), "sort_size": estimate_tokens(conversation_to_markdown(c))}) for c in convs]
                pane.apply_filter()
                self.status = f"Filtered {pane.name}"
            elif ch == ord('t'):
                pane.cycle_sort()
                self.status = f"Sort: {pane.sort_mode}"
            elif ch == ord('g'):
                raw = self.prompt(stdscr, "Jump to index: ").strip()
                if raw.isdigit():
                    pane.cursor = min(max(int(raw) - 1, 0), max(0, len(pane.filtered) - 1))
            elif ch == ord('p'):
                self.preview_final = not self.preview_final
            elif ch == ord('e') and pane.name == "Memory":
                current = pane.current_item()
                if current is not None:
                    new_text = self.prompt(stdscr, "Edit memory text: ").strip()
                    if new_text:
                        current.meta["memory_text"] = new_text
                        current.meta["final"] = new_text
                        current.meta["edited"] = True
                        current.label = f"[edited] {new_text}"
                        self.status = "Edited memory item"
            elif ch == ord('s'):
                self.save()
            elif ch == curses.KEY_MOUSE:
                try:
                    _, _, my, _, state = curses.getmouse()
                    if state & curses.BUTTON1_CLICKED:
                        self.handle_click(my, curses.LINES)
                    elif state & getattr(curses, "BUTTON4_PRESSED", 0):
                        pane.cursor = max(0, pane.cursor - 3)
                    elif state & getattr(curses, "BUTTON5_PRESSED", 0):
                        pane.cursor = min(max(0, len(pane.filtered) - 1), pane.cursor + 3)
                except curses.error:
                    pass


def main() -> int:
    import sys
    if len(sys.argv) != 3:
        print("Usage: python chatgpt_migration_tui.py <chatgpt-export.zip> <selection.json>")
        return 2
    return curses.wrapper(App(Path(sys.argv[1]), Path(sys.argv[2])).run)


if __name__ == "__main__":
    raise SystemExit(main())
