"""Launches a Selenium-controlled Chrome window with a persistent profile.

No credentials are ever handled here - login is always done manually
by the human in the real browser window.
"""

import os
import sys

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import WebDriverException


def start_browser(profile_dir: str) -> "webdriver.Chrome":
    os.makedirs(profile_dir, exist_ok=True)
    options = Options()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--start-maximized")
    try:
        return webdriver.Chrome(options=options)
    except WebDriverException as e:
        print("ERROR: Could not start Chrome via Selenium.")
        print(str(e))
        print(
            "\nMake sure Google Chrome is installed and that no other process is "
            "already using the CHROME_PROFILE_DIR folder."
        )
        sys.exit(1)
