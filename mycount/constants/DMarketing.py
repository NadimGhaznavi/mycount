"""Marketing form choices and input limits."""

from typing import Final


class DMarketing:
    PLATFORMS: Final[tuple[str, ...]] = (
        "Discord",
        "Email",
        "Facebook",
        "LinkedIn",
        "Reddit",
        "X",
        "MyCount",
    )
    MAX_URL_LENGTH: Final[int] = 2048
    MAX_NOTES_LENGTH: Final[int] = 4000
    MAX_FORM_BYTES: Final[int] = 65536
    MAX_SCREENSHOT_BYTES: Final[int] = 10 * 1024 * 1024
    SCREENSHOT_DIRECTORY: Final[str] = "pages/marketing"
