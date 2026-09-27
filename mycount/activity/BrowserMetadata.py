"""Derive browser, operating system, device, and bot metadata."""

from dataclasses import replace

from user_agents import parse

from mycount.entity.Visit import Visit
from mycount.constants.DVisitorDetails import DVisitorDetails


class BrowserMetadata:
    def enrich(self, visit: Visit, user_agent: str) -> Visit:
        browser = parse(user_agent)
        if browser.is_tablet:
            device = "tablet"
        elif browser.is_mobile:
            device = "mobile"
        elif browser.is_pc:
            device = "desktop"
        else:
            device = "other"
        return replace(
            visit,
            browser_family=browser.browser.family if browser.browser.family != "Other" else None,
            os_family=browser.os.family if browser.os.family != "Other" else None,
            device_category=device,
            browser_version=browser.browser.version_string[:DVisitorDetails.VERSION_LENGTH] or None,
            os_version=browser.os.version_string[:DVisitorDetails.VERSION_LENGTH] or None,
            device_brand=(browser.device.brand or "")[:DVisitorDetails.TEXT_LENGTH] or None,
            device_model=(browser.device.model or "")[:DVisitorDetails.TEXT_LENGTH] or None,
            is_bot=(browser.is_bot or browser.browser.family in DVisitorDetails.BOT_BROWSER_FAMILIES)
            if user_agent else None,
        )
