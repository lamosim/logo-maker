import io
import math

import pytest
from PIL import Image
from playwright.sync_api import Error as PlaywrightError

from logomaker.output import CliError
from logomaker.raster import ink_mask
from logomaker.render import Renderer, svg_size, with_size
from tests.conftest import requires_chrome

CIRCLE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="50" fill="#000"/></svg>'


def test_svg_size_and_with_size():
    assert svg_size('<svg viewBox="0 0 200 50">', 400) == (400, 100)
    assert svg_size('<svg viewBox="0,0,200,50">', 400) == (400, 100)
    assert svg_size("<svg>", 64) == (64, 64)
    sized = with_size(CIRCLE, 64, 64)
    assert sized.startswith('<svg width="64" height="64" ')


def test_missing_chrome_exits_3(tmp_path):
    with pytest.raises(CliError) as exc:
        with Renderer(chrome_app=tmp_path / "Nope.app"):
            pass
    assert exc.value.code == 3


def test_playwright_start_failure_exits_3(tmp_path, monkeypatch):
    class FailingPlaywright:
        def start(self):
            raise PlaywrightError("driver failed to start")

    monkeypatch.setattr("logomaker.render.sync_playwright", FailingPlaywright)
    with pytest.raises(CliError) as exc, Renderer(chrome_app=tmp_path):  # tmp_path exists, so the launch path runs
        pass
    assert exc.value.code == 3


def test_exit_stops_playwright_even_if_closing_chrome_fails():
    events = []

    class Browser:
        def close(self):
            events.append("close")
            raise PlaywrightError("close failed")

    class Playwright:
        def stop(self):
            events.append("stop")

    renderer = Renderer()
    renderer._browser, renderer._pw = Browser(), Playwright()
    with pytest.raises(PlaywrightError):
        renderer.__exit__(None, None, None)
    assert events == ["close", "stop"] and renderer._browser is None and renderer._pw is None


@requires_chrome
@pytest.mark.render
def test_svg_to_png_sizes_and_alpha(renderer):
    png = renderer.svg_to_png(CIRCLE, 100)
    image = Image.open(io.BytesIO(png))
    assert image.size == (100, 100) and image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0  # transparent outside the mark
    ink = ink_mask(png).sum()
    assert math.isclose(ink, math.pi * 50 * 50, rel_tol=0.05)
    opaque = Image.open(io.BytesIO(renderer.svg_to_png(CIRCLE, 50, background="#ffffff")))
    assert opaque.getpixel((1, 1))[:3] == (255, 255, 255)


@requires_chrome
@pytest.mark.render
def test_html_to_png_and_pdf(renderer):
    html = "<html><body style='margin:0'><div style='width:200px;height:50px;background:#f00'></div></body></html>"
    image = Image.open(io.BytesIO(renderer.html_to_png(html, 200, 50, full_page=False)))
    assert image.size == (200, 50) and image.getpixel((10, 10))[:3] == (255, 0, 0)
    pdf = renderer.html_to_pdf(html)
    assert pdf[:4] == b"%PDF"


@requires_chrome
@pytest.mark.render
def test_chrome_failure_while_rendering_exits_3(renderer):
    renderer._browser.close()
    with pytest.raises(CliError) as exc:
        renderer.svg_to_png(CIRCLE, 50)
    assert exc.value.code == 3
