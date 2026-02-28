"""Tests for Home Assistant tool (parse_service_params, find_entities, etc.)."""

import pytest

from gregory.tools.home_assistant import find_entities, parse_service_params


def test_parse_service_params_simple():
    """Parse basic light.turn_on with entity_id."""
    result = parse_service_params("light.turn_on | entity_id=light.living_room")
    assert result is not None
    domain, service, data = result
    assert domain == "light"
    assert service == "turn_on"
    assert data == {"entity_id": "light.living_room"}


def test_parse_service_params_brightness():
    """Parse brightness (int)."""
    result = parse_service_params(
        "light.turn_on | entity_id=light.kitchen | brightness=128"
    )
    assert result is not None
    _, _, data = result
    assert data["brightness"] == 128
    assert data["entity_id"] == "light.kitchen"


def test_parse_service_params_color_temp():
    """Parse color_temp_kelvin (int)."""
    result = parse_service_params(
        "light.turn_on | entity_id=light.x | color_temp_kelvin=3000"
    )
    assert result is not None
    _, _, data = result
    assert data["color_temp_kelvin"] == 3000


def test_parse_service_params_rgb_color():
    """Parse rgb_color as list."""
    result = parse_service_params(
        "light.turn_on | entity_id=light.x | rgb_color=255,128,0"
    )
    assert result is not None
    _, _, data = result
    assert data["rgb_color"] == [255, 128, 0]


def test_parse_service_params_transition():
    """Parse transition (float)."""
    result = parse_service_params(
        "light.turn_on | entity_id=light.x | transition=2.5"
    )
    assert result is not None
    _, _, data = result
    assert data["transition"] == 2.5


def test_parse_service_params_multiple():
    """Parse multiple params."""
    result = parse_service_params(
        "light.turn_on | entity_id=light.lr | brightness=64 | color_temp_kelvin=2700"
    )
    assert result is not None
    domain, service, data = result
    assert domain == "light"
    assert service == "turn_on"
    assert data["entity_id"] == "light.lr"
    assert data["brightness"] == 64
    assert data["color_temp_kelvin"] == 2700


def test_parse_service_params_invalid_empty():
    """Empty or invalid returns None."""
    assert parse_service_params("") is None


def test_parse_service_params_invalid_no_dot():
    """Missing domain.service dot returns None."""
    assert parse_service_params("light | entity_id=x") is None


def test_parse_service_params_light_turn_off():
    """Parse light.turn_off."""
    result = parse_service_params("light.turn_off | entity_id=light.bedroom")
    assert result is not None
    domain, service, data = result
    assert domain == "light"
    assert service == "turn_off"
    assert data["entity_id"] == "light.bedroom"


def test_parse_service_params_switch():
    """Parse switch.turn_on."""
    result = parse_service_params("switch.turn_on | entity_id=switch.outlet")
    assert result is not None
    domain, service, data = result
    assert domain == "switch"
    assert service == "turn_on"
    assert data["entity_id"] == "switch.outlet"


@pytest.mark.asyncio
async def test_find_entities_matches_friendly_name():
    """find_entities filters by friendly_name."""
    entities = [
        {"entity_id": "binary_sensor.front_door", "state": "off", "friendly_name": "Front Door"},
        {"entity_id": "sensor.other", "state": "1", "friendly_name": "Other"},
    ]

    async def mock_list(base_url, token, domain=None):
        return entities

    import gregory.tools.home_assistant as ha_module
    original = ha_module.list_entities
    ha_module.list_entities = mock_list
    try:
        result = await find_entities("http://test", "token", "front door")
        assert len(result) == 1
        assert result[0]["entity_id"] == "binary_sensor.front_door"
    finally:
        ha_module.list_entities = original


@pytest.mark.asyncio
async def test_find_entities_matches_entity_id():
    """find_entities filters by entity_id."""
    entities = [
        {"entity_id": "light.living_room", "state": "on", "friendly_name": "Living Room"},
        {"entity_id": "light.kitchen", "state": "off", "friendly_name": "Kitchen"},
    ]

    async def mock_list(base_url, token, domain=None):
        return entities

    import gregory.tools.home_assistant as ha_module
    original = ha_module.list_entities
    ha_module.list_entities = mock_list
    try:
        result = await find_entities("http://test", "token", "living room")
        assert len(result) == 1
        assert result[0]["entity_id"] == "light.living_room"
    finally:
        ha_module.list_entities = original


@pytest.mark.asyncio
async def test_find_entities_splits_on_hyphens():
    """find_entities treats 'bedroom-master' as 'bedroom' and 'master'."""
    entities = [
        {"entity_id": "light.bulb", "state": "on", "friendly_name": "Table Lamp Master Bedroom"},
    ]

    async def mock_list(base_url, token, domain=None):
        return entities

    import gregory.tools.home_assistant as ha_module
    original = ha_module.list_entities
    ha_module.list_entities = mock_list
    try:
        result = await find_entities("http://test", "token", "bedroom-master table lamp")
        assert len(result) == 1
        assert result[0]["entity_id"] == "light.bulb"
    finally:
        ha_module.list_entities = original


@pytest.mark.asyncio
async def test_find_entities_no_match_returns_empty():
    """find_entities returns empty when no entities match."""
    entities = [
        {"entity_id": "light.kitchen", "state": "off", "friendly_name": "Kitchen"},
    ]

    async def mock_list(base_url, token, domain=None):
        return entities

    import gregory.tools.home_assistant as ha_module
    original = ha_module.list_entities
    ha_module.list_entities = mock_list
    try:
        result = await find_entities("http://test", "token", "garage")
        assert result == []
    finally:
        ha_module.list_entities = original
