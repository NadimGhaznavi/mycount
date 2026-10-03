"""Validate and store PNG screenshots in the application's marketing folder."""

from pathlib import Path
from collections.abc import Iterator
from datetime import datetime
import re
import struct
from uuid import uuid4
import zlib

from mycount.constants.DMarketing import DMarketing


class MarketingScreenshots:
    def __init__(self, application: Path | None = None) -> None:
        self._application = application if application is not None else Path(__file__).resolve().parents[2]

    @staticmethod
    def validate(data: bytes) -> None:
        """Check PNG headers, required chunks, lengths, and checksums."""
        if len(data) > DMarketing.MAX_SCREENSHOT_BYTES:
            raise ValueError("Screenshot must be at most 10 MiB.")
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValueError("Screenshot must be a PNG file.")
        offset = 8
        seen_header = False
        seen_image = False
        while offset + 12 <= len(data):
            length = struct.unpack_from(">I", data, offset)[0]
            kind = data[offset + 4:offset + 8]
            end = offset + 8 + length
            if end + 4 > len(data):
                break
            chunk = data[offset + 8:end]
            checksum = struct.unpack_from(">I", data, end)[0]
            if zlib.crc32(data[offset + 4:end]) != checksum:
                break
            if not seen_header:
                if kind != b"IHDR" or length != 13:
                    break
                width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", chunk)
                depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
                if not (0 < width <= 0x7fffffff and 0 < height <= 0x7fffffff
                        and depth in depths.get(color, ()) and compression == filtering == 0 and interlace in (0, 1)):
                    break
                seen_header = True
            elif kind == b"IHDR":
                break
            elif kind == b"IDAT":
                seen_image = seen_image or length > 0
            elif kind == b"IEND":
                if length == 0 and seen_image and end + 4 == len(data):
                    return
                break
            offset = end + 4
        raise ValueError("Screenshot is an invalid or incomplete PNG file.")

    def save(self, data: bytes) -> str:
        reference = f"{DMarketing.SCREENSHOT_DIRECTORY}/{uuid4().hex}.png"
        path = self._application / reference
        path.parent.mkdir(parents=True, exist_ok=True)
        stream = path.open("xb")
        try:
            with stream:
                stream.write(data)
        except OSError:
            path.unlink()
            raise
        return reference

    def remove(self, reference: str) -> None:
        (self._application / reference).unlink()

    def older_than(self, cutoff: datetime) -> Iterator[str]:
        """Yield only generated screenshots old enough for reconciliation."""
        directory = self._application / DMarketing.SCREENSHOT_DIRECTORY
        if not directory.exists():
            return
        for path in directory.iterdir():
            if (re.fullmatch(r"[0-9a-f]{32}\.png", path.name) is not None
                    and path.is_file() and path.stat().st_mtime < cutoff.timestamp()):
                yield f"{DMarketing.SCREENSHOT_DIRECTORY}/{path.name}"

    def read(self, reference: str) -> bytes:
        if re.fullmatch(re.escape(DMarketing.SCREENSHOT_DIRECTORY) + r"/[0-9a-f]{32}\.png", reference) is None:
            raise FileNotFoundError("Screenshot not found")
        return (self._application / reference).read_bytes()
