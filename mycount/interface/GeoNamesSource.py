"""Download GeoNames reference files into a staging directory."""

from pathlib import Path
from urllib.request import Request, urlopen

from mycount.constants.DCities import DCities
from mycount.constants.DMyCount import DMyCount


class GeoNamesSource:
    def download(self, directory: Path) -> None:
        for name in ("cities500.zip", "admin1CodesASCII.txt"):
            request = Request(DCities.SOURCE + name, headers={"User-Agent": f"MyCount/{DMyCount.VERSION}"})
            with urlopen(request, timeout=DCities.TIMEOUT) as response, (directory / name).open("wb") as stream:
                size = 0
                while chunk := response.read(64 * 1024):
                    size += len(chunk)
                    if size > DCities.MAX_DOWNLOAD_BYTES:
                        raise ValueError("GeoNames download exceeds the size limit.")
                    stream.write(chunk)

