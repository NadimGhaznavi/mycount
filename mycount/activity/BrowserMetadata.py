"""Derive broad browser categories from transient request data."""

from dataclasses import replace

from user_agents import parse

from mycount.entity.Visit import Visit


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
        )
