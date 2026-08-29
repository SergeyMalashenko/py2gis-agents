from __future__ import annotations

from py2gis_agents.core.taxonomy import (
    SOCIAL_INFRASTRUCTURE_CATEGORIES,
    TRANSPORT_INFRASTRUCTURE_CATEGORIES,
)


def test_social_taxonomy_has_expected_groups_and_categories() -> None:
    assert len(SOCIAL_INFRASTRUCTURE_CATEGORIES) == 11
    assert {category.group_key for category in SOCIAL_INFRASTRUCTURE_CATEGORIES} == {
        "mandatory",
        "everyday",
        "leisure",
    }


def test_transport_taxonomy_has_seven_categories_and_no_roads() -> None:
    assert len(TRANSPORT_INFRASTRUCTURE_CATEGORIES) == 7
    keys = {category.key for category in TRANSPORT_INFRASTRUCTURE_CATEGORIES}

    assert keys == {
        "public_transport_stops",
        "railway_stations_platforms",
        "bus_stations",
        "railway_objects",
        "airports",
        "ports",
        "logistics_terminals",
    }
    assert "roads" not in keys
