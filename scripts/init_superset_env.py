"""Create an ignored .env.superset with strong local-only credentials."""

from __future__ import annotations

import secrets
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".env.superset"


def token(length: int = 36) -> str:
    return secrets.token_urlsafe(length)


def main() -> int:
    if TARGET.exists():
        print(f"{TARGET.name} already exists; left unchanged.")
        return 0

    content = f"""SUPERSET_PORT=8088
SUPERSET_SECRET_KEY={token(48)}

SUPERSET_METADATA_DB_NAME=superset_metadata
SUPERSET_METADATA_DB_USER=superset_metadata_app
SUPERSET_METADATA_DB_PASSWORD={token()}

SUPERSET_ADMIN_USERNAME=admin
SUPERSET_ADMIN_FIRSTNAME=Green
SUPERSET_ADMIN_LASTNAME=Taxi
SUPERSET_ADMIN_EMAIL=admin@greentaxi.local
SUPERSET_ADMIN_PASSWORD={token(24)}

SUPERSET_WAREHOUSE_HOST=postgres_warehouse
SUPERSET_WAREHOUSE_PORT=5432
SUPERSET_WAREHOUSE_DB=green_taxi_warehouse
SUPERSET_WAREHOUSE_USER=superset_ro
SUPERSET_WAREHOUSE_PASSWORD={token()}

SUPERSET_VIEWER_USERNAME=superset_viewer
SUPERSET_VIEWER_PASSWORD={token(24)}
"""
    TARGET.write_text(content, encoding="utf-8")
    print("Created .env.superset with generated local credentials.")
    print("Use scripts/show_superset_login.py to display the local demo login.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
