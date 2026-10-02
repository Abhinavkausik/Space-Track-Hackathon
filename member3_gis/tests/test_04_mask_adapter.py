import os
import tempfile

import numpy as np
import pytest
import rasterio
from hypothesis import given, strategies as st
from rasterio.transform import from_origin

from gis_engine.mask_adapter import (
    compute_assessed_area_fraction,
    process_masks,
    validate_mask_pair,
)
from tests.fixtures.mask_fixtures import synthetic_flood_raster


def test_process_masks_on_synthetic_raster():
    flood_path, valid_path, flood_arr, valid_arr, transform, crs = synthetic_flood_raster()

    try:
        # min_area_m2=200 should filter out the 1x1 (100m2) artifact but keep the 2x2 (400m2)
        flood_gdf, unassessed_gdf, fraction = process_masks(flood_path, valid_path, min_area_m2=200)

        # Flood should have 2 polygons: the 10x10 and the 2x2
        assert len(flood_gdf) == 2
        areas = sorted(flood_gdf["area_m2"].tolist())
        assert areas == [400.0, 10000.0]

        # Unassessed should have 2 polygons: 
        # 1. 10x10 radar shadow (reason: radar_shadow) -> 10000 m2
        # 2. 10x10 no data (reason: no_data) -> 10000 m2
        assert len(unassessed_gdf) == 2
        reasons = sorted(unassessed_gdf["reason"].tolist())
        assert reasons == ["no_data", "radar_shadow"]
        assert list(unassessed_gdf["area_m2"]) == [10000.0, 10000.0]

        # Assessed fraction: Total 10000 pixels. 100 radar shadow + 100 no data = 200 unassessed.
        # So 9800 assessed pixels out of 10000 -> 0.98
        assert fraction == 0.98

    finally:
        os.remove(flood_path)
        os.remove(valid_path)


def test_mask_mismatch_raises():
    flood_path, valid_path, _, _, transform, crs = synthetic_flood_raster()
    
    # Create a mismatched file
    fd, bad_path = tempfile.mkstemp(suffix=".tif")
    os.close(fd)
    
    meta = {
        'driver': 'GTiff',
        'dtype': 'uint8',
        'nodata': None,
        'width': 50, # Different shape
        'height': 100,
        'count': 1,
        'crs': crs,
        'transform': transform
    }
    
    with rasterio.open(bad_path, 'w', **meta) as dst:
        dst.write(np.zeros((100, 50), dtype=np.uint8), 1)
        
    try:
        with pytest.raises(AssertionError, match="Shape mismatch"):
            validate_mask_pair(flood_path, bad_path)
    finally:
        os.remove(flood_path)
        os.remove(valid_path)
        os.remove(bad_path)


def test_area_filter_removes_small_polygons():
    flood_path, valid_path, _, _, _, _ = synthetic_flood_raster()
    
    try:
        # 500m2 minimum should filter out both 1x1 (100) and 2x2 (400)
        flood_gdf, _, _ = process_masks(flood_path, valid_path, min_area_m2=500)
        assert len(flood_gdf) == 1
        assert flood_gdf["area_m2"].iloc[0] == 10000.0
    finally:
        os.remove(flood_path)
        os.remove(valid_path)


@given(
    valid_count=st.integers(0, 10000),
    total_count=st.integers(1, 10000)
)
def test_property_fraction_in_range(valid_count, total_count):
    # Hypothesis test
    if valid_count > total_count:
        valid_count = total_count
        
    arr = np.ones(total_count, dtype=np.uint8)
    arr[:valid_count] = 0 # 0 is valid
    
    fraction = compute_assessed_area_fraction(arr, from_origin(0, 0, 10, 10), 100.0)
    
    assert 0.0 <= fraction <= 1.0
    assert fraction == valid_count / total_count
