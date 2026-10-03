"""Public HTTPS deployment settings."""

from typing import Final


class DCaddy:
    HOSTNAME: Final[str] = "count.osoyalce.com"
    HTTP_PORT: Final[int] = 80
    CONFIG: Final[str] = "/etc/caddy/Caddyfile"
    SITE_CONFIG: Final[str] = "/etc/caddy/mycount.caddy"
    SERVICE: Final[str] = "caddy.service"
    VISITOR_HEADER: Final[str] = "X-MyCount-Client-IP"
