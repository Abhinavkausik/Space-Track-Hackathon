# OSM Data Loading and Tiling

This document explains our approach to fetching OpenStreetMap (OSM) data using the Ohsome API, how we handle large areas using a tiling strategy, and how we cache the results for rapid local development.

## The Ohsome API

Ohsome is an open-source analytics platform for OSM history. Unlike the Overpass API which returns the current state of OSM data, Ohsome allows us to request a snapshot of OSM data at a specific point in time.

### Why `snapshot_date`?

During disaster response and analysis, it is crucial to analyze the baseline infrastructure as it existed **before** the event. 
If we use current OSM data, it might contain post-disaster edits (like destroyed buildings being removed or temporary camps being added), which pollutes our baseline analysis.

We require a `snapshot_date` parameter when loading OSM data, and we assert that this date is strictly before the `event_date`.

## Fetching and Retries

The Ohsome API limits request rates. We implement a retry mechanism for HTTP 429 (Too Many Requests) errors using exponential backoff (e.g., wait 1s, then 2s, 4s... up to 5 retries).

## Tiling Strategy

Ohsome requests can timeout (HTTP 413 or 504) if the bounding box is too large or contains too much data. To avoid this, we implement a **tiling** strategy:

1. We take the input bounding box.
2. We split it into smaller tiles of roughly 0.1° x 0.1° (~11km x 11km).
3. We fetch each tile sequentially (with retries for 429s).
4. If a tile times out or fails (e.g., HTTP 413), we log a warning, mark the result as "partial" in our metadata, but we continue processing the remaining tiles.
5. Finally, we merge all successful tiles into a single `GeoDataFrame`.

## Caching with GeoParquet

To speed up repeated runs and avoid spamming the Ohsome API, we cache the downloaded data locally.
The cache key is a hash of:
- The bounding box `(minx, miny, maxx, maxy)`
- The `snapshot_date`
- The `filter_name` (e.g., "highways", "buildings")

We save the resulting GeoDataFrame as a GeoParquet file in `member3_gis/cache/osm/{hash}.parquet`. If a cache file exists, we load it instead of hitting the API, unless the `cache_bust=True` flag is set.

## Example

```python
from datetime import datetime, timezone
from gis_engine.loaders.osm_loader import load_osm_data

bbox = (85.2, 27.6, 85.4, 27.8)
event_date = datetime(2015, 4, 25, tzinfo=timezone.utc)
snapshot_date = datetime(2015, 4, 1, tzinfo=timezone.utc)

# This will tile the bounding box, fetch data from Ohsome, and cache it locally
osm_data = load_osm_data(
    bbox=bbox, 
    snapshot_date=snapshot_date, 
    event_date=event_date
)

# Access individual layers
highways_gdf = osm_data["highways"]
buildings_gdf = osm_data["buildings"]
```
