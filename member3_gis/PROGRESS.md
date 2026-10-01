# Progress Log

## Track 0: Initialization and Fixtures
- Initialized uv project.
- Applied teammate M1's updates regarding data contract and masks.
- Working CRS to be derived from the raster (EPSG:32645 for Trishuli, EPSG:32644 for Chamoli). Output strictly reprojected to EPSG:4326.
- Raster mask values explicitly handled:
  - Flood Mask: 0=no flood, 1=flood/debris, 255=no data. 255 is NOT "no flood".
  - Valid-data Mask: 0=valid, 1=no data, 2=radar shadow/layover, 3=cloud/cloud shadow.
  - `flood_pixels` = (flood == 1) AND (valid == 0).
  - `not_assessed_pixels` = (flood == 255) OR (valid != 0).
- Handled UNASSESSED status for infrastructures and UNKNOWN_NO_DATA for settlements depending on PESSIMISTIC scenario.

## Open Questions / Decisions
- `snapshot_date` defaults to `event_date - 1 day`.
- Need to strictly enforce `snapshot_date < event_date` everywhere.
- API signatures use local masks. Tests will use synthetic generator for these masks.
