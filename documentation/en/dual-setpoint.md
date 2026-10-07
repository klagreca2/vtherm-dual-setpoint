# Dual setpoint (HEAT_COOL passthrough)

This fork adds support for the Home Assistant `heat_cool` HVAC mode to
`over_climate` Versatile Thermostats, where the climate entity exposes two
target temperatures simultaneously: `target_temp_high` (cooling setpoint) and
`target_temp_low` (heating setpoint), with a deadband in between.

## Why a passthrough

Upstream VTherm is built around a single `target_temperature` and its
regulation/preset engine operates on that single value. Devices like AirZone
already implement the heat/cool deadband well natively. Rather than reinvent
dual-setpoint regulation, this fork forwards the two setpoints straight to the
underlying climate device when the VTherm is in `heat_cool` mode.

## Behaviour

- **`heat_cool` mode** — VTherm forwards `target_temp_high` / `target_temp_low`
  directly to the underlying climate entity. VTherm's single-setpoint
  auto-regulation (TPI, offset, EMA) and preset temperatures are **not** applied
  to the deadband in this mode; the underlying device handles it.
- **`heat`, `cool`, `off`, other modes** — unchanged from upstream. Full
  single-setpoint regulation, presets, window/motion/presence handling apply.

`heat_cool` is offered automatically whenever the underlying climate entity
advertises it (`HVACMode.HEAT_COOL` + `ClimateEntityFeature.TARGET_TEMPERATURE_RANGE`).
No extra configuration is required.

## Requirements

- `over_climate` type VTherm.
- The underlying climate entity must support `heat_cool` and
  `TARGET_TEMPERATURE_RANGE`. If it does not, `heat_cool` simply will not appear.

## Interaction with scheduler-component / scheduler-card

The VTherm climate entity advertises `TARGET_TEMPERATURE_RANGE`, so the
scheduler-card can schedule `climate.set_temperature` actions with
`target_temp_high` + `target_temp_low` while the VTherm is in `heat_cool`.

## Implementation notes

The change is intentionally small and contained:

- `vtherm_state.py` — `VThermState` carries optional `target_temperature_high` /
  `target_temperature_low`.
- `state_manager.py` — in `heat_cool`, requested high/low are carried into the
  current state, bypassing the single-setpoint preset/window/presence logic.
- `base_thermostat.py` — `async_set_temperature` reads `target_temp_high` /
  `target_temp_low`; `update_states` reflects them on the entity.
- `thermostat_climate.py` — `build_hvac_list` keeps `heat_cool`;
  `_send_regulated_temperature` short-circuits to a passthrough send; the
  range properties report VTherm state in `heat_cool`.
- `underlyings.py` — `UnderlyingClimate.set_temperature_range()` sends the two
  setpoints, with change-detection to avoid spamming the device each cycle.

## Restore after an interrupted start (fork fix)

Upstream VTherm only restores its saved state once Home Assistant fires
`EVENT_HOMEASSISTANT_STARTED`. Until then the entity shows its default `off`
state. If Home Assistant is stopped during that window (for example a second
restart, or a Core update, issued while the first restart is still booting),
Home Assistant saves that default `off` as the VTherm's last state. The next start
then restores `off`, marks it `hvac_off_manual` and turns the underlying climate off.

The fork keeps the last good saved state from `async_added_to_hass` until the
restored state has been published, and hands it to the next run through
`extra_restore_state_data`. A run that never got to start the VTherm therefore no
longer overwrites what the next run restores. When this happens, the log shows:

    <name> - previous run stopped before this VTherm was started. Restoring the state saved before it (<state>)

Covered by `test_over_climate_restore_after_interrupted_start` and
`test_over_climate_carries_last_state_until_started` in `tests/test_start.py`.
