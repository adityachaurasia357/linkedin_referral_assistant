"""Top-level orchestration for the LinkedIn Referral Assistant."""

import os
import sys
import time

import pyperclip
from selenium.common.exceptions import WebDriverException

from . import config
from .browser import start_browser
from .cli import parse_args
from .connections import load_connections, prompt_company_filter
from .messaging import build_message, validate_template
from .sent_log import append_sent_log, load_sent_log
from .ui import print_progress, wait_for_key


def validate_paths() -> None:
    if not os.path.isfile(config.CONNECTIONS_FILE):
        print(f"ERROR: Connections CSV not found: {config.CONNECTIONS_FILE}")
        print("\nFix the paths in linkedin_referral_assistant/config.py.")
        sys.exit(1)


def _build_filter_label(connections, all_connections) -> str:
    if len(connections) == len(all_connections):
        return "ALL connections (no filter)"
    matched_companies = sorted({c.company for c in connections}, key=str.lower)
    label = ", ".join(matched_companies[:5])
    if len(matched_companies) > 5:
        label += f", +{len(matched_companies) - 5} more"
    return label


def _run_review_loop(driver, pending, total, already_done, filter_label) -> None:
    idx = already_done
    for connection in pending:
        idx += 1

        try:
            message = build_message(config.MESSAGE_TEMPLATE, connection)
        except KeyError as e:
            print(f"Template error ({e}) for {connection.name}; skipping.")
            append_sent_log(config.SENT_LOG_FILE, connection, "template_error")
            continue

        if connection.url:
            try:
                driver.get(connection.url)
                time.sleep(config.PAGE_LOAD_WAIT_SECONDS)
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
            append_sent_log(config.SENT_LOG_FILE, connection, "sent")
        elif key == "K":
            append_sent_log(config.SENT_LOG_FILE, connection, "skipped")
        elif key == "Q":
            print("\nQuitting. Your progress has been saved to", config.SENT_LOG_FILE)
            break


def main() -> None:
    args = parse_args()

    print("LinkedIn Referral Assistant")
    print("-" * 64)

    validate_template(config.MESSAGE_TEMPLATE)
    validate_paths()

    all_connections = load_connections(config.CONNECTIONS_FILE)
    if not all_connections:
        print("No usable rows found in the connections CSV. Nothing to do.")
        sys.exit(0)

    print(f"Loaded {len(all_connections)} connection(s) from: {config.CONNECTIONS_FILE}\n")

    connections = prompt_company_filter(all_connections, args.company)
    if not connections:
        print("No connections match that filter. Nothing to do.")
        sys.exit(0)

    filter_label = _build_filter_label(connections, all_connections)

    sent_log = load_sent_log(config.SENT_LOG_FILE)
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
        print(f"Delete or edit {config.SENT_LOG_FILE} if you want to reprocess someone.")
        sys.exit(0)

    input("\nPress Enter to launch Chrome...")

    driver = start_browser(config.CHROME_PROFILE_DIR)

    try:
        driver.get("https://www.linkedin.com/login")
    except WebDriverException as e:
        print(f"WARNING: Could not navigate to LinkedIn login page: {e}")

    print()
    print("A Chrome window has opened. Please log into LinkedIn manually")
    print("(this script never sees or stores your username/password).")
    input("Once you're fully logged in, press Enter here to continue...")

    try:
        _run_review_loop(driver, pending, total, already_done, filter_label)
    except KeyboardInterrupt:
        print("\nInterrupted. Your progress up to this point has been saved.")
    finally:
        try:
            driver.quit()
        except Exception:
            pass

    print("\nDone.")
