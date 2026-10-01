import pytest
from tests.fixtures.scene import get_fixture_data

def test_fixture_integrity():
    roads_gdf, dest_gdf, settlements_gdf, flood_gdf = get_fixture_data()
    
    # 1. Total counts
    assert len(roads_gdf) == 10
    assert len(roads_gdf[roads_gdf["bridge"] == True]) == 1
    assert len(dest_gdf) == 2
    assert len(settlements_gdf) == 6
    assert len(flood_gdf) == 1
    
    # 2. Check CRS
    assert roads_gdf.crs.to_string() == "EPSG:32645"
    assert settlements_gdf.crs.to_string() == "EPSG:32645"
    
    # 3. Check flood intersection
    # Flood intersects R6, but no other roads.
    intersecting_roads = roads_gdf[roads_gdf.intersects(flood_gdf.unary_union)]
    assert len(intersecting_roads) == 1
    assert intersecting_roads.iloc[0]["id"] == "R6"
