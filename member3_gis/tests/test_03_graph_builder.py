import pytest
import networkx as nx
from shapely.geometry import LineString
import geopandas as gpd
from hypothesis import given, strategies as st

from tests.fixtures.scene import get_fixture_data
from tests.fixtures.graph_fixtures import create_synthetic_roads
from gis_engine.graph_builder import node_geometries, build_road_graph, is_connected

def test_graph_builder_on_scene_fixture():
    roads_gdf, dest_gdf, settlements_gdf, flood_gdf = get_fixture_data()
    G, summary = build_road_graph(roads_gdf, snap_tolerance_m=0) # No snapping needed for exact grid
    
    assert summary["n_nodes"] == 11 # A, B, C, D, E, F, G, K, H, I, J... Wait, how many nodes? Let's check:
    # Main: A, B, C, D, E
    # Branch 1: F, G, K
    # Branch 2: H, I
    # Branch 3: J
    # Wait, B is shared, C is shared, D is shared. 
    # Total unique points: 11
    assert isinstance(G, nx.MultiGraph)
    assert summary["n_edges"] >= len(roads_gdf)
    
    # Check is_bridge
    edge_R9_found = False
    for u, v, data in G.edges(data=True):
        if data["is_bridge"]:
            edge_R9_found = True
    assert edge_R9_found

def test_snapping_close_endpoints():
    # Two lines that are 4m apart. Should snap and connect if tolerance=5
    l1 = LineString([(0, 0), (100, 0)])
    l2 = LineString([(100, 4), (200, 4)])
    gdf = create_synthetic_roads([l1, l2])
    
    G, summary = build_road_graph(gdf, snap_tolerance_m=5)
    
    # Should be 1 connected component
    assert summary["connected_components"] == 1
    assert is_connected(G) is True

def test_snapping_far_endpoints():
    # Two lines that are 6m apart. Should NOT snap if tolerance=5
    l1 = LineString([(0, 0), (100, 0)])
    l2 = LineString([(100, 6), (200, 6)])
    gdf = create_synthetic_roads([l1, l2])
    
    G, summary = build_road_graph(gdf, snap_tolerance_m=5)
    
    # Should be 2 connected components
    assert summary["connected_components"] == 2
    assert is_connected(G) is False

def test_length_computation():
    # A known line segment: lon 0 to 1 at equator is ~111.32 km.
    # In UTM it will be measured correctly. We just use EPSG:4326 and let it estimate UTM.
    l1 = LineString([(0, 0), (1, 0)])
    gdf = create_synthetic_roads([l1], crs="EPSG:4326")
    
    G, summary = build_road_graph(gdf, snap_tolerance_m=5)
    
    # 1 degree at equator is approx 111,319 meters
    length = summary["total_road_length_m"]
    assert 111000 < length < 112000

def test_multigraph_parallel_edges():
    # Two parallel roads between same points, following different geometric paths
    l1 = LineString([(0, 0), (50, 10), (100, 0)])
    l2 = LineString([(0, 0), (50, -10), (100, 0)])
    gdf = create_synthetic_roads([l1, l2])
    
    G, summary = build_road_graph(gdf, snap_tolerance_m=5)
    
    assert summary["n_edges"] == 2
    assert G.number_of_edges() == 2

@given(
    x1=st.floats(0, 100), y1=st.floats(0, 100),
    x2=st.floats(0, 100), y2=st.floats(0, 100),
    x3=st.floats(0, 100), y3=st.floats(0, 100)
)
def test_noding_is_idempotent(x1, y1, x2, y2, x3, y3):
    # Two lines that might intersect
    # x1,y1 to x2,y2
    # x2,y2 to x3,y3
    if (x1, y1) == (x2, y2) or (x2, y2) == (x3, y3):
        return
        
    l1 = LineString([(x1, y1), (x2, y2)])
    l2 = LineString([(x2, y2), (x3, y3)])
    
    gdf = create_synthetic_roads([l1, l2])
    
    # Node once
    noded1 = node_geometries(gdf, snap_tolerance_m=1.0)
    
    # Node twice
    noded2 = node_geometries(noded1, snap_tolerance_m=1.0)
    
    # The geometries should be practically identical in count
    assert len(noded1) == len(noded2)
