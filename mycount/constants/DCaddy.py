"""Public HTTPS deployment settings."""

from typing import Final


class DCaddy:
    HOSTNAME: Final[str] = "count.osoyalce.com"
    CONFIG: Final[str] = "/etc/caddy/Caddyfile"
    SITE_CONFIG: Final[str] = "/etc/caddy/mycount.caddy"
    SERVICE: Final[str] = "caddy.service"
    VISITOR_HEADER: Final[str] = "X-MyCount-Client-IP"
