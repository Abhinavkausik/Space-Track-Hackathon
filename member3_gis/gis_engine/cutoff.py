import logging
from typing import Tuple, List, Dict

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

def snap_points_to_graph(gdf: gpd.GeoDataFrame, graph: nx.MultiGraph, max_snap_m: float = 500) -> dict:
    if gdf.empty or len(graph) == 0:
        return {idx: None for idx in gdf.index}
        
    orig_crs = gdf.crs
    is_geo = orig_crs and orig_crs.is_geographic
    
    if is_geo:
        utm_crs = gdf.estimate_utm_crs()
        gdf_utm = gdf.to_crs(utm_crs)
    else:
        gdf_utm = gdf
        utm_crs = orig_crs
        
    nodes = list(graph.nodes())
    if "SUPER_DEST" in nodes:
        nodes.remove("SUPER_DEST")
        
    if not nodes:
        return {idx: None for idx in gdf.index}
        
    import shapely
    node_points = [shapely.Point(n[0], n[1]) for n in nodes]
    nodes_gdf = gpd.GeoDataFrame(geometry=node_points, crs=orig_crs)
    if is_geo:
        nodes_gdf = nodes_gdf.to_crs(utm_crs)
        
    tree = shapely.STRtree(nodes_gdf.geometry.values)
    
    snap_map = {}
    for idx, row in gdf_utm.iterrows():
        pt = row.geometry
        if pt.is_empty:
            snap_map[idx] = None
            continue
            
        nearest_idx = tree.nearest(pt)
        if nearest_idx is not None:
            nearest_geom = nodes_gdf.geometry.iloc[nearest_idx]
            dist = pt.distance(nearest_geom)
            if dist <= max_snap_m:
                snap_map[idx] = nodes[nearest_idx]
            else:
                snap_map[idx] = None
        else:
            snap_map[idx] = None
            
    return snap_map

def add_super_destination(graph: nx.MultiGraph, hospitals_gdf: gpd.GeoDataFrame, towns_gdf: gpd.GeoDataFrame, max_snap_m: float = 2000) -> Tuple[str, dict]:
    dests = []
    if not hospitals_gdf.empty:
        dests.append(hospitals_gdf)
    if not towns_gdf.empty:
        dests.append(towns_gdf)
        
    super_node = "SUPER_DEST"
    node_to_name = {}
    
    if not dests:
        graph.add_node(super_node)
        return super_node, node_to_name
        
    all_dests = pd.concat(dests, ignore_index=True)
    snap_map = snap_points_to_graph(all_dests, graph, max_snap_m)
    
    graph.add_node(super_node)
    for idx, node in snap_map.items():
        if node is not None:
            graph.add_edge(super_node, node, length_m=0.0)
            name = all_dests.iloc[idx].get("name", f"Dest_{idx}")
            node_to_name[node] = name
            
    return super_node, node_to_name

def remove_flooded_edges(graph: nx.MultiGraph, flood_gdf: gpd.GeoDataFrame, buffer_m: float = 0.0, min_overlap_m: float = 0.0) -> nx.MultiGraph:
    after_graph = graph.copy()
    if flood_gdf.empty:
        return after_graph
        
    if buffer_m > 0:
        # Buffer in UTM
        utm_crs = flood_gdf.estimate_utm_crs() if flood_gdf.crs.is_geographic else flood_gdf.crs
        buffered = flood_gdf.to_crs(utm_crs).geometry.buffer(buffer_m)
        flood_gdf_work = gpd.GeoDataFrame(geometry=buffered, crs=utm_crs).to_crs(flood_gdf.crs)
    else:
        flood_gdf_work = flood_gdf
        
    flood_union = flood_gdf_work.union_all()
    
    edges = list(after_graph.edges(data=True, keys=True))
    for u, v, k, d in edges:
        if 'geometry' in d:
            geom = d['geometry']
            if geom.intersects(flood_union):
                if min_overlap_m > 0:
                    intersection = geom.intersection(flood_union)
                    length_m = d.get('length_m', 0.0)
                    geom_len = geom.length
                    if geom_len > 0:
                        inter_len_m = (intersection.length / geom_len) * length_m
                        if inter_len_m >= min_overlap_m:
                            after_graph.remove_edge(u, v, k)
                else:
                    after_graph.remove_edge(u, v, k)
                    
    return after_graph

def compute_reachability(graph: nx.MultiGraph, snap_map: dict, super_dest_node: str):
    try:
        lengths, paths = nx.single_source_dijkstra(graph, super_dest_node, weight='length_m')
    except nx.NodeNotFound:
        lengths, paths = {}, {}
        
    reach = {}
    reach_paths = {}
    for idx, node in snap_map.items():
        if node is not None and node in lengths:
            reach[idx] = lengths[node]
            reach_paths[idx] = paths[node]
        else:
            reach[idx] = None
            reach_paths[idx] = None
    return reach, reach_paths

def flag_unassessed_edges(graph: nx.MultiGraph, unassessed_gdf: gpd.GeoDataFrame):
    if unassessed_gdf.empty:
        return
    unassess_union = unassessed_gdf.union_all()
    for u, v, k, d in graph.edges(data=True, keys=True):
        if 'geometry' in d and d['geometry'].intersects(unassess_union):
            d['is_unassessed'] = True
        else:
            d['is_unassessed'] = False

