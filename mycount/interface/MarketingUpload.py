"""Decode bounded marketing forms and validate an optional PNG attachment."""

from io import BytesIO

from werkzeug.formparser import parse_form_data

from mycount.constants.DMarketing import DMarketing


class MarketingUpload:
    @staticmethod
    def parse(body: bytes, content_type: str) -> tuple[dict[str, list[str]], bytes | None]:
        _, form, files = parse_form_data({
            "wsgi.input": BytesIO(body), "CONTENT_LENGTH": str(len(body)),
            "CONTENT_TYPE": content_type, "REQUEST_METHOD": "POST",
        }, max_form_memory_size=DMarketing.MAX_FORM_BYTES * 4,
           max_content_length=DMarketing.MAX_SCREENSHOT_BYTES + DMarketing.MAX_FORM_BYTES,
           max_form_parts=10, silent=False)
        try:
            if len(form) > 6 or any(name != "screenshot" for name in files) or len(files.getlist("screenshot")) > 1:
                raise ValueError("Supply one screenshot and the posting fields only.")
            if sum(len(value.encode("utf-8")) for _, value in form.items(multi=True)) > DMarketing.MAX_FORM_BYTES:
                raise ValueError("Posting fields are too large.")
            screenshot = files.get("screenshot")
            data = None
            if screenshot is not None and screenshot.filename:
                data = screenshot.read(DMarketing.MAX_SCREENSHOT_BYTES + 1)
            return form.to_dict(flat=False), data
        finally:
            for _, upload in files.items(multi=True):
                upload.close()
