"""Read/write sent_log.csv - the resumable history of processed connections."""

import csv
import datetime as dt
import os
from typing import Dict

from .models import Connection

LOG_COLUMNS = ["timestamp", "key", "name", "company", "position", "url", "status"]


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
                writer.writerow(LOG_COLUMNS)
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
