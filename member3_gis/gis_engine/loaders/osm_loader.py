import hashlib
import json
import logging
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import geopandas as gpd
import pandas as pd
import requests

logger = logging.getLogger(__name__)

OHSOME_API_URL = "https://api.ohsome.org/v1/elements/geometry"

LAYERS_CONFIG = {
    "highways": {
        "filter": "highway=*",
        "columns": ["name", "name:en", "name:ne", "highway", "bridge", "geometry"],
    },
    "buildings": {
        "filter": "building=*",
        "columns": ["name", "building", "geometry"],
    },
    "places": {
        "filter": "place=* and type:node",
        "columns": ["name", "name:en", "name:ne", "place", "geometry"],
    },
    "hospitals": {
        "filter": "amenity=hospital",
        "columns": ["amenity", "geometry"],
    },
    "towns": {
        "filter": "place=town or place=city",
        "columns": ["place", "geometry"],
    },
}


def _get_cache_dir() -> Path:
    cache_dir = Path(__file__).parent.parent.parent / "cache" / "osm"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _generate_cache_key(bbox: Tuple[float, float, float, float], snapshot_date: datetime, filter_name: str) -> str:
    # Hash bounding box, snapshot date, and filter name
    bbox_str = f"{bbox[0]:.4f},{bbox[1]:.4f},{bbox[2]:.4f},{bbox[3]:.4f}"
    date_str = snapshot_date.isoformat()
    raw = f"{bbox_str}|{date_str}|{filter_name}".encode("utf-8")
    return hashlib.md5(raw).hexdigest()


def _create_tiles(bbox: Tuple[float, float, float, float], step: float = 0.1) -> List[Tuple[float, float, float, float]]:
    minx, miny, maxx, maxy = bbox
    tiles = []
    
    eps = 1e-9
    x = minx
    while x < maxx - eps:
        y = miny
        next_x = round(min(x + step, maxx), 6)
        while y < maxy - eps:
            next_y = round(min(y + step, maxy), 6)
            tiles.append((x, y, next_x, next_y))
            y = next_y
        x = next_x
            
    return tiles


def _fetch_ohsome_tile(bbox: Tuple[float, float, float, float], snapshot_date: datetime, filter_str: str) -> dict:
    """Fetch a single tile from Ohsome API with retries."""
    bboxes_str = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    time_str = snapshot_date.isoformat().replace("+00:00", "")
    if not time_str.endswith("Z"):
        time_str += "Z"
        
    data = {
        "bboxes": bboxes_str,
        "time": time_str,
        "filter": filter_str,
        "properties": "tags",
    }
    
    retries = [1, 2, 4, 8, 16]
    for attempt, wait_time in enumerate(retries):
        try:
            response = requests.post(OHSOME_API_URL, data=data, timeout=30)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                if attempt == len(retries) - 1:
                    logger.error("Max retries reached for 429 Too Many Requests.")
                    break
                logger.warning(f"429 Too Many Requests. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            elif response.status_code in (413, 504):
                logger.warning(f"Ohsome API timeout/too large (HTTP {response.status_code}) for tile {bboxes_str}.")
                return None
            else:
                response.raise_for_status()
        except requests.RequestException as e:
            if attempt == len(retries) - 1:
                logger.error(f"Failed to fetch tile {bboxes_str}: {e}")
                return None
            logger.warning(f"Request failed: {e}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
    
    return None


def fetch_layer(bbox: Tuple[float, float, float, float], snapshot_date: datetime, filter_name: str, cache_bust: bool = False) -> gpd.GeoDataFrame:
    config = LAYERS_CONFIG[filter_name]
    filter_str = config["filter"]
    required_cols = config["columns"]
    
    cache_key = _generate_cache_key(bbox, snapshot_date, filter_name)
    cache_path = _get_cache_dir() / f"{cache_key}.parquet"
    
    if not cache_bust and cache_path.exists():
        logger.info(f"Loading {filter_name} from cache: {cache_path}")
        return gpd.read_parquet(cache_path)
        
    tiles = _create_tiles(bbox, step=0.1)
    gdfs = []
    
    for i, tile_bbox in enumerate(tiles):
        logger.debug(f"Fetching {filter_name} tile {i+1}/{len(tiles)}")
        feature_collection = _fetch_ohsome_tile(tile_bbox, snapshot_date, filter_str)
        
        if feature_collection and feature_collection.get("features"):
            gdf = gpd.GeoDataFrame.from_features(feature_collection["features"], crs="EPSG:4326")
            
            # Ensure required columns exist, fill with None if missing
            for col in required_cols:
                if col not in gdf.columns and col != "geometry":
                    gdf[col] = None
                    
            # Keep only required columns that are present
            available_cols = [c for c in required_cols if c in gdf.columns]
            gdf = gdf[available_cols]
            gdfs.append(gdf)
            
    if gdfs:
        merged_gdf = pd.concat(gdfs, ignore_index=True)
        # Drop duplicates in case tiles overlap elements
        if "geometry" in merged_gdf.columns:
            # Drop purely identical rows
            merged_gdf = merged_gdf.drop_duplicates()
    else:
        # Return empty GeoDataFrame with correct columns
        merged_gdf = gpd.GeoDataFrame(columns=required_cols, geometry="geometry", crs="EPSG:4326")
        
    # Cache the result
    merged_gdf.to_parquet(cache_path)
    return merged_gdf


def load_osm_data(bbox: Tuple[float, float, float, float], snapshot_date: datetime, event_date: datetime, cache_bust: bool = False) -> Dict[str, gpd.GeoDataFrame]:
    """
    Load OSM data for a bounding box at a specific snapshot date.
    """
    assert snapshot_date < event_date, "snapshot_date must be earlier than event_date"
    
    results = {}
    for layer_name in LAYERS_CONFIG.keys():
        results[layer_name] = fetch_layer(bbox, snapshot_date, layer_name, cache_bust=cache_bust)
        
    return results
