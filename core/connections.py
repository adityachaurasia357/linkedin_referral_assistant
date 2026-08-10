"""Reading Connections.csv and letting the user filter it by company."""

import csv
import sys
from collections import Counter
from typing import Dict, List, Optional, Tuple

from . import config
from .models import Connection


def load_connections(path: str) -> List[Connection]:
    """
    Parses a LinkedIn 'Connections.csv' export.

    LinkedIn's export includes a few explanatory 'Notes:' lines before
    the real header row, so we scan for the header row (the one
    containing 'First Name' and 'Last Name') instead of assuming it's
    line 1.
    """
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            raw_lines = f.readlines()
    except OSError as e:
        print(f"ERROR: Could not read connections file: {e}")
        sys.exit(1)

    header_idx = None
    for i, line in enumerate(raw_lines):
        if "First Name" in line and "Last Name" in line:
            header_idx = i
            break

    if header_idx is None:
        print("ERROR: Could not find a header row containing 'First Name' / 'Last Name'.")
        print("Make sure this is an unmodified LinkedIn 'Connections.csv' export.")
        sys.exit(1)

    reader = csv.DictReader(raw_lines[header_idx:])

    connections: List[Connection] = []
    seen_keys = set()
    skipped_rows = 0

    for row in reader:
        norm = {(k or "").strip(): (v or "").strip() for k, v in row.items() if k}

        first_name = norm.get("First Name", "")
        last_name = norm.get("Last Name", "")
        company = norm.get("Company", "")
        position = norm.get("Position", "")
        url = norm.get("URL", "")

        if not first_name and not last_name and not url:
            continue  # blank/malformed row

        conn = Connection(
            first_name=first_name or "there",
            last_name=last_name,
            company=company or config.DEFAULT_COMPANY_TEXT,
            position=position or config.DEFAULT_POSITION_TEXT,
            url=url,
        )

        if conn.key in seen_keys:
            skipped_rows += 1
            continue
        seen_keys.add(conn.key)
        connections.append(conn)

    if skipped_rows:
        print(f"Note: skipped {skipped_rows} duplicate row(s) in the connections file.")

    return connections


def get_company_counts(connections: List[Connection]) -> List[Tuple[str, int]]:
    """
    Groups connections by company (case-insensitive) and returns
    (display_name, count) pairs sorted by most-common first.
    Connections with no real company on file are excluded.
    """
    counts: Counter = Counter()
    display_name: Dict[str, str] = {}
    for c in connections:
        company = c.company.strip()
        if not company or company == config.DEFAULT_COMPANY_TEXT:
            continue
        key = company.lower()
        counts[key] += 1
        display_name.setdefault(key, company)
    pairs = [(display_name[key], n) for key, n in counts.items()]
    pairs.sort(key=lambda p: (-p[1], p[0].lower()))
    return pairs


def filter_by_company(connections: List[Connection], search_term: str) -> List[Connection]:
    """Case-insensitive substring match against each connection's company."""
    term = search_term.strip().lower()
    if not term:
        return connections
    return [c for c in connections if term in c.company.lower()]


def prompt_company_filter(
    connections: List[Connection], cli_company: Optional[str] = None
) -> List[Connection]:
    """
    Lets the user narrow the list down to a single company, in the
    friendliest way possible for someone who has never used a
    terminal before:
      - If --company was passed on the command line, filter instantly
        and skip the menu (fastest path, for repeat/power users).
      - Otherwise show a numbered list of their most common companies
        (just press a number key) with a free-text search fallback
        (just type a company name, e.g. "phonepe").
      - Pressing Enter or typing 0 means "no filter, show everyone".
    """
    if cli_company:
        matches = filter_by_company(connections, cli_company)
        print(f'Filtering by company "{cli_company}" -> {len(matches)} match(es) found.')
        if not matches:
            print("No matches found. Continuing with ALL connections instead.\n")
            return connections
        print()
        return matches

    company_counts = get_company_counts(connections)

    print("=" * 64)
    print("FILTER BY COMPANY (optional)")
    print("=" * 64)

    if not company_counts:
        print("No company info was found in your connections file, so there's")
        print("nothing to filter by. Continuing with everyone.\n")
        return connections

    shown = company_counts[:15]
    print("You can go through everyone, or narrow it down to just one company.\n")
    print("Your most common companies:")
    for i, (name, count) in enumerate(shown, start=1):
        print(f"   {i:>2}. {name}  ({count})")
    print(f"    0. Show ALL connections (no filter)")
    print()
    print('Type a NUMBER above, OR type any company name to search for it')
    print('(e.g. "phonepe"), then press Enter. Just press Enter for everyone.')

    while True:
        choice = input("\n> ").strip()

        if choice == "" or choice == "0":
            print("\nNo filter applied - going through everyone.\n")
            return connections

        if choice.isdigit():
            num = int(choice)
            if 1 <= num <= len(shown):
                name = shown[num - 1][0]
                matches = filter_by_company(connections, name)
                print(f'\nSelected "{name}" -> {len(matches)} connection(s).\n')
                return matches
            print(f"Please type a number between 0 and {len(shown)}, or a company name.")
            continue

        matches = filter_by_company(connections, choice)
        if not matches:
            print(f'No connections found matching "{choice}". Try again, or press Enter for everyone.')
            continue

        distinct_companies = sorted({c.company for c in matches}, key=str.lower)
        if len(distinct_companies) == 1:
            print(f'\nFound "{distinct_companies[0]}" -> {len(matches)} connection(s).\n')
            return matches

        print(f'\n"{choice}" matched {len(matches)} connection(s) across these companies:')
        for name in distinct_companies[:10]:
            n = sum(1 for c in matches if c.company == name)
            print(f"   - {name} ({n})")
        if len(distinct_companies) > 10:
            print(f"   ...and {len(distinct_companies) - 10} more")
        confirm = input(f"\nUse all {len(matches)} of these? (Y/N): ").strip().upper()
        if confirm == "Y":
            print()
            return matches
        print("Okay, let's try again.")
