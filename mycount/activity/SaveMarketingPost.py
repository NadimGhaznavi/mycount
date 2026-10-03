"""Save a promotional event and remove its screenshot if persistence fails."""

from dataclasses import replace

from mycount.entity.MarketingPost import MarketingPost
from mycount.interface.MarketingDb import MarketingDb
from mycount.interface.MarketingScreenshots import MarketingScreenshots
from mycount.interface.DbCommitUncertain import DbCommitUncertain


class SaveMarketingPost:
    def __init__(self, posts: MarketingDb, screenshots: MarketingScreenshots) -> None:
        self._posts = posts
        self._screenshots = screenshots

    def save(self, post: MarketingPost, screenshot: bytes | None) -> int:
        existing = self._posts.submission(post.submission_id)
        if existing is not None:
            return existing
        reference = self._screenshots.save(screenshot) if screenshot is not None else None
        try:
            return self._posts.record(replace(post, screenshot_path=reference))
        except (DbCommitUncertain, KeyboardInterrupt, SystemExit):
            # The database may reference this file despite the lost commit reply.
            raise
        except BaseException as error:
            if reference is not None:
                try:
                    self._screenshots.remove(reference)
                except OSError as cleanup_error:
                    error.add_note(f"Unable to remove screenshot {reference}: {cleanup_error}")
            raise
