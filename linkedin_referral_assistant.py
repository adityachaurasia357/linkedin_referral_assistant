#!/usr/bin/env python3
"""
LinkedIn Referral Assistant
============================

A semi-automated helper for sending personalized referral outreach
messages to YOUR OWN LinkedIn connections (from your official
"Connections.csv" export).

WHAT THIS SCRIPT DOES
----------------------
1. Launches Chrome with a dedicated, persistent Chrome profile so you
   only need to log into LinkedIn once (manually).
2. Loads your connections from your LinkedIn "Connections.csv" export.
3. Steps through connections one at a time:
     - Builds a personalized message from MESSAGE_TEMPLATE below.
     - Opens that connection's LinkedIn profile in the browser.
     - Copies the personalized message to your clipboard.
     - Waits for YOU to manually open the message box, paste, review,
       and click Send yourself.
     - Waits for you to press a key to confirm what happened, then
       moves to the next connection.
4. Keeps a persistent sent_log.csv so re-running the script after a
   restart automatically skips people you already contacted or
   skipped.

WHAT THIS SCRIPT DELIBERATELY DOES NOT DO
------------------------------------------
- It never stores, reads, or asks for your LinkedIn username/password.
  You log in manually, once, in the real Chrome window.
- It never clicks LinkedIn's "Send" button or submits any message on
  your behalf. Sending is always a manual, human action.
- It does not try to detect, defeat, or evade CAPTCHAs, rate limits,
  or any LinkedIn anti-automation/anti-bot systems. If LinkedIn shows
  you a CAPTCHA or security checkpoint, solve it yourself in the
  browser window like normal.
- It does not scrape LinkedIn search results or any profiles beyond
  the people already listed in your own connections export.
- It does not add "stealth" browser flags or try to disguise the
  browser as non-automated. It's a plain Selenium-controlled Chrome
  window that you are expected to interact with directly.

Because outreach at scale can look like spam and LinkedIn actively
restricts accounts that message too many people too quickly, you are
responsible for pacing yourself sensibly (e.g. a few dozen messages a
day, not hundreds in one sitting) and for the content you send.

------------------------------------------------------------------
INSTALLATION
------------------------------------------------------------------
1. Install Python 3.10 or later (Windows).
2. Install Google Chrome (a normal, current version).
3. Install the two required Python packages:

     pip install selenium pyperclip

   (Selenium 4.6+ ships "Selenium Manager", which downloads a
   matching chromedriver automatically the first time you run this
   script — you do not need to install chromedriver separately.)

------------------------------------------------------------------
GETTING YOUR CONNECTIONS.CSV
------------------------------------------------------------------
LinkedIn -> click your profile photo -> "Settings & Privacy" ->
"Data privacy" -> "Get a copy of your data" -> select "Connections"
-> request archive -> download the ZIP LinkedIn emails you -> unzip
it -> you'll find "Connections.csv" inside. Point CONNECTIONS_FILE
below at that file. Do not hand-edit the header row LinkedIn gives
you; this script auto-detects it even with LinkedIn's export notes
at the top of the file.

------------------------------------------------------------------
USAGE
------------------------------------------------------------------
1. Edit the CONFIGURATION block below (paths + message template).
2. Run:

     python linkedin_referral_assistant.py

3. Right after loading your connections, you'll be shown a simple
   menu where you can optionally filter to just ONE company (e.g.
   type "phonepe" or pick it from the numbered list). Press Enter /
   type 0 to skip filtering and go through everyone instead.

   TIP for power users: you can skip this menu entirely by running:
       python linkedin_referral_assistant.py --company phonepe
4. A Chrome window opens on the LinkedIn login page. Log in
   manually (solve any 2FA/CAPTCHA LinkedIn shows you), then come
   back to the terminal and press Enter to continue.
5. For each connection the script shows you their info and a
   ready-to-send message, and copies that message to your
   clipboard. Their profile is opened in the browser. You:
     - Click "Message" on their profile yourself.
     - Paste (Ctrl+V) the message.
     - Edit anything you want.
     - Click LinkedIn's Send button yourself.
     - Come back to the terminal and press:
         S = you sent it (logged as "sent", moves to next person)
         K = skip this person (logged as "skipped", moves to next)
         Q = quit now (progress so far is already saved)
5. Re-running the script later automatically resumes where you left
   off, using sent_log.csv.

------------------------------------------------------------------
"""

