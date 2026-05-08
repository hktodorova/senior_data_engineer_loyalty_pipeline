from pipeline.marts import _points_for_amount


def test_points_threshold():
    assert _points_for_amount(1200) > 0