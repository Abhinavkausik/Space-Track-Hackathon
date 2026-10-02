import pytest
import networkx as nx
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon

from tests.fixtures.scene import get_fixture_data
from gis_engine.graph_builder import build_road_graph
from gis_engine.cutoff import (
    analyze_cutoff,
    add_super_destination,
    snap_points_to_graph,
    remove_flooded_edges,
    compute_reachability,
    flag_unassessed_edges
)

def test_cutoff_on_scene_fixture():
    roads_gdf, dest_gdf, settlements_gdf, flood_gdf = get_fixture_data()
    G, _ = build_road_graph(roads_gdf, snap_tolerance_m=0)
    
    towns_gdf = dest_gdf[dest_gdf["type"] == "town"]
    hospitals_gdf = dest_gdf[dest_gdf["type"] == "hospital"]
    
    # We have no unassessed areas in fixture, create empty
    unassessed_gdf = gpd.GeoDataFrame(columns=["geometry"], crs=roads_gdf.crs)
    
    result = analyze_cutoff(G, settlements_gdf, towns_gdf, hospitals_gdf, flood_gdf, unassessed_gdf)
    
    stats = result["statistics"]
    # Track 0 fixture: 6 settlements, 1 flood edge (R6), 
    # expected: 2 cut-off, 1 no_road, 3 connected.
    # Wait, S1 (connected), S2 (cut-off), S3 (cut-off), S4 (connected), S5 (connected), S6 (no road)
    # Are there any inside the flood zone?
    # Flood is [(50, 140), (150, 140), (150, 160), (50, 160)]
    # S2 is at (105, 200) - outside
    # S3 is at (100, 305) - outside
    assert stats["POTENTIALLY_CUT_OFF"] == 2
    assert stats["NO_MAPPED_ROAD_ACCESS"] == 1
    assert stats["CONNECTED"] == 3

def test_super_destination_reachability():
    roads_gdf, dest_gdf, _, _ = get_fixture_data()
    G, _ = build_road_graph(roads_gdf, snap_tolerance_m=0)
    super_dest, node_to_name = add_super_destination(G, dest_gdf, gpd.GeoDataFrame())
    
    assert super_dest in G.nodes()
    # Check that destinations are connected to SUPER_DEST with 0 length
    edges = G.edges(super_dest, data=True)
    assert len(edges) == len(dest_gdf)
    for u, v, d in edges:
        assert d["length_m"] == 0.0

def test_snapping_beyond_tolerance():
    roads_gdf, _, _, _ = get_fixture_data()
    G, _ = build_road_graph(roads_gdf, snap_tolerance_m=0)
    
    # Create settlement far away
    far_gdf = gpd.GeoDataFrame([{"geometry": Point(10000, 10000)}], crs=roads_gdf.crs)
    snap_map = snap_points_to_graph(far_gdf, G, max_snap_m=500)
    
    assert snap_map[0] is None

def test_edge_removal_cuts_settlements():
    roads_gdf, _, _, _ = get_fixture_data()
    G, _ = build_road_graph(roads_gdf, snap_tolerance_m=0)
    
    # Remove R2, which connects (100,0) to (200,0)
    flood = [{"geometry": Polygon([(120, -10), (180, -10), (180, 10), (120, 10)])}]
    flood_gdf = gpd.GeoDataFrame(flood, crs=roads_gdf.crs)
    
    after_g = remove_flooded_edges(G, flood_gdf)
    
    # R2 should be gone. Edges count should drop.
    assert after_g.number_of_edges() < G.number_of_edges()

def test_sensitivity_confidence_in_range():
    roads_gdf, dest_gdf, settlements_gdf, flood_gdf = get_fixture_data()
    G, _ = build_road_graph(roads_gdf, snap_tolerance_m=0)
    towns_gdf = dest_gdf[dest_gdf["type"] == "town"]
    
    unassessed_gdf = gpd.GeoDataFrame(columns=["geometry"], crs=roads_gdf.crs)
    result = analyze_cutoff(G, settlements_gdf, towns_gdf, gpd.GeoDataFrame(), flood_gdf, unassessed_gdf)
    
    for s in result["settlements"]:
        assert 0.0 <= s["confidence"] <= 1.0

def test_unassessed_creates_unknown_status():
    roads_gdf, dest_gdf, settlements_gdf, flood_gdf = get_fixture_data()
    G, _ = build_road_graph(roads_gdf, snap_tolerance_m=0)
    towns_gdf = dest_gdf[dest_gdf["type"] == "town"]
    
    # Create an unassessed polygon covering the main highway (which S4 uses)
    unassessed = [{"geometry": Polygon([(250, -10), (350, -10), (350, 10), (250, 10)])}]
    unassessed_gdf = gpd.GeoDataFrame(unassessed, crs=roads_gdf.crs)
    
    # Empty flood mask so it's not cut off
    empty_flood = gpd.GeoDataFrame(columns=["geometry"], crs=roads_gdf.crs)
    
    result = analyze_cutoff(G, settlements_gdf, towns_gdf, gpd.GeoDataFrame(), empty_flood, unassessed_gdf)
    
    # S4 (at 300, 205) should now route through the unassessed area (around 300, 0)
    s4_res = next(s for s in result["settlements"] if s["name"] == "S4_Conn")
    assert s4_res["status"] == "UNKNOWN_NO_DATA"
