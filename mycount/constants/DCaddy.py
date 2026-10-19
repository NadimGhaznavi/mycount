"""Public HTTPS deployment settings."""

from typing import Final


class DCaddy:
    HOSTNAME: Final[str] = "count.osoyalce.com"
    CONFIG: Final[str] = "/etc/caddy/Caddyfile"
    SITE_CONFIG: Final[str] = "/etc/caddy/mycount.caddy"
    SERVICE: Final[str] = "caddy.service"
    COMMAND_TIMEOUT: Final[int] = 60
    VISITOR_HEADER: Final[str] = "X-MyCount-Client-IP"
