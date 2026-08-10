"""Building the personalized outreach message from MESSAGE_TEMPLATE."""

import sys

from .models import Connection


def build_message(template: str, connection: Connection) -> str:
    return template.format(
        name=connection.name,
        first_name=connection.first_name,
        last_name=connection.last_name,
        company=connection.company,
        position=connection.position,
    )


def validate_template(template: str) -> None:
    """Fails fast on startup if MESSAGE_TEMPLATE has a bad placeholder."""
    dummy = Connection(
        first_name="Test",
        last_name="User",
        company="TestCo",
        position="Tester",
        url="https://www.linkedin.com/in/test",
    )
    try:
        build_message(template, dummy)
    except KeyError as e:
        print(f"ERROR: MESSAGE_TEMPLATE uses an unsupported placeholder: {{{e.args[0]}}}")
        print("Supported placeholders: {name} {first_name} {last_name} {company} {position}")
        sys.exit(1)
    except (IndexError, ValueError) as e:
        print(f"ERROR: MESSAGE_TEMPLATE is not a valid template string: {e}")
        sys.exit(1)
