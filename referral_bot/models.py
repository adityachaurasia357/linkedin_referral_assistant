"""Domain model shared across the package."""

from dataclasses import dataclass


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
