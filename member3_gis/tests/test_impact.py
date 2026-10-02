import pytest
import geopandas as gpd
from shapely.geometry import Polygon
import json

from tests.fixtures.scene import get_fixture_data
from gis_engine.graph_builder import build_road_graph
from gis_engine.impact import classify_infrastructure

def test_impact_on_fixture():
    roads_gdf, dest_gdf, settlements_gdf, flood_gdf = get_fixture_data()
    G, _ = build_road_graph(roads_gdf, snap_tolerance_m=0)
    
    # We create a dummy buildings_gdf that has 2 buildings:
    # 1 inside the flood zone, 1 outside.
    # Flood zone is [(50, 140), (150, 140), (150, 160), (50, 160)]
    b1 = Polygon([(60, 145), (70, 145), (70, 155), (60, 155)]) # inside
    b2 = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]) # outside
    
    buildings_gdf = gpd.GeoDataFrame(
        [{"id": "B1", "geometry": b1}, {"id": "B2", "geometry": b2}],
        crs=roads_gdf.crs
    )
    
    # Run impact
    # Wait, the graph edges might be in a different CRS if we don't handle it, but for the fixture it's all EPSG:32645
    result = classify_infrastructure(G, buildings_gdf, flood_gdf)
    
    # R6 is the only edge intersecting flood_gdf. Its length is 100m (from F to G).
    assert result["affected_road_km"] == 0.1 # 100m = 0.1km
    assert result["affected_bridges"] == 0 # R6 is not a bridge
    assert result["affected_buildings"] == 1 # B1
    
    # Verify geojson features
    roads_geojson = json.loads(result["affected_roads_geojson"])
    assert len(roads_geojson["features"]) == 1
    
    buildings_geojson = json.loads(result["affected_buildings_geojson"])
    assert len(buildings_geojson["features"]) == 1

def test_no_false_positives():
    roads_gdf, dest_gdf, settlements_gdf, _ = get_fixture_data()
    G, _ = build_road_graph(roads_gdf, snap_tolerance_m=0)
    
    # Empty flood polygon
    empty_flood = gpd.GeoDataFrame(columns=["geometry"], crs=roads_gdf.crs)
    
    buildings_gdf = gpd.GeoDataFrame([
        {"id": "B1", "geometry": Polygon([(0,0), (10,0), (10,10), (0,10)])}
    ], crs=roads_gdf.crs)
    
    result = classify_infrastructure(G, buildings_gdf, empty_flood)
    
    assert result["affected_road_km"] == 0.0
    assert result["affected_bridges"] == 0
    assert result["affected_buildings"] == 0
