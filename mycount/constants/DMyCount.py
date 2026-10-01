"""Shared MyCount constants."""

from typing import Final


class DMyCount:
    VERSION: Final[str] = "0.12.0"
    BASE_DIR: Final[str] = "/opt/prod/mycount"
    DATABASE_ENV: Final[str] = "/etc/mycount/database.env"
    DATABASE_NAME: Final[str] = "mycount"
    DATABASE_USER: Final[str] = "mycount"
    SERVICE_USER: Final[str] = "mycount"
    SERVICE_UNIT: Final[str] = "mycount-server.service"
    HOST: Final[str] = "127.0.0.1"
    PORT: Final[int] = 36666
    ORIGINS: Final[tuple[str, ...]] = (
        "https://mycount.osoyalce.com",
        "https://ax3l.osoyalce.com",
        "https://r3el.osoyalce.com",
        "https://blog.osoyalce.com",
        "https://snakelab.osoyalce.com",
        "https://snakelabserver.osoyalce.com",
        "https://bmca.osoyalce.com",
        "https://cmdb.osoyalce.com",
        "https://db4e.osoyalce.com",
        "https://kb.osoyalce.com",
        "https://llamaserver.osoyalce.com",
        "https://mydynip.osoyalce.com",
        "https://nadim.ghaznavi.org",
        "https://nadim-daniel.ghaznavi.org",
        "https://now.osoyalce.com",
        "https://snakeweb.osoyalce.com",
        "https://systemctl.osoyalce.com",
        "https://www.osoyalce.com",
        "https://xmr.osoyalce.com",
        "https://p2pool.osoyalce.com",
    )
    MAX_SITE_LENGTH: Final[int] = 100
    WORKERS: Final[int] = 2
    REQUEST_TIMEOUT: Final[int] = 30
    MAX_BODY_BYTES: Final[int] = 16384
    MAX_LANGUAGES: Final[int] = 32
    MAX_LANGUAGE_LENGTH: Final[int] = 255
    MAX_USER_AGENT_LENGTH: Final[int] = 2048
    CITY_NAME_LENGTH: Final[int] = 255
    SCHEMA_VERSION: Final[int] = 1
    OPTIONAL_PAYLOAD_FIELDS: Final[frozenset[str]] = frozenset({"referrer", "client_details", "visitor_id", "search"})
    VISITOR_ID_PATTERN: Final[str] = r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
    EVENT: Final[str] = "page_view"
    COUNT_PATH: Final[str] = "/get_count"
    COLLECTION_PATH: Final[str] = "/count"
    HEALTH_PATH: Final[str] = "/health"
    HTTPS_PORT: Final[int] = 443
    PAYLOAD_FIELDS: Final[frozenset[str]] = frozenset(
        {
            "schema_version",
            "event",
            "site",
            "url",
            "languages",
            "user_agent",
        }
    )
    LANGUAGE_PATTERN: Final[str] = r"[A-Za-z]{1,8}(?:-[A-Za-z0-9]{1,8})*"
