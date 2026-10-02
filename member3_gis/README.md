# GIS Engine — Space Track Flood Damage Assessment

## Overview
End-to-end geospatial pipeline for analyzing flood damage from satellite imagery:
1. **OSM Data Loading** (Track A) — fetch pre-event infrastructure
2. **Road Graph Building** (Track B) — construct routing network
3. **Mask Parsing** (Track D) — extract flood and unassessed areas from rasters
4. **Infrastructure Classification** (Impact) — identify affected roads/buildings
5. **Settlement Reachability** (Track E) — determine which villages lost access
6. **API & Output** (Track C) — JSON + GeoJSON for dashboard

## Setup

### Prerequisites
- Python 3.11+
- `uv` package manager (or `pip`)

### Installation
```bash
cd member3_gis
uv sync
# or: pip install -r requirements.txt
```

### Environment
All work stays in `member3_gis/`. Large files (rasters, caches) are git-ignored.

## Usage

### Full Pipeline
```python
from gis_engine.pipeline import analyze_full
from datetime import date

result = analyze_full(
    bbox=(85.05, 27.85, 85.45, 28.30),  # Trishuli
    event_date=date(2026, 8, 26),
    flood_mask_path="path/to/flood.tif",
    valid_mask_path="path/to/valid.tif",
    snapshot_date=date(2026, 8, 25)  # optional, defaults to event_date - 1 day
)

# result is a dict matching AnalysisResult schema:
# - metadata (bbox, dates, attributions)
# - statistics (flood area, affected roads, settlement counts)
# - settlements (array with status, confidence, destination, distance)
# - GeoJSON layers (flood, roads, bridges, buildings, settlements, destinations)
```

### Individual Modules
```python
# 1. Fetch OSM data
from gis_engine.loaders.osm_loader import load_osm_data
osm = load_osm_data(
    bbox=(85.05, 27.85, 85.45, 28.30),
    snapshot_date=date(2026, 8, 25),
    event_date=date(2026, 8, 26)
)
# Returns dict: {"highways": GeoDataFrame, "buildings": ..., "places": ..., "hospitals": ..., "towns": ...}

# 2. Build road graph
from gis_engine.graph_builder import build_road_graph
G, summary = build_road_graph(osm["highways"], snap_tolerance_m=5.0)
# Returns NetworkX MultiGraph and summary stats

# 3. Parse masks
from gis_engine.mask_adapter import process_masks
flood_gdf, unassessed_gdf, assessed_fraction = process_masks(
    flood_mask_path="flood.tif",
    valid_mask_path="valid.tif"
)

# 4. Classify infrastructure
from gis_engine.impact import classify_infrastructure
impact = classify_infrastructure(G, osm["buildings"], flood_gdf)
# Returns dict with affected_road_km, affected_bridges, affected_buildings

# 5. Analyze cut-off settlements
from gis_engine.cutoff import analyze_cutoff
cutoff_result = analyze_cutoff(
    roads_graph=G,
    settlements_gdf=osm["places"],
    towns_gdf=osm["towns"],
    hospitals_gdf=osm["hospitals"],
    flood_gdf=flood_gdf,
    unassessed_gdf=unassessed_gdf
)
# Returns dict with settlements list and statistics
```

### FastAPI Endpoint
```bash
uvicorn gis_engine.api:app --reload
```

Then POST to `http://localhost:8000/analyze`:
```json
{
  "bbox": [85.05, 27.85, 85.45, 28.30],
  "event_date": "2026-08-26",
  "flood_mask_path": "/path/to/flood.tif",
  "valid_mask_path": "/path/to/valid.tif",
  "snapshot_date": "2026-08-25"
}
```

Response: AnalysisResult JSON with metadata, statistics, settlements, GeoJSON layers.

## Testing
```bash
# All tests
uv run pytest tests/ -v

# Specific module
uv run pytest tests/test_05_cutoff.py -v

# Skip network tests (live OSM API calls)
uv run pytest tests/ -v -m "not network"
```

