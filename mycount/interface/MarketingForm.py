"""Validate submitted marketing form data and resolve its local timestamp."""

from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
import re

from mycount.constants.DMarketing import DMarketing
from mycount.entity.MarketingPost import MarketingPost


class MarketingForm:
    @staticmethod
    def parse(fields: dict[str, list[str]]) -> MarketingPost:
        if fields.keys() - {"posted_at", "timezone_offset", "platform", "url", "notes", "submission_id"}:
            raise ValueError("Supply the posting fields only.")
        def field(name: str) -> str:
            values = fields.get(name, [""])
            if len(values) != 1:
                raise ValueError(f"Supply one value for {name}.")
            return values[0].strip()

        submission_id = field("submission_id")
        if re.fullmatch(r"[0-9a-f]{32}", submission_id) is None:
            raise ValueError("Invalid posting submission ID. Reload the form to start a new posting.")
        posted_at = field("posted_at")
        try:
            local = datetime.strptime(posted_at, "%Y-%m-%d %H:%M")
            offset = int(field("timezone_offset"))
            if local.strftime("%Y-%m-%d %H:%M") != posted_at or not -840 <= offset <= 840:
                raise ValueError
            utc = (local + timedelta(minutes=offset)).replace(tzinfo=timezone.utc)
        except (ValueError, OverflowError) as error:
            raise ValueError("Posted At must be yyyy-mm-dd hh:mm with a valid browser timezone.") from error
        platform = field("platform")
        if platform not in DMarketing.PLATFORMS:
            raise ValueError("Choose a platform from the list.")
        url = field("url")
        try:
            parsed = urlsplit(url)
            valid_url = parsed.scheme in ("http", "https") and parsed.hostname and parsed.port != 0
        except ValueError:
            valid_url = False
        if (not valid_url or len(url) > DMarketing.MAX_URL_LENGTH
                or any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in url)):
            raise ValueError("Posting URL must be an HTTP(S) URL of at most 2048 characters.")
        notes = field("notes")
        if len(notes) > DMarketing.MAX_NOTES_LENGTH:
            raise ValueError("Notes must be at most 4000 characters.")
        return MarketingPost(utc, platform, url, notes, submission_id=submission_id)
