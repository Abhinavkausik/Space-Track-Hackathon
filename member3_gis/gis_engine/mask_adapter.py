import numpy as np
import rasterio
from rasterio.features import shapes
import geopandas as gpd
from shapely.geometry import shape
from typing import Tuple, Dict

def validate_mask_pair(flood_mask_path: str, valid_mask_path: str) -> None:
    with rasterio.open(flood_mask_path) as src_flood, rasterio.open(valid_mask_path) as src_valid:
        if src_flood.shape != src_valid.shape:
            raise AssertionError(f"Shape mismatch: {src_flood.shape} vs {src_valid.shape}")
        if src_flood.crs != src_valid.crs:
            raise AssertionError(f"CRS mismatch: {src_flood.crs} vs {src_valid.crs}")
        if src_flood.transform != src_valid.transform:
            raise AssertionError(f"Transform mismatch: {src_flood.transform} vs {src_valid.transform}")

def read_masks(flood_mask_path: str, valid_mask_path: str) -> Tuple[np.ndarray, np.ndarray, rasterio.crs.CRS, rasterio.Affine]:
    validate_mask_pair(flood_mask_path, valid_mask_path)
    with rasterio.open(flood_mask_path) as src_flood:
        flood_arr = src_flood.read(1)
        crs = src_flood.crs
        transform = src_flood.transform
    with rasterio.open(valid_mask_path) as src_valid:
        valid_arr = src_valid.read(1)
    return flood_arr, valid_arr, crs, transform

def extract_flood_polygons(flood_pixels: np.ndarray, transform: rasterio.Affine, crs: rasterio.crs.CRS, min_area_m2: float = 100) -> gpd.GeoDataFrame:
    # flood_pixels is a boolean or 0/1 array
    mask = flood_pixels > 0
    if not np.any(mask):
        return gpd.GeoDataFrame(columns=["geometry", "area_m2"], geometry="geometry", crs=crs)
        
    polygons = []
    # shapes() returns (geojson_dict, value)
    for geom_dict, val in shapes(flood_pixels.astype(np.uint8), mask=mask, transform=transform):
        if val > 0:
            poly = shape(geom_dict)
            area = poly.area
            if area >= min_area_m2:
                polygons.append({"geometry": poly, "area_m2": area})
                
    if not polygons:
        return gpd.GeoDataFrame(columns=["geometry", "area_m2"], geometry="geometry", crs=crs)
        
    return gpd.GeoDataFrame(polygons, crs=crs)

def extract_unassessed_polygons(valid_pixels: np.ndarray, reason_map: Dict[int, str], transform: rasterio.Affine, crs: rasterio.crs.CRS, min_area_m2: float = 100) -> gpd.GeoDataFrame:
    # valid_pixels contains 1, 2, 3... 0 is valid (so ignored for unassessed)
    mask = valid_pixels > 0
    if not np.any(mask):
        return gpd.GeoDataFrame(columns=["geometry", "area_m2", "reason"], geometry="geometry", crs=crs)
        
    polygons = []
    for geom_dict, val in shapes(valid_pixels.astype(np.uint8), mask=mask, transform=transform):
        val = int(val)
        if val > 0:
            poly = shape(geom_dict)
            area = poly.area
            if area >= min_area_m2:
                reason = reason_map.get(val, f"unknown_{val}")
                polygons.append({"geometry": poly, "area_m2": area, "reason": reason})
                
    if not polygons:
        return gpd.GeoDataFrame(columns=["geometry", "area_m2", "reason"], geometry="geometry", crs=crs)
        
    return gpd.GeoDataFrame(polygons, crs=crs)

def compute_assessed_area_fraction(valid_mask: np.ndarray, transform: rasterio.Affine, pixel_area_m2: float) -> float:
    total_pixels = valid_mask.size
    if total_pixels == 0:
        return 0.0
    assessed_pixels = np.count_nonzero(valid_mask == 0)
    return float(assessed_pixels) / float(total_pixels)

def process_masks(flood_mask_path: str, valid_mask_path: str, min_area_m2: float = 100) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, float]:
    flood_arr, valid_arr, crs, transform = read_masks(flood_mask_path, valid_mask_path)
    
    # 1. Compute derived arrays
    # flood_pixels = (flood_mask == 1) AND (valid_mask == 0)
    flood_pixels = np.logical_and(flood_arr == 1, valid_arr == 0).astype(np.uint8)
    
    # unassessed categoricals
    # We want a combined categorical array:
    # If valid_arr != 0, it takes precedence.
    # If valid_arr == 0 AND flood_arr == 255, we assign it reason 1 (no_data)
    unassessed_arr = np.copy(valid_arr)
    no_data_mask = np.logical_and(valid_arr == 0, flood_arr == 255)
    unassessed_arr[no_data_mask] = 1
    
    # 2. Extract polygons
    flood_gdf = extract_flood_polygons(flood_pixels, transform, crs, min_area_m2)
    
    reason_map = {0: "valid", 1: "no_data", 2: "radar_shadow", 3: "cloud"}
    unassessed_gdf = extract_unassessed_polygons(unassessed_arr, reason_map, transform, crs, min_area_m2)
    
    # 3. Compute fraction
    # The true "assessed" area is where valid_arr == 0 AND flood_arr != 255
    # Let's create a strictly assessed mask for area calc:
    strictly_assessed = unassessed_arr # where this == 0
    # Wait, the prompt says:
    # compute assessed_area_fraction = area(valid_mask==0) / total_bbox_area
    # But then later "create a grid with 80 valid pixels and 20 nodata; fraction should be ~0.8."
    # We will use the unassessed_arr to compute this so that flood=255 is properly counted as nodata.
    pixel_area_m2 = abs(transform.a * transform.e)
    fraction = compute_assessed_area_fraction(unassessed_arr, transform, pixel_area_m2)
    
    return flood_gdf, unassessed_gdf, fraction

def reproject_to_wgs84(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Reprojects the polygons back to EPSG:4326 for output to the frontend."""
    if gdf.empty:
        # Just ensure crs is correct
        gdf = gdf.copy()
        gdf.crs = "EPSG:4326"
        return gdf
    return gdf.to_crs("EPSG:4326")
