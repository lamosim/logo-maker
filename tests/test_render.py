import io
import math

import pytest
from PIL import Image
from playwright.sync_api import Error as PlaywrightError

from logomaker.output import CliError
from logomaker.raster import ink_mask
from logomaker.render import Renderer, fit_box, svg_size, with_size
from tests.conftest import requires_chrome

CIRCLE = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="50" cy="50" r="50" fill="#000"/></svg>'


def test_svg_size_and_with_size():
    assert svg_size('<svg viewBox="0 0 200 50">', 400) == (400, 100)
    assert svg_size('<svg viewBox="0,0,200,50">', 400) == (400, 100)
    assert svg_size("<svg>", 64) == (64, 64)
    sized = with_size(CIRCLE, 64, 64)
    assert sized.startswith('<svg width="64" height="64" ')


def test_fit_box_limits_width_or_height():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 100"><rect width="200" height="100"/></svg>'
    assert fit_box(svg, 400, 400).startswith('<svg width="400" height="200" ')
    assert fit_box(svg, 400, 100).startswith('<svg width="200" height="100" ')


def test_missing_chrome_exits_3(tmp_path):
    with pytest.raises(CliError) as exc:
        with Renderer(chrome_app=tmp_path / "Nope.app"):
            pass
    assert exc.value.code == 3


def test_playwright_start_failure_exits_3(tmp_path, monkeypatch):
    class FailingPlaywright:
        def start(self):
            raise PlaywrightError("driver failed to start")

    monkeypatch.setattr("playwright.sync_api.sync_playwright", FailingPlaywright)
    with pytest.raises(CliError) as exc, Renderer(chrome_app=tmp_path):  # tmp_path exists, so the launch path runs
        pass
    assert exc.value.code == 3


def test_any_failure_starting_the_driver_exits_3(tmp_path, monkeypatch):
    class BrokenDriver:
        def start(self):
            raise OSError("driver binary missing")

    monkeypatch.setattr("playwright.sync_api.sync_playwright", BrokenDriver)
    with pytest.raises(CliError) as exc, Renderer(chrome_app=tmp_path):
        pass
    assert exc.value.code == 3 and "driver binary missing" in str(exc.value)


def test_exit_ignores_shutdown_failures_and_still_stops_playwright():
    events = []

    class Browser:
        def close(self):
            events.append("close")
            raise PlaywrightError("close failed")

    class Playwright:
        def stop(self):
            events.append("stop")
            raise PlaywrightError("stop failed")

    renderer = Renderer()
    renderer._browser, renderer._pw = Browser(), Playwright()
    renderer.__exit__(None, None, None)  # the work is done: a messy shutdown must not fail the command
    assert events == ["close", "stop"] and renderer._browser is None and renderer._pw is None


def test_a_renderer_outside_its_with_block_says_how_to_use_it():
    renderer = Renderer()
    for render in (lambda: renderer.svg_to_png(CIRCLE, 50), lambda: renderer.html_to_pdf("<p>x</p>")):
        with pytest.raises(RuntimeError, match="Renderer is not open; use it as a context manager"):
            render()


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
