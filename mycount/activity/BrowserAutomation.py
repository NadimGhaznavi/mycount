"""Recognize the browser impersonation and rendering profiles found in traffic."""

from mycount.constants.DVisitorDetails import DVisitorDetails
from mycount.entity.Visit import Visit


class BrowserAutomation:
    @staticmethod
    def matches(visit: Visit) -> bool:
        """Match combined signals, including clients that hide their webdriver flag.

        VisitDb applies the same profiles to historical rows when filtering reports.
        """
        details = dict(visit.client_details)
        if details.get("vendor") != DVisitorDetails.BOT_CLIENT_VENDOR:
            return False
        platform = details.get("platform")
        screen = (details.get("screen_width"), details.get("screen_height"))
        phone_renderer = (
            visit.device_category == "mobile"
            and platform == DVisitorDetails.BOT_LINUX_PLATFORM
            and screen == DVisitorDetails.BOT_PHONE_SCREEN
            and details.get("device_memory") == DVisitorDetails.BOT_RENDERER_MEMORY
            and details.get("max_touch_points") == DVisitorDetails.BOT_PHONE_TOUCH_POINTS
            and details.get("hardware_concurrency", 0) >= DVisitorDetails.BOT_PHONE_MIN_CPUS
        )
        desktop_impersonation = (
            visit.os_family in DVisitorDetails.BOT_DESKTOP_OS_FAMILIES
            and platform == DVisitorDetails.BOT_LINUX_PLATFORM
        )
        oversized_viewport = (
            screen == DVisitorDetails.BOT_RENDERER_SCREEN
            and details.get("viewport_width", 0) > DVisitorDetails.BOT_RENDERER_SCREEN[0]
        )
        preview_renderer = (
            platform == DVisitorDetails.BOT_PREVIEW_PLATFORM
            and screen == DVisitorDetails.BOT_PREVIEW_SCREEN
            and details.get("device_memory") == DVisitorDetails.BOT_RENDERER_MEMORY
            and visit.referrer_host == DVisitorDetails.BOT_PREVIEW_REFERRER
        )
        iphone_impersonation = (
            visit.os_family == "iOS"
            and platform in DVisitorDetails.BOT_IOS_DESKTOP_PLATFORMS
            and details.get("max_touch_points") == DVisitorDetails.BOT_IPHONE_TOUCH_POINTS
        )
        return (phone_renderer or desktop_impersonation or oversized_viewport
                or preview_renderer or iphone_impersonation)
