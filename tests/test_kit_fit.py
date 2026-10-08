import math

import pytest

from logomaker.kit.fit import cubic_at, fit_cubics


def arc_points(r: float, start: float, end: float, n: int) -> list[tuple[float, float]]:
    return [(r * math.cos(math.radians(start + (end - start) * i / n)), r * math.sin(math.radians(start + (end - start) * i / n)))
            for i in range(n + 1)]


def segment_distance(q, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    t = 0.0 if not length2 else max(0.0, min(1.0, ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / length2))
    return math.dist(q, (a[0] + t * dx, a[1] + t * dy))


def max_distance(points, cubics, samples=50) -> float:
    """The largest distance from any sampled curve point to the input polyline."""
    worst = 0.0
    for c in cubics:
        for i in range(samples + 1):
            q = cubic_at(c, i / samples)
            worst = max(worst, min(segment_distance(q, a, b) for a, b in zip(points, points[1:])))
    return worst


def test_a_straight_run_is_one_cubic():
    cubics = fit_cubics([(0, 0), (10, 0), (20, 0), (30, 0)])
    assert len(cubics) == 1 and cubics[0][0] == (0, 0) and cubics[0][3] == (30, 0)


def test_a_quarter_circle_fits_within_tolerance_with_few_segments():
    points = arc_points(400, 0, 90, 64)
    cubics = fit_cubics(points, tolerance=0.5)
    assert 1 <= len(cubics) <= 3
    assert cubics[0][0] == points[0] and cubics[-1][3] == points[-1]
    assert max_distance(points, cubics) < 1.0  # the samples are 10 units apart; the curve must hug the polyline through them


def test_a_sharp_corner_splits_there():
    points = [(i, 0) for i in range(0, 101, 10)] + [(100, i) for i in range(10, 101, 10)]
    cubics = fit_cubics(points, tolerance=0.5)
    assert any(math.dist(c[3], (100, 0)) < 2 for c in cubics[:-1])  # a segment ends at the corner


def test_two_points_and_fewer_are_handled():
    assert fit_cubics([(0, 0), (30, 40)]) == [((0, 0), (10, 40 / 3), (20, 80 / 3), (30, 40))]
    with pytest.raises(ValueError, match="at least two points"):
        fit_cubics([(0, 0)])


def test_tolerance_must_be_positive():
    with pytest.raises(ValueError, match="tolerance must be positive"):
        fit_cubics([(0, 0), (1, 1), (2, 0)], tolerance=0)


def test_repeated_points_are_dropped():
    assert fit_cubics([(0, 0), (0, 0), (10, 0), (10, 0)]) == [((0, 0), (10 / 3, 0), (20 / 3, 0), (10, 0))]
    with pytest.raises(ValueError, match="at least two points"):
        fit_cubics([(5, 5), (5, 5)])


def test_a_closed_circle_fits_end_to_end():
    points = arc_points(100, 0, 360, 72)
    points[-1] = points[0]
    cubics = fit_cubics(points, tolerance=0.5)
    assert cubics[0][0] == points[0] and cubics[-1][3] == points[0]
    assert all(a[3] == b[0] for a, b in zip(cubics, cubics[1:]))
    assert max_distance(points, cubics) < 1.0


def test_a_sampled_cubic_fits_as_one_or_two_cubics():
    # Uniform-in-t samples of a humped cubic sit far from chord-length parameters (about 11 units at first), so the fit
    # must reparameterise before it splits: brush() fits its sides from samples like these.
    hump = ((-400, 0), (-350, 150), (-250, 150), (-200, 0))
    points = [cubic_at(hump, i / 24) for i in range(25)]
    cubics = fit_cubics(points)
    assert len(cubics) <= 2
    assert max_distance(points, cubics) < 1.0
