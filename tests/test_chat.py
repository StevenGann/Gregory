"""Tests for chat route helpers: intent inference, device extraction, entity_id conversion."""

import pytest

from gregory.ai.providers.base import ChatMessage
from gregory.api.routes.chat import (
    _entity_id_to_search_query,
    _extract_last_device_from_history,
    _infer_ha_action,
)


class TestInferHaAction:
    """Intent detection for turn on/off."""

    def test_turn_it_back_on(self):
        assert _infer_ha_action("Good. Now turn it back on.") == "turn_on"

    def test_turn_that_on(self):
        assert _infer_ha_action("could you turn that on") == "turn_on"

    def test_turn_the_lamp_off(self):
        assert _infer_ha_action("turn the lamp off") == "turn_off"

    def test_turn_on_turn_off(self):
        assert _infer_ha_action("turn on the kitchen light") == "turn_on"
        assert _infer_ha_action("turn off the lamp") == "turn_off"

    def test_switch_on_off(self):
        assert _infer_ha_action("switch on the light") == "turn_on"
        assert _infer_ha_action("switch off") == "turn_off"

    def test_multiword_device(self):
        assert _infer_ha_action("turn the master bedroom lamp off") == "turn_off"
        assert _infer_ha_action("turn the living room light on") == "turn_on"

    def test_no_intent(self):
        assert _infer_ha_action("what time is it") is None
        assert _infer_ha_action("tell me a joke") is None

    def test_correction_no_it_isnt_with_history(self):
        history = [ChatMessage("assistant", "The master bedroom lamp is now on.", None)]
        assert _infer_ha_action("No it isn't", history) == "turn_on"

    def test_correction_still_off_with_history(self):
        history = [ChatMessage("assistant", "The lamp is now on.", None)]
        assert _infer_ha_action("still off", history) == "turn_on"

    def test_correction_still_on_with_history(self):
        history = [ChatMessage("assistant", "Done. The kitchen light is now off.", None)]
        assert _infer_ha_action("it's still on", history) == "turn_off"

    def test_correction_that_didnt_work_with_history(self):
        history = [ChatMessage("assistant", "The lamp is back off.", None)]
        assert _infer_ha_action("that didn't work", history) == "turn_off"

    def test_correction_without_history_returns_none(self):
        assert _infer_ha_action("No it isn't", history=None) is None


class TestExtractLastDeviceFromHistory:
    """Device name extraction from assistant messages."""

    def test_the_x_is_now_on(self):
        h = [ChatMessage("assistant", "The kitchen light is now on.", None)]
        assert _extract_last_device_from_history(h) == "kitchen light"

    def test_the_x_is_back_off(self):
        h = [ChatMessage("assistant", "The master bedroom lamp is back off.", None)]
        assert _extract_last_device_from_history(h) == "master bedroom lamp"

    def test_done_the_x_is_now_off(self):
        h = [ChatMessage("assistant", "Done. The kitchen light is now off.", None)]
        assert _extract_last_device_from_history(h) == "kitchen light"

    def test_turned_off_the_x(self):
        h = [ChatMessage("assistant", "Turned off the kitchen light.", None)]
        assert _extract_last_device_from_history(h) == "kitchen light"

    def test_turned_on_the_x(self):
        h = [ChatMessage("assistant", "Turned on the master bedroom table lamp.", None)]
        assert _extract_last_device_from_history(h) == "master bedroom table lamp"

    def test_the_x_lamp_is_now_on(self):
        h = [ChatMessage("assistant", "The master bedroom table lamp is now on.", None)]
        # Pattern 1 captures full "X is now on" -> "master bedroom table lamp"
        assert _extract_last_device_from_history(h) == "master bedroom table lamp"

    def test_skips_user_messages(self):
        h = [
            ChatMessage("user", "turn off the lamp", None),
            ChatMessage("assistant", "The kitchen light is now off.", None),
        ]
        assert _extract_last_device_from_history(h) == "kitchen light"

    def test_returns_last_device_when_multiple(self):
        h = [
            ChatMessage("assistant", "The living room light is now on.", None),
            ChatMessage("user", "turn that off", None),
            ChatMessage("assistant", "The kitchen lamp is now off.", None),
        ]
        assert _extract_last_device_from_history(h) == "kitchen lamp"

    def test_empty_history(self):
        assert _extract_last_device_from_history([]) is None

    def test_no_match(self):
        h = [ChatMessage("assistant", "Sure, I can help with that.", None)]
        assert _extract_last_device_from_history(h) is None

    def test_the_x_is_on_simple_form(self):
        h = [ChatMessage("assistant", "The kitchen light is off.", None)]
        assert _extract_last_device_from_history(h) == "kitchen light"

    def test_i_turned_on_the_x(self):
        h = [ChatMessage("assistant", "I've turned on the living room lamp.", None)]
        assert _extract_last_device_from_history(h) == "living room lamp"


class TestEntityIdToSearchQuery:
    """Conversion of entity_id to search query."""

    def test_light_domain(self):
        assert (
            _entity_id_to_search_query("light.master_bedroom_table_lamp")
            == "master bedroom table lamp"
        )

    def test_without_domain(self):
        assert _entity_id_to_search_query("master_bedroom_lamp") == "master bedroom lamp"

    def test_single_word(self):
        assert _entity_id_to_search_query("light.lamp") == "lamp"