import argparse
import csv
import datetime as dt
import os
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    import pyperclip
except ImportError:
    print("Missing dependency 'pyperclip'. Install it with:\n    pip install pyperclip")
    sys.exit(1)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.common.exceptions import WebDriverException
except ImportError:
    print("Missing dependency 'selenium'. Install it with:\n    pip install selenium")
    sys.exit(1)

if os.name == "nt":
    import msvcrt
else:
    msvcrt = None  # Non-Windows fallback uses input() instead of single-keypress reads


# ==================================================================
# CONFIGURATION - edit these values before running
# ==================================================================

# Path to your LinkedIn "Connections.csv" export (see instructions above).
CONNECTIONS_FILE = r"C:\Users\yourname\Downloads\connections.csv"

# Folder used as a DEDICATED, PERSISTENT Chrome profile. LinkedIn
# session/cookies live here after your first manual login, so you
# won't have to log in again on future runs. Use a folder that isn't
# your everyday Chrome profile.
CHROME_PROFILE_DIR = r"C:\LinkedInReferralAssistant\ChromeProfile"

# Where processed-connection history is kept. Safe to keep across runs.
SENT_LOG_FILE = "sent_log.csv"

# How long to wait (seconds) after navigating to a profile page for
# it to finish loading before showing it to you.
PAGE_LOAD_WAIT_SECONDS = 2.5

# Personalized message template. Supported placeholders:
#   {name}        full name, e.g. "Rahul Sharma"
#   {first_name}  e.g. "Rahul"
#   {last_name}   e.g. "Sharma"
#   {company}     current company if known, else a generic fallback
#   {position}    current position/title if known, else a generic fallback
MESSAGE_TEMPLATE = """Hi {first_name},

Hope you're doing well! I'm currently exploring software
engineering opportunities and noticed that {company} has
some relevant openings.

Would you be comfortable referring me for a suitable role?
I'd really appreciate your help.

Thanks!
"""

# Used in the message when a connection's CSV row has no company/position.
DEFAULT_COMPANY_TEXT = "your company"
DEFAULT_POSITION_TEXT = "your role"

# ==================================================================
# END CONFIGURATION
# ==================================================================


@dataclass
class Connection:
    first_name: str
    last_name: str
    company: str
    position: str
    url: str

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def key(self) -> str:
        """Stable identifier used for dedup and the sent log."""
        if self.url:
            return self.url.strip().lower().rstrip("/")
        return f"name:{self.name.strip().lower()}"


def validate_paths() -> None:
    errors = []
    if not os.path.isfile(CONNECTIONS_FILE):
        errors.append(f"Connections CSV not found: {CONNECTIONS_FILE}")
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        print("\nFix the paths in the CONFIGURATION block at the top of this script.")
        sys.exit(1)


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
            company=company or DEFAULT_COMPANY_TEXT,
            position=position or DEFAULT_POSITION_TEXT,
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
        if not company or company == DEFAULT_COMPANY_TEXT:
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


def validate_template() -> None:
    dummy = Connection(
        first_name="Test",
        last_name="User",
        company="TestCo",
        position="Tester",
        url="https://www.linkedin.com/in/test",
    )
    try:
        build_message(MESSAGE_TEMPLATE, dummy)
    except KeyError as e:
        print(f"ERROR: MESSAGE_TEMPLATE uses an unsupported placeholder: {{{e.args[0]}}}")
        print("Supported placeholders: {name} {first_name} {last_name} {company} {position}")
        sys.exit(1)
    except (IndexError, ValueError) as e:
        print(f"ERROR: MESSAGE_TEMPLATE is not a valid template string: {e}")
        sys.exit(1)


def build_message(template: str, connection: Connection) -> str:
    return template.format(
        name=connection.name,
        first_name=connection.first_name,
        last_name=connection.last_name,
        company=connection.company,
        position=connection.position,
    )


def load_sent_log(path: str) -> Dict[str, str]:
    done: Dict[str, str] = {}
    if not os.path.isfile(path):
        return done
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row.get("key") or "").strip().lower()
                if key:
                    done[key] = row.get("status", "")
    except OSError as e:
        print(f"WARNING: Could not read {path}: {e}. Starting with empty history.")
    return done


