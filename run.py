#!/usr/bin/env python3
"""Entry point. Run with: python run.py [--company NAME]"""

import sys

try:
    import pyperclip  # noqa: F401
except ImportError:
    print("Missing dependency 'pyperclip'. Install it with:\n    pip install -r requirements.txt")
    sys.exit(1)

try:
    import selenium  # noqa: F401
except ImportError:
    print("Missing dependency 'selenium'. Install it with:\n    pip install -r requirements.txt")
    sys.exit(1)

from core.app import main

if __name__ == "__main__":
    main()
