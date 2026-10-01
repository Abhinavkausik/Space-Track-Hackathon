import numpy as np
import rasterio
from rasterio.transform import from_origin
from pathlib import Path

def generate_synthetic_masks(out_dir: Path, crs="EPSG:32645"):
    """
    Generates synthetic flood mask and valid mask GeoTIFFs for testing.
    Grid: 10m resolution.
    
    Flood mask codes:
    0 = no flood
    1 = flood/debris
    255 = no data
    
    Valid mask codes:
    0 = valid
    1 = no data
    2 = radar shadow/layover
    3 = cloud/cloud shadow
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    flood_path = out_dir / "flood_mask.tif"
    valid_path = out_dir / "valid_mask.tif"
    
    # 100x100 grid (1km x 1km)
    width, height = 100, 100
    transform = from_origin(300000.0, 3100000.0, 10, 10)
    
    flood_data = np.zeros((height, width), dtype=np.uint8)
    valid_data = np.zeros((height, width), dtype=np.uint8)
    
    # Introduce flood area (1)
    flood_data[20:40, 20:80] = 1
    
    # Introduce no-data in flood mask (255)
    flood_data[60:80, 60:80] = 255
    
    # Introduce valid mask issues
    # No data (1)
    valid_data[80:90, 80:90] = 1
    # Radar shadow (2)
    valid_data[10:30, 80:95] = 2
    # Cloud (3)
    valid_data[50:60, 10:30] = 3
    
    kwargs = {
        'driver': 'GTiff',
        'height': height,
        'width': width,
        'count': 1,
        'dtype': rasterio.uint8,
        'crs': crs,
        'transform': transform,
    }
    
    with rasterio.open(flood_path, 'w', nodata=255, **kwargs) as dst:
        dst.write(flood_data, 1)
        
    # the valid data doesn't necessarily have a single nodata value, 
    # but 1, 2, 3 all mean invalid. We can set nodata=1 maybe, or None.
    with rasterio.open(valid_path, 'w', **kwargs) as dst:
        dst.write(valid_data, 1)
        
    return flood_path, valid_path