def append_sent_log(path: str, connection: Connection, status: str) -> None:
    file_exists = os.path.isfile(path)
    try:
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(
                    ["timestamp", "key", "name", "company", "position", "url", "status"]
                )
            writer.writerow(
                [
                    dt.datetime.now().isoformat(timespec="seconds"),
                    connection.key,
                    connection.name,
                    connection.company,
                    connection.position,
                    connection.url,
                    status,
                ]
            )
    except OSError as e:
        print(f"WARNING: Could not write to {path}: {e}")


def start_browser() -> "webdriver.Chrome":
    os.makedirs(CHROME_PROFILE_DIR, exist_ok=True)
    options = Options()
    options.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")
    options.add_argument("--start-maximized")
    try:
        driver = webdriver.Chrome(options=options)
    except WebDriverException as e:
        print("ERROR: Could not start Chrome via Selenium.")
        print(str(e))
        print(
            "\nMake sure Google Chrome is installed and that no other process is "
            "already using the CHROME_PROFILE_DIR folder."
        )
        sys.exit(1)
    return driver


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


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LinkedIn Referral Assistant - semi-automated referral outreach helper."
    )
    parser.add_argument(
        "--company",
        "-c",
        default=None,
        metavar="NAME",
        help=(
            "Skip the interactive filter menu and jump straight to connections "
            'at this company (e.g. --company phonepe). Fastest way to run.'
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("LinkedIn Referral Assistant")
    print("-" * 64)

    validate_template()
    validate_paths()

    all_connections = load_connections(CONNECTIONS_FILE)
    if not all_connections:
        print("No usable rows found in the connections CSV. Nothing to do.")
        sys.exit(0)

    print(f"Loaded {len(all_connections)} connection(s) from: {CONNECTIONS_FILE}\n")

    connections = prompt_company_filter(all_connections, args.company)
    if not connections:
        print("No connections match that filter. Nothing to do.")
        sys.exit(0)

    if len(connections) == len(all_connections):
        filter_label = "ALL connections (no filter)"
    else:
        matched_companies = sorted({c.company for c in connections}, key=str.lower)
        filter_label = ", ".join(matched_companies[:5])
        if len(matched_companies) > 5:
            filter_label += f", +{len(matched_companies) - 5} more"

    sent_log = load_sent_log(SENT_LOG_FILE)
    pending = [c for c in connections if c.key not in sent_log]
    total = len(connections)
    already_done = total - len(pending)

    print("=" * 64)
    print(f"Filter:                        {filter_label}")
    print(f"Connections in this run:       {total}")
    print(f"Already processed previously:  {already_done}")
    print(f"Remaining to process this run: {len(pending)}")

    if not pending:
        print("\nEverybody in your connections file has already been processed.")
        print(f"Delete or edit {SENT_LOG_FILE} if you want to reprocess someone.")
        sys.exit(0)

    input("\nPress Enter to launch Chrome...")

    driver = start_browser()

    try:
        driver.get("https://www.linkedin.com/login")
    except WebDriverException as e:
        print(f"WARNING: Could not navigate to LinkedIn login page: {e}")

    print()
    print("A Chrome window has opened. Please log into LinkedIn manually")
    print("(this script never sees or stores your username/password).")
    input("Once you're fully logged in, press Enter here to continue...")

    idx = already_done
    try:
        for connection in pending:
            idx += 1

            try:
                message = build_message(MESSAGE_TEMPLATE, connection)
            except KeyError as e:
                print(f"Template error ({e}) for {connection.name}; skipping.")
                append_sent_log(SENT_LOG_FILE, connection, "template_error")
                continue

            if connection.url:
                try:
                    driver.get(connection.url)
                    time.sleep(PAGE_LOAD_WAIT_SECONDS)
                except WebDriverException as e:
                    print(f"Could not open profile for {connection.name}: {e}")
            else:
                print(f"No profile URL on file for {connection.name}; browser not navigated.")

            try:
                pyperclip.copy(message)
            except Exception as e:
                print(f"WARNING: Could not copy message to clipboard: {e}")

            print_progress(idx, total, connection, message, filter_label)

            key = wait_for_key({"S", "K", "Q"})

            if key == "S":
                append_sent_log(SENT_LOG_FILE, connection, "sent")
            elif key == "K":
                append_sent_log(SENT_LOG_FILE, connection, "skipped")
            elif key == "Q":
                print("\nQuitting. Your progress has been saved to", SENT_LOG_FILE)
                break
    except KeyboardInterrupt:
        print("\nInterrupted. Your progress up to this point has been saved.")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    print("\nDone.")


if __name__ == "__main__":
    main()