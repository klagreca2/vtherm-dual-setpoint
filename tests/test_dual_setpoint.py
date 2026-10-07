# pylint: disable=unused-argument, line-too-long, protected-access

""" Test the dual-setpoint fork HEAT_COOL passthrough to the underlying climate """
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from homeassistant.core import HomeAssistant, State
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)

from custom_components.versatile_thermostat.underlyings import UnderlyingClimate

# Airzone Aidoo PRO: TURN_ON | TURN_OFF | FAN_MODE | TARGET_TEMPERATURE_RANGE | TARGET_TEMPERATURE,
# stored as a plain int in the state attributes
AIDOO_SUPPORTED_FEATURES = 395
# In heat_cool the Aidoo reports only the range of the side that is active
AIDOO_COOLING_RANGE = (67, 87)
AIDOO_HEATING_RANGE = (63, 83)


async def test_heat_cool_waits_for_a_range_that_accepts_both_setpoints(hass: HomeAssistant):
    """Night schedule asks 63/67 while the Aidoo reports its cooling range 67-87. Clamping sent
    67/67, the Aidoo moved cool to 70, and the two setpoints flapped every cycle. The fork must not
    send until the reported range accepts both bounds, then send them exactly once"""
    under = UnderlyingClimate(hass=hass, thermostat=MagicMock(), climate_entity_id="climate.aidoo_pro")
    under.hass_services_async_call = AsyncMock()

    def report_range(min_temp, max_temp):
        under.state_manager.get_state = MagicMock(
            return_value=State(
                "climate.aidoo_pro",
                HVACMode.HEAT_COOL,
                attributes={"supported_features": AIDOO_SUPPORTED_FEATURES, "min_temp": min_temp, "max_temp": max_temp},
            )
        )

    with patch.object(type(under), "is_initialized", new_callable=PropertyMock, return_value=True):
        report_range(*AIDOO_COOLING_RANGE)
        await under.set_temperature_range(67.0, 63.0)
        under.hass_services_async_call.assert_not_awaited()

        report_range(*AIDOO_HEATING_RANGE)
        await under.set_temperature_range(67.0, 63.0)
        under.hass_services_async_call.assert_awaited_once_with(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {"entity_id": "climate.aidoo_pro", "target_temp_high": 67.0, "target_temp_low": 63.0},
        )

        # Back on the cooling side: the setpoints are already there, nothing to clamp or resend
        report_range(*AIDOO_COOLING_RANGE)
        await under.set_temperature_range(67.0, 63.0)
        assert under.hass_services_async_call.await_count == 1
