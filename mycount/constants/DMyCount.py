"""Shared MyCount constants."""

from typing import Final


class DMyCount:
    VERSION: Final[str] = "0.1.0"
    BASE_DIR: Final[str] = "/opt/prod/mycount"
    DATABASE_ENV: Final[str] = "/etc/mycount/database.env"
    DATABASE_NAME: Final[str] = "mycount"
    DATABASE_USER: Final[str] = "mycount"
    SERVICE_USER: Final[str] = "mycount"
    SERVICE_UNIT: Final[str] = "mycount-server.service"
    HOST: Final[str] = "127.0.0.1"
    PORT: Final[int] = 36666
    SITE: Final[str] = "mycount"
    ORIGIN: Final[str] = "https://mycount.osoyalce.com"
    WORKERS: Final[int] = 2
    REQUEST_TIMEOUT: Final[int] = 30
    MAX_BODY_BYTES: Final[int] = 16384
    MAX_LANGUAGES: Final[int] = 32
    MAX_LANGUAGE_LENGTH: Final[int] = 255
    MAX_USER_AGENT_LENGTH: Final[int] = 2048
    CITY_NAME_LENGTH: Final[int] = 255
    SCHEMA_VERSION: Final[int] = 1
    EVENT: Final[str] = "page_view"
    COLLECTION_PATH: Final[str] = "/"
    HEALTH_PATH: Final[str] = "/health"
    HTTPS_PORT: Final[int] = 443
    PAYLOAD_FIELDS: Final[frozenset[str]] = frozenset({
        "schema_version", "event", "site", "url", "languages", "user_agent",
    })
    LANGUAGE_PATTERN: Final[str] = r"[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*"
