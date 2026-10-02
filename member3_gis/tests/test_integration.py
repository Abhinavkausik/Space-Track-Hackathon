import pytest
from fastapi.testclient import TestClient
from datetime import date
import os
import tempfile
import numpy as np
import rasterio
from rasterio.transform import from_origin
from unittest import mock
import geopandas as gpd

from gis_engine.api import app
from tests.fixtures.scene import get_fixture_data

client = TestClient(app)

def mock_load_osm_data(*args, **kwargs):
    roads_gdf, dest_gdf, settlements_gdf, _ = get_fixture_data()
    towns_gdf = dest_gdf[dest_gdf["type"] == "town"]
    hospitals_gdf = dest_gdf[dest_gdf["type"] == "hospital"]
    # empty buildings for fixture
    buildings_gdf = gpd.GeoDataFrame(columns=["geometry"], crs=roads_gdf.crs)
    return {
        "highways": roads_gdf,
        "buildings": buildings_gdf,
        "places": settlements_gdf,
        "hospitals": hospitals_gdf,
        "towns": towns_gdf
    }

@pytest.fixture
def synthetic_masks():
    flood_arr = np.zeros((100, 100), dtype=np.uint8)
    valid_arr = np.zeros((100, 100), dtype=np.uint8)
    
    # R6 in fixture goes from (100, 100) to (100, 200)
    # We create a flood from (50, 140) to (150, 160)
    # Origin is at 0, 0, resolution 10
    # X=50 -> col 5, X=150 -> col 15
    # Y=140 -> row (assuming origin top left or bottom left, let's just make it big)
    flood_arr[40:60, 5:15] = 1 
    
    transform = from_origin(0.0, 500.0, 10, 10)
    crs = "EPSG:32645"
    
    fd_f, flood_path = tempfile.mkstemp(suffix=".tif")
    os.close(fd_f)
    fd_v, valid_path = tempfile.mkstemp(suffix=".tif")
    os.close(fd_v)
    
    meta = {
        'driver': 'GTiff', 'dtype': 'uint8', 'nodata': None,
        'width': 100, 'height': 100, 'count': 1,
        'crs': crs, 'transform': transform
    }
    
    with rasterio.open(flood_path, 'w', **meta) as dst:
        dst.write(flood_arr, 1)
    with rasterio.open(valid_path, 'w', **meta) as dst:
        dst.write(valid_arr, 1)
        
    yield flood_path, valid_path
    
    os.remove(flood_path)
    os.remove(valid_path)

@mock.patch('gis_engine.pipeline.load_osm_data', side_effect=mock_load_osm_data)
def test_full_pipeline_on_fixture(mock_load, synthetic_masks):
    from gis_engine.pipeline import analyze_full
    flood_path, valid_path = synthetic_masks
    
    result = analyze_full(
        bbox=(0, 0, 1000, 1000),
        event_date=date(2026, 8, 26),
        flood_mask_path=flood_path,
        valid_mask_path=valid_path
    )
    
    # Check schema
    assert "metadata" in result
    assert "statistics" in result
    assert "settlements" in result
    
    stats = result["statistics"]
    assert stats["n_settlements_total"] == 6
    # Exact connected vs cutoff depends on intersection with synthetic mask, but it shouldn't crash!
    assert stats["n_settlements_connected"] + stats["n_settlements_cut_off"] + stats["n_settlements_no_road"] == 6

@mock.patch('gis_engine.pipeline.load_osm_data', side_effect=mock_load_osm_data)
def test_api_endpoint_success(mock_load, synthetic_masks):
    flood_path, valid_path = synthetic_masks
    
    payload = {
        "bbox": [0, 0, 1000, 1000],
        "event_date": "2026-08-26",
        "flood_mask_path": flood_path,
        "valid_mask_path": valid_path
    }
    
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["statistics"]["n_settlements_total"] == 6

def test_api_endpoint_error_handling():
    payload = {
        "bbox": [0, 0, 1000, 1000],
        "event_date": "2026-08-26",
        "flood_mask_path": "invalid_path.tif",
        "valid_mask_path": "invalid_path.tif"
    }
    
    response = client.post("/analyze", json=payload)
    assert response.status_code == 400
    assert "Mask files do not exist" in response.text