def sensitivity_sweep(graph: nx.MultiGraph, flood_gdf: gpd.GeoDataFrame, settlements_gdf: gpd.GeoDataFrame, snap_map: dict, super_dest: str, buffer_range: list, overlap_range: list) -> dict:
    runs = 0
    cutoff_counts = {idx: 0 for idx in settlements_gdf.index}
    
    for buf in buffer_range:
        for overlap in overlap_range:
            runs += 1
            after_g = remove_flooded_edges(graph, flood_gdf, buffer_m=buf, min_overlap_m=overlap)
            reach, _ = compute_reachability(after_g, snap_map, super_dest)
            
            for idx in settlements_gdf.index:
                if reach.get(idx) is None:
                    cutoff_counts[idx] += 1
                    
    if runs == 0:
        return {idx: 1.0 for idx in settlements_gdf.index}
        
    return {idx: counts / runs for idx, counts in cutoff_counts.items()}

def classify_settlements(settlements_gdf: gpd.GeoDataFrame, before_reach: dict, after_reach: dict, after_paths: dict, flood_gdf: gpd.GeoDataFrame, unassessed_gdf: gpd.GeoDataFrame, snap_map: dict, after_graph: nx.MultiGraph, node_to_name: dict) -> list:
    results = []
    
    flood_union = flood_gdf.to_crs(settlements_gdf.crs).union_all() if not flood_gdf.empty else None
    
    for idx, row in settlements_gdf.iterrows():
        pt = row.geometry
        snapped_node = snap_map.get(idx)
        
        dist_before = before_reach.get(idx)
        dist_after = after_reach.get(idx)
        
        is_inside_flood = flood_union.intersects(pt) if flood_union else False
        
        has_unassessed = False
        dest_name = "Unknown"
        
        if dist_after is not None:
            path_nodes = after_paths.get(idx)
            if path_nodes and len(path_nodes) > 1:
                # First node is SUPER_DEST, second is the actual destination snapped node
                dest_node = path_nodes[1]
                dest_name = node_to_name.get(dest_node, "Unknown")
                
                for i in range(len(path_nodes)-1):
                    u = path_nodes[i]
                    v = path_nodes[i+1]
                    if u == "SUPER_DEST" or v == "SUPER_DEST":
                        continue
                    edge_data = after_graph.get_edge_data(u, v)
                    if any(d.get('is_unassessed', False) for d in edge_data.values()):
                        has_unassessed = True
                        break
                        
        if is_inside_flood:
            status = "INSIDE_FLOOD_ZONE"
        elif snapped_node is None or dist_before is None:
            status = "NO_MAPPED_ROAD_ACCESS"
        elif dist_after is None:
            status = "POTENTIALLY_CUT_OFF"
        elif has_unassessed:
            status = "UNKNOWN_NO_DATA"
        else:
            status = "CONNECTED"
            
        detour_ratio = 1.0
        if dist_before and dist_after and dist_before > 0:
            detour_ratio = dist_after / dist_before
            
        results.append({
            "id": row.get("id", str(idx)),
            "name": row.get("name", "Unknown"),
            "name_ne": row.get("name:ne", ""),
            "status": status,
            "destination_name": dest_name,
            "baseline_distance_m": dist_before if dist_before else 0.0,
            "detour_ratio": detour_ratio
        })
        
    return results

def analyze_cutoff(roads_graph: nx.MultiGraph, settlements_gdf: gpd.GeoDataFrame, towns_gdf: gpd.GeoDataFrame, hospitals_gdf: gpd.GeoDataFrame, flood_gdf: gpd.GeoDataFrame, unassessed_gdf: gpd.GeoDataFrame) -> dict:
    
    graph = roads_graph.copy()
    super_dest, node_to_name = add_super_destination(graph, hospitals_gdf, towns_gdf)
    
    snap_map = snap_points_to_graph(settlements_gdf, graph, max_snap_m=500)
    
    before_reach, _ = compute_reachability(graph, snap_map, super_dest)
    
    target_crs = settlements_gdf.crs
    if flood_gdf.crs and target_crs and flood_gdf.crs != target_crs:
        flood_gdf = flood_gdf.to_crs(target_crs)
    if unassessed_gdf.crs and target_crs and unassessed_gdf.crs != target_crs:
        unassessed_gdf = unassessed_gdf.to_crs(target_crs)
        
    after_graph = remove_flooded_edges(graph, flood_gdf)
    flag_unassessed_edges(after_graph, unassessed_gdf)
    after_reach, after_paths = compute_reachability(after_graph, snap_map, super_dest)
    
    settlements_results = classify_settlements(settlements_gdf, before_reach, after_reach, after_paths, flood_gdf, unassessed_gdf, snap_map, after_graph, node_to_name)
    
    confidence_map = sensitivity_sweep(graph, flood_gdf, settlements_gdf, snap_map, super_dest, buffer_range=[-5, 0, 5], overlap_range=[0, 10])
    
    counts = {"CONNECTED": 0, "POTENTIALLY_CUT_OFF": 0, "NO_MAPPED_ROAD_ACCESS": 0, "UNKNOWN_NO_DATA": 0, "INSIDE_FLOOD_ZONE": 0}
    
    for i, res in enumerate(settlements_results):
        res["confidence"] = confidence_map.get(i, 1.0)
        counts[res["status"]] = counts.get(res["status"], 0) + 1
        
    return {
        "settlements": settlements_results,
        "statistics": counts
    }
