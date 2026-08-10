"""Command-line argument parsing."""

import argparse


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
