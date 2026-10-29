# Farm geo defaults + leaf crop fallback

## Goals

1. Farm profile: GPS + Indian state dropdown; auto soil for that state; major crops dropdown with free-type override.
2. Leaf upload: pre-select farm-profile crop; if Auto-detect / vision fails, use profile crop for diagnosis.

## Farm profile (option C)

- **State** select (all Indian states/UTs).
- **Use my location**: browser geolocation → reverse geocode → set state (overrideable).
- Optional **place** text (village/district); saved `location` = `"Place, State"` or `"State"`.
- **Soil** auto-fills from curated state→dominant soil map; farmer can edit.
- **Crop** select of major crops for the state + **Other** free text.

Data is a static curated map (not live soil APIs). Soil/crops are typical statewide defaults.

## Leaf diagnosis (option C)

- On attach: leaf crop control defaults to farm-profile crop (or matching tomato/potato/maize).
- Auto-detect stays available.
- Backend `crop_hint` = user selection OR farm profile crop when selection empty / detection unsure.

## Out of scope

- District-level soil maps, live crop calendars, new API fields beyond existing `location` / `crop` / `soil_type`.
