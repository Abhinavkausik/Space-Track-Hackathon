import geopandas as gpd
from shapely.geometry import LineString
from typing import List, Dict

CRS_UTM = "EPSG:32645"
CRS_WGS84 = "EPSG:4326"

def create_synthetic_roads(lines: List[LineString], crs=CRS_UTM) -> gpd.GeoDataFrame:
    data = []
    for i, line in enumerate(lines):
        data.append({
            "id": f"R{i}",
            "geometry": line,
            "highway": "residential",
            "bridge": False,
            "osm_way_id": i
        })
    return gpd.GeoDataFrame(data, crs=crs)
