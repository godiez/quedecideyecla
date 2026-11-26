import re
import time
from urllib.parse import unquote

import httpx

from actas import municipality

RETRY_STATUS = {429, 500, 502, 503, 504}
USER_AGENT = f"Mozilla/5.0 (compatible; transparencia-ayuntamiento-{municipality.load().slug})"


class Fetcher:
    def __init__(self, delay_s: float = 1.0, max_retries: int = 3, timeout: float = 90) -> None:
        self.http = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        self.delay_s = delay_s
        self.max_retries = max_retries
        self._last = 0.0

    def _get(self, url: str, **kw) -> httpx.Response:
        for attempt in range(self.max_retries):
            wait = self.delay_s - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                resp = self.http.get(url, **kw)
            except httpx.TransportError:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(self.delay_s * 2 ** (attempt + 1))
                continue
            if resp.status_code in RETRY_STATUS and attempt < self.max_retries - 1:
                time.sleep(self.delay_s * 2 ** (attempt + 1))
                continue
            resp.raise_for_status()
            return resp
        raise RuntimeError("unreachable")

    def get_text(self, url: str, **kw) -> str:
        return self._get(url, **kw).text

    def get_bytes(self, url: str, **kw) -> bytes:
        return self._get(url, **kw).content

    def download(self, url: str, **kw) -> tuple[bytes, str | None]:
        resp = self._get(url, **kw)
        return resp.content, filename_from_disposition(resp.headers.get("content-disposition", ""))

    def get_json(self, url: str, **kw):
        return self._get(url, **kw).json()


def filename_from_disposition(header: str) -> str | None:
    m = re.search(r"filename\*=UTF-8''([^;]+)", header, re.I)
    if m:
        return unquote(m.group(1)).strip()
    m = re.search(r'filename="([^"]+)"', header, re.I)
    return m.group(1).strip() if m else None
