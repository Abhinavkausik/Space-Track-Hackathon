import logging
from typing import Tuple

import geopandas as gpd
import networkx as nx
import numpy as np
import shapely
from shapely.ops import nearest_points

logger = logging.getLogger(__name__)


def node_geometries(gdf: gpd.GeoDataFrame, snap_tolerance_m: float = 5.0) -> gpd.GeoDataFrame:
    """
    Snaps endpoints and nodes geometries (splits at intersections).
    Preserves all attributes from the original GeoDataFrame.
    """
    if gdf.empty:
        return gdf

    orig_crs = gdf.crs
    is_geographic = orig_crs and orig_crs.is_geographic
    
    if is_geographic:
        # Transform to UTM to apply snap tolerance in meters
        utm_crs = gdf.estimate_utm_crs()
        gdf_working = gdf.to_crs(utm_crs)
    else:
        gdf_working = gdf.copy()

    lines = gdf_working.geometry.values
    tree = shapely.STRtree(lines)
    
    snapped_lines = list(lines)
    for i in range(len(snapped_lines)):
        line = snapped_lines[i]
        coords = list(line.coords)
        if not coords:
            continue
            
        modified = False
        for end_idx in [0, -1]:
            pt = shapely.Point(coords[end_idx])
            # Query original tree with double tolerance to catch points that moved towards us
            idx = tree.query(pt.buffer(snap_tolerance_m * 2.0))
            # Exclude self
            idx = idx[idx != i]
            if len(idx) > 0:
                nearby = shapely.GeometryCollection([snapped_lines[j] for j in idx])
                nearest_pt = nearest_points(pt, nearby)[1]
                if pt.distance(nearest_pt) <= snap_tolerance_m:
                    coords[end_idx] = (nearest_pt.x, nearest_pt.y)
                    modified = True
        
        if modified:
            snapped_lines[i] = shapely.LineString(coords)
        
    multiline = shapely.MultiLineString([l for l in snapped_lines if not l.is_empty])
    noded = shapely.node(multiline)
    noded_segments = list(noded.geoms) if hasattr(noded, 'geoms') else []
    
    noded_gdf = gpd.GeoDataFrame(geometry=noded_segments, crs=gdf_working.crs)
    
    # Map attributes back
    if not noded_gdf.empty:
        snapped_tree = shapely.STRtree(snapped_lines)
        midpoints = [seg.interpolate(0.5, normalized=True) for seg in noded_segments]
        nearest_indices = snapped_tree.nearest(midpoints)
        
        for col in gdf.columns:
            if col != gdf._geometry_column_name:
                noded_gdf[col] = gdf[col].iloc[nearest_indices].values
                
    if is_geographic:
        noded_gdf = noded_gdf.to_crs(orig_crs)
        
    return noded_gdf


def build_road_graph(highways_gdf: gpd.GeoDataFrame, snap_tolerance_m: float = 5.0) -> Tuple[nx.MultiGraph, dict]:
    """
    Builds a NetworkX MultiGraph from road geometries.
    """
    G = nx.MultiGraph()
    
    if highways_gdf.empty:
        return G, {"n_nodes": 0, "n_edges": 0, "connected_components": 0, "dangling_nodes": 0, "total_road_length_m": 0.0}
        
    noded_gdf = node_geometries(highways_gdf, snap_tolerance_m)
    
    is_geographic = noded_gdf.crs and noded_gdf.crs.is_geographic
    if is_geographic:
        utm_crs = noded_gdf.estimate_utm_crs()
        gdf_utm = noded_gdf.to_crs(utm_crs)
    else:
        gdf_utm = noded_gdf
        
    total_length = 0.0
    
    for idx, row in gdf_utm.iterrows():
        line = row.geometry
        if line.is_empty:
            continue
            
        coords = list(line.coords)
        if len(coords) < 2:
            continue
            
        orig_line = noded_gdf.geometry.iloc[idx]
        u_orig = tuple(orig_line.coords[0])
        v_orig = tuple(orig_line.coords[-1])
        
        # Rounding slightly to avoid floating point issues during dict lookup
        # 6 decimals in 4326 is ~0.1m, safe for noded intersections
        u_node = (round(u_orig[0], 6), round(u_orig[1], 6))
        v_node = (round(v_orig[0], 6), round(v_orig[1], 6))
        
        length_m = line.length
        total_length += length_m
        
        highway = row.get("highway", "unknown")
        bridge_val = row.get("bridge", False)
        if isinstance(bridge_val, str):
            is_bridge = bridge_val.lower() in ("yes", "true", "1", "t")
        else:
            is_bridge = bool(bridge_val)
            
        osm_way_id = row.get("osm_way_id", None)
        
        edge_attr = {
            "length_m": float(length_m),
            "highway": highway,
            "is_bridge": is_bridge,
            "geometry": orig_line,
        }
        if osm_way_id is not None:
            edge_attr["osm_way_id"] = osm_way_id
            
        G.add_edge(u_node, v_node, **edge_attr)
        
    dangling = sum(1 for n, d in G.degree() if d == 1)
    components = nx.number_connected_components(G) if len(G) > 0 else 0
    
    summary = {
        "n_nodes": G.number_of_nodes(),
        "n_edges": G.number_of_edges(),
        "connected_components": components,
        "dangling_nodes": dangling,
        "total_road_length_m": float(total_length),
    }
    
    return G, summary


def is_connected(graph: nx.MultiGraph) -> bool:
    """
    Checks if graph is a single connected component.
    Logs warning if disconnected.
    """
    if len(graph) == 0:
        return True
    
    connected = nx.is_connected(graph)
    if not connected:
        components = nx.number_connected_components(graph)
        logger.warning(f"Graph is not fully connected. It has {components} components.")
        
    return connected
