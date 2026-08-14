import pytest

from app.exceptions import AppException
from app.services.field_geometry import (
    analyze_boundary,
    intersection_area_square_meters,
    normalize_boundary,
)


BEIJING_RECTANGLE = {
    "type": "Polygon",
    "coordinates": [
        [
            [116.3000, 40.0000],
            [116.3010, 40.0000],
            [116.3010, 40.0010],
            [116.3000, 40.0010],
            [116.3000, 40.0000],
        ]
    ],
}


def test_analyze_boundary_returns_area_and_representative_point_inside_polygon():
    """A broken geodesic calculation would store user-visible field area as zero or a degree-based value."""
    result = analyze_boundary(BEIJING_RECTANGLE)

    assert result.area_square_meters == pytest.approx(9481, rel=0.05)
    assert result.area_mu == pytest.approx(14.22, rel=0.05)
    assert 40.0 < result.latitude < 40.001
    assert 116.3 < result.longitude < 116.301
    assert result.normalized["coordinates"][0][0] == [116.3, 40.0]


def test_normalize_boundary_closes_open_outer_ring():
    """Leaflet drafts may omit the repeated final vertex; rejecting that would drop a valid field outline."""
    normalized = normalize_boundary(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [116.3000, 40.0000],
                    [116.3010, 40.0000],
                    [116.3010, 40.0010],
                    [116.3000, 40.0010],
                ]
            ],
        }
    )

    assert normalized["coordinates"][0][0] == normalized["coordinates"][0][-1]


@pytest.mark.parametrize(
    "boundary",
    [
        {"type": "MultiPolygon", "coordinates": []},
        {"type": "Polygon", "coordinates": []},
        {"type": "Polygon", "coordinates": [[[116.3, 40.0], [116.3, 40.0], [116.3, 40.0]]]},
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [116.3000, 40.0000],
                    [116.3010, 40.0010],
                    [116.3000, 40.0010],
                    [116.3010, 40.0000],
                    [116.3000, 40.0000],
                ]
            ],
        },
        {"type": "Polygon", "coordinates": [[[200, 40], [201, 40], [201, 41], [200, 40]]]},
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [116.3000, 40.0000],
                    [116.3010, 40.0000],
                    [116.3010, 40.0010],
                    [116.3000, 40.0010],
                    [116.3000, 40.0000],
                ],
                [
                    [116.3002, 40.0002],
                    [116.3004, 40.0002],
                    [116.3004, 40.0004],
                    [116.3002, 40.0002],
                ],
            ],
        },
    ],
)
def test_analyze_boundary_rejects_invalid_or_unsupported_polygons(boundary):
    """Unsupported or invalid geometry saved to fields would make later area and weather queries unreliable."""
    with pytest.raises(AppException) as exc:
        analyze_boundary(boundary)

    assert exc.value.status_code == 422


def test_intersection_area_distinguishes_overlap_from_shared_edge():
    """Treating shared boundaries as overlap would block adjacent fields in a real farm."""
    left = analyze_boundary(BEIJING_RECTANGLE)
    shared_edge = analyze_boundary(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [116.3010, 40.0000],
                    [116.3020, 40.0000],
                    [116.3020, 40.0010],
                    [116.3010, 40.0010],
                    [116.3010, 40.0000],
                ]
            ],
        }
    )
    overlapping = analyze_boundary(
        {
            "type": "Polygon",
            "coordinates": [
                [
                    [116.3005, 40.0000],
                    [116.3015, 40.0000],
                    [116.3015, 40.0010],
                    [116.3005, 40.0010],
                    [116.3005, 40.0000],
                ]
            ],
        }
    )

    assert intersection_area_square_meters(left.shape, shared_edge.shape) == 0
    assert intersection_area_square_meters(left.shape, overlapping.shape) > 1
