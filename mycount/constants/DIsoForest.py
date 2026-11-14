"""Versioned settings for the independently trained IsoForest pipeline."""

from typing import Final


class DIsoForest:
    DIRECTORY: Final[str] = "data/isoforest"
    CRON_FILE: Final[str] = "/etc/cron.d/mycount-isoforest"
    SERVICE_UNIT: Final[str] = "mycount-isoforest.service"
    DEFAULT_SCHEDULE: Final[str] = "0 * * * *"
    FEATURE_VERSION: Final[str] = "browser-context-v3"
    IPV4_PREFIX: Final[int] = 16
    IPV6_PREFIX: Final[int] = 48
    WINDOW_HOURS: Final[int] = 24
    RANDOM_SEED: Final[int] = 42
    HISTORY_LIMIT: Final[int] = 20
    OBSERVATION_LIMIT: Final[int] = 100
    PROFILE_FIELDS: Final[tuple[str, ...]] = (
        "screen_width", "screen_height", "viewport_width", "viewport_height",
        "hardware_concurrency", "device_memory", "platform", "vendor", "timezone",
        "max_touch_points", "pixel_ratio",
    )
    TEMPLATE_FIELDS: Final[tuple[str, ...]] = (
        "screen_width", "screen_height", "available_width", "available_height",
        "color_depth", "pixel_depth", "pixel_ratio", "hardware_concurrency",
        "device_memory", "platform", "vendor", "max_touch_points",
        "connection_effective_type",
    )
    OS_PLATFORM_PREFIXES: Final[dict[str, tuple[str, ...]]] = {
        "Windows": ("Win",), "Mac OS X": ("Mac",),
        "Android": ("Linux arm", "Linux aarch", "Android"),
        "iOS": ("iPhone", "iPad", "iPod", "Mac"),
    }
    NETWORK_FEATURES: Final[tuple[str, ...]] = (
        "agent_diversity_across_ips", "distinct_20_blocks_log", "distinct_24_blocks_log",
        "distinct_ips_log", "inter_ip_gap_cv", "inter_ip_median_gap_log",
        "network_distinct_24_blocks_log", "network_distinct_ips_log",
        "path_diversity_across_ips", "profile_diversity_across_ips", "site_ip_share_of_network",
    )
    BROWSER_FEATURES: Final[tuple[str, ...]] = (
        "timezone_coverage", "timezone_mismatch_share", "timezone_gap_hours",
        "template_coverage", "template_ips_log", "template_networks_log",
        "template_timezones_log", "template_viewports_log",
        "platform_os_coverage", "platform_os_mismatch_share", "direct_referrer_share",
    )
    FEATURES: Final[tuple[str, ...]] = NETWORK_FEATURES + BROWSER_FEATURES