## Project Structure
member3_gis/
├── gis_engine/
│ ├── loaders/
│ │ └── osm_loader.py # Ohsome API fetching + caching
│ ├── graph_builder.py # Noding, snapping, road graph
│ ├── mask_adapter.py # Raster to vector, flood extraction
│ ├── impact.py # Infrastructure classification
│ ├── cutoff.py # Settlement reachability
│ ├── schemas.py # Pydantic v2 output contracts
│ ├── pipeline.py # End-to-end orchestration
│ └── api.py # FastAPI endpoint
├── tests/
│ ├── fixtures/
│ │ ├── scene.py # Track 0 synthetic data
│ │ ├── graph_fixtures.py
│ │ └── mask_fixtures.py
│ ├── test_02_osm_loader.py
│ ├── test_03_graph_builder.py
│ ├── test_04_mask_adapter.py
│ ├── test_05_cutoff.py
│ ├── test_impact.py
│ └── test_integration.py
├── docs/
│ ├── learn/
│ │ ├── 01-api.md # Schema design
│ │ ├── 02-osm.md # Ohsome tiling + caching
│ │ ├── 03-graph.md # Noding + snapping
│ │ ├── 04-mask.md # Raster polygonization
│ │ └── 05-cutoff.md # Dijkstra routing
│ ├── limitations.md # Technical constraints
│ └── mock_output.json # Example AnalysisResult
├── configs/
│ ├── trishuli.yaml
│ └── chamoli.yaml
├── pyproject.toml
├── PROGRESS.md
└── README.md (this file)

## Key Design Decisions

- **Snapping tolerance: 5 metres** — balances digitisation jitter correction vs. false connections
- **Settlement snap distance: 500 metres** — beyond this = NO_MAPPED_ROAD_ACCESS (OSM gap, not flood impact)
- **Minimum polygon area: 100 m²** — filters SAR speckle noise
- **Super-destination routing** — one virtual node connected to all hospitals/towns enables efficient multi-destination Dijkstra
- **Sensitivity sweep** — reruns analysis with buffer/overlap parameter grids to compute confidence scores

See `PROGRESS.md` for full decision log.

## Output Schema

See `gis_engine/schemas.py` for the complete Pydantic v2 AnalysisResult model.

### Key Statistics
- `flood_area_km2` — Total flooded area
- `affected_road_km` — Sum of road lengths overlapping flood
- `assessed_area_fraction` — Fraction of bbox with valid satellite data (0.0–1.0)
- `n_settlements_*` — Counts by status (connected, cut_off, no_road, unknown, inside_flood)

### Settlement Status
- **CONNECTED:** Reachable before and after
- **POTENTIALLY_CUT_OFF:** Was reachable before, not after (confidence: 0–1)
- **NO_MAPPED_ROAD_ACCESS:** >500m from any road (not a flood impact)
- **INSIDE_FLOOD_ZONE:** Settlement point within flood polygon
- **UNKNOWN_NO_DATA:** Route depends on unassessed area (radar shadow/cloud)

## Data Requirements

### Input
- **Flood mask:** GeoTIFF, uint8 (0=no flood, 1=flood/debris, 255=no data)
- **Valid-data mask:** GeoTIFF, uint8 (0=valid, 1=no data, 2=radar shadow, 3=cloud)
- Both on same UTM grid (CRS and transform must match exactly)

### Output
All geometries reprojected to EPSG:4326 (WGS84 lat/lon) for frontend consumption.

## Limitations
See `docs/limitations.md` for technical constraints (OSM gaps, overlap ≠ destruction, satellite revisit intervals, unassessed areas).

## Attribution
- © OpenStreetMap contributors (ODbL)
- Sentinel-1, Sentinel-2 data: Copernicus (free, full, open policy)
- Copernicus DEM (used in some analyses)

## Contact
Member 3 (GIS/Backend): This module.