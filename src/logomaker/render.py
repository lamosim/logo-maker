"""Rendering through the installed Google Chrome via Playwright (channel "chrome"; never `playwright install`)."""
from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, sync_playwright

from .output import EXIT_EXTERNAL, CliError

CHROME_APP = Path("/Applications/Google Chrome.app")
PAPER = {"letter": {"width": "8.5in", "height": "11in"}, "a4": {"format": "A4"}}
_VIEWBOX = re.compile(r'viewBox="([^"]+)"')


def check_chrome(chrome_app: Path = CHROME_APP) -> dict:
    return {"found": chrome_app.exists(), "path": str(chrome_app)}


def svg_size(svg: str, width: int) -> tuple[int, int]:
    match = _VIEWBOX.search(svg)
    if not match:
        return width, width
    _, _, w, h = (float(v) for v in match.group(1).replace(",", " ").split())
    return width, max(1, round(width * h / w))


def with_size(svg: str, width: int, height: int) -> str:
    return svg.replace("<svg ", f'<svg width="{width}" height="{height}" ', 1)


class Renderer:
    """`chrome_app` only gates the existence check; Playwright's `channel="chrome"` launches the standard install."""

    def __init__(self, chrome_app: Path = CHROME_APP):
        self.chrome_app = chrome_app
        self._pw = None
        self._browser = None

    def __enter__(self) -> "Renderer":
        if not self.chrome_app.exists():
            raise CliError(f"Google Chrome not found at {self.chrome_app}; install it to render", code=EXIT_EXTERNAL)
        try:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(channel="chrome", headless=True)
        except PlaywrightError as err:
            if self._pw is not None:
                self._pw.stop()
                self._pw = None
            raise CliError(f"Could not launch Google Chrome: {err}", code=EXIT_EXTERNAL) from err
        return self

    def __exit__(self, *exc) -> None:
        browser, pw = self._browser, self._pw
        self._browser = self._pw = None
        try:
            if browser is not None:
                browser.close()
        finally:
            if pw is not None:
                pw.stop()

    @contextmanager
    def _page(self, **options) -> Iterator[Page]:
        """A fresh page, closed afterwards; a Chrome failure on the way (crash, disconnect, timeout) exits 3."""
        try:
            page = self._browser.new_page(**options)
            try:
                yield page
            finally:
                page.close()
        except PlaywrightError as err:
            raise CliError(f"Chrome failed while rendering: {err}", code=EXIT_EXTERNAL) from err

    def html_to_png(self, html: str, width: int, height: int | None = None, full_page: bool = True, transparent: bool = False) -> bytes:
        with self._page(viewport={"width": width, "height": height or 100}, device_scale_factor=1) as page:
            page.set_content(html, wait_until="load")
            return page.screenshot(full_page=full_page, omit_background=transparent)

    def svg_to_png(self, svg: str, width: int, height: int | None = None, background: str | None = None) -> bytes:
        w, h = width, height or svg_size(svg, width)[1]
        bg = f"background:{background};" if background else ""
        html = (
            "<!doctype html><html><head><meta charset='utf-8'><style>"
            f"html,body{{margin:0;padding:0;{bg}}}svg{{display:block}}</style></head>"
            f"<body>{with_size(svg, w, h)}</body></html>"
        )
        return self.html_to_png(html, w, h, full_page=False, transparent=background is None)

    def html_to_pdf(self, html: str, paper: str = "letter") -> bytes:
        with self._page() as page:
            page.set_content(html, wait_until="load")
            return page.pdf(print_background=True, **PAPER[paper])
