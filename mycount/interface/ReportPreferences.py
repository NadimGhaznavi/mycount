"""Remember shared report filters in a browser session cookie."""

from http.cookies import CookieError, SimpleCookie
from urllib.parse import parse_qs, urlencode

from mycount.constants.DReports import DReports


class ReportPreferences:
    @staticmethod
    def read(header: str | None) -> dict[str, list[str]]:
        cookies = SimpleCookie()
        try:
            cookies.load(header or "")
        except CookieError as error:
            raise ValueError("Invalid report filter cookie.") from error
        if DReports.PREFERENCES_COOKIE not in cookies:
            return {}
        query = parse_qs(cookies[DReports.PREFERENCES_COOKIE].value, keep_blank_values=True)
        return {name: query[name] for name in DReports.PREFERENCE_FIELDS if name in query}

    @staticmethod
    def merge(saved: dict[str, list[str]], query: dict[str, list[str]]) -> dict[str, list[str]]:
        merged = {**saved, **query}
        if "exclude_bots" in query and "filter" not in query:
            merged.pop("filter", None)
        return merged

    @staticmethod
    def header(query: dict[str, list[str]], filter_mode: str) -> str:
        values = {name: query[name][0] for name in DReports.PREFERENCE_FIELDS if name in query}
        values["filter"] = filter_mode
        cookies = SimpleCookie()
        cookies[DReports.PREFERENCES_COOKIE] = urlencode(values)
        cookie = cookies[DReports.PREFERENCES_COOKIE]
        cookie["path"] = "/"
        cookie["httponly"] = True
        cookie["samesite"] = "Lax"
        return cookie.OutputString()
