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
