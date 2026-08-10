"""Console rendering and keyboard input for the interactive review loop."""

import os

from .models import Connection

if os.name == "nt":
    import msvcrt
else:
    msvcrt = None  # non-Windows fallback uses input() instead of single-keypress reads


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def wait_for_key(valid_keys) -> str:
    """Blocking single-keypress read on Windows; falls back to input() elsewhere."""
    while True:
        if msvcrt:
            raw = msvcrt.getch()
            try:
                ch = raw.decode("utf-8", errors="ignore").upper()
            except Exception:
                continue
        else:
            typed = input("Press S (sent) / K (skip) / Q (quit) then Enter: ").strip().upper()
            ch = typed[:1] if typed else ""
        if ch in valid_keys:
            return ch


def print_progress(
    idx: int, total: int, connection: Connection, message: str, filter_label: str = ""
) -> None:
    clear_screen()
    print("=" * 64)
    print(f"Progress: {idx} / {total}" + (f"   |   Filter: {filter_label}" if filter_label else ""))
    print("=" * 64)
    print(f"Name:     {connection.name}")
    print(f"Company:  {connection.company}")
    print(f"Position: {connection.position}")
    print(f"URL:      {connection.url or '(no URL on file)'}")
    print("-" * 64)
    print("Message:")
    print(message)
    print("-" * 64)
    print("Message copied to clipboard. Paste it manually and send it yourself.")
    print()
    print("[ S ] Sent -> Next     [ K ] Skip     [ Q ] Quit")
