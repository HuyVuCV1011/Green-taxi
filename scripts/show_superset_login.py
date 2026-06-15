"""Print the local Superset URL and admin username/password on explicit request."""

from __future__ import annotations

from pathlib import Path

from scripts.apply_warehouse_ddl import load_dotenv


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    import os

    load_dotenv(ROOT / ".env.superset")
    print(f"URL: http://localhost:{os.environ.get('SUPERSET_PORT', '8088')}")
    print(f"Username: {os.environ['SUPERSET_ADMIN_USERNAME']}")
    print(f"Password: {os.environ['SUPERSET_ADMIN_PASSWORD']}")


if __name__ == "__main__":
    main()
