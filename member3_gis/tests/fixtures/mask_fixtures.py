import numpy as np
import rasterio
from rasterio.transform import from_origin
import tempfile
import os
from typing import Tuple

def synthetic_flood_raster() -> Tuple[str, str, np.ndarray, np.ndarray, rasterio.Affine, str]:
    """
    Creates a synthetic 100x100 raster and writes to temporary GeoTIFF files.
    Returns:
        flood_path, valid_path, flood_arr, valid_arr, transform, crs
    """
    # Create arrays
    flood_arr = np.zeros((100, 100), dtype=np.uint8)
    valid_arr = np.zeros((100, 100), dtype=np.uint8)
    
    # 1. Flood zone (10x10) -> Area: 100 pixels * (10m*10m) = 10,000 m2
    flood_arr[10:20, 10:20] = 1
    
    # 2. Radar shadow (unassessed reason 2) (10x10) -> Area 10,000 m2
    valid_arr[50:60, 50:60] = 2
    
    # 3. No data in flood mask (unassessed reason 1 via fallback if not specified in valid_mask)
    flood_arr[80:90, 80:90] = 255
    valid_arr[80:90, 80:90] = 0 # It claims valid, but flood is 255
    
    # 4. Tiny flood artifact (2x2) -> Area 400 m2
    flood_arr[30:32, 30:32] = 1
    
    # 5. Micro flood artifact (1x1) -> Area 100 m2
    flood_arr[40, 40] = 1
    
    # Define spatial properties (UTM EPSG:32645, 10m pixels)
    transform = from_origin(300000.0, 3100000.0, 10, 10)
    crs = "EPSG:32645"
    
    # Write to temp files
    fd_flood, flood_path = tempfile.mkstemp(suffix=".tif")
    os.close(fd_flood)
    
    fd_valid, valid_path = tempfile.mkstemp(suffix=".tif")
    os.close(fd_valid)
    
    meta = {
        'driver': 'GTiff',
        'dtype': 'uint8',
        'nodata': None,
        'width': 100,
        'height': 100,
        'count': 1,
        'crs': crs,
        'transform': transform
    }
    
    with rasterio.open(flood_path, 'w', **meta) as dst:
        dst.write(flood_arr, 1)
        
    with rasterio.open(valid_path, 'w', **meta) as dst:
        dst.write(valid_arr, 1)
        
    return flood_path, valid_path, flood_arr, valid_arr, transform, crs
