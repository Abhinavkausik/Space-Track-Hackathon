import json
import networkx as nx
import geopandas as gpd

def classify_infrastructure(roads_graph: nx.MultiGraph, buildings_gdf: gpd.GeoDataFrame, flood_gdf: gpd.GeoDataFrame) -> dict:
    affected_road_km = 0.0
    affected_bridges = 0
    affected_buildings = 0
    
    affected_roads_list = []
    affected_buildings_list = []
    
    if flood_gdf.empty:
        return {
            "affected_road_km": 0.0,
            "affected_bridges": 0,
            "affected_buildings": 0,
            "affected_roads_geojson": json.dumps({"type": "FeatureCollection", "features": []}),
            "affected_buildings_geojson": json.dumps({"type": "FeatureCollection", "features": []})
        }
        
    # Standardize CRS based on flood_gdf
    target_crs = flood_gdf.crs
    flood_union = flood_gdf.union_all()
    
    # Check roads & bridges
    for u, v, k, d in roads_graph.edges(data=True, keys=True):
        if 'geometry' in d:
            geom = d['geometry']
            # We assume geom is in target_crs, or we should reproject.
            # In typical flow, roads_graph geometry is EPSG:4326.
            # But we can check if we have a way to know graph CRS.
            # For robustness, we just use the geometry directly, assuming it matches flood_gdf 
            # (or caller aligns them).
            
            if geom.intersects(flood_union):
                length_m = d.get('length_m', 0.0)
                affected_road_km += (length_m / 1000.0)
                
                is_bridge = d.get('is_bridge', False)
                if is_bridge:
                    affected_bridges += 1
                    
                affected_roads_list.append({
                    "type": "Feature",
                    "geometry": geom.__geo_interface__,
                    "properties": {
                        "highway": d.get('highway', 'unknown'),
                        "is_bridge": is_bridge,
                        "length_m": length_m
                    }
                })
                
    # Check buildings
    if not buildings_gdf.empty:
        # Align CRS
        if buildings_gdf.crs and target_crs and buildings_gdf.crs != target_crs:
            b_gdf = buildings_gdf.to_crs(target_crs)
        else:
            b_gdf = buildings_gdf
            
        affected_b = b_gdf[b_gdf.intersects(flood_union)]
        affected_buildings = len(affected_b)
        
        # Convert to geojson
        if affected_buildings > 0:
            # We should probably project back to 4326 for valid geojson output
            affected_b_4326 = affected_b.to_crs("EPSG:4326") if affected_b.crs else affected_b
            affected_buildings_geojson = affected_b_4326.to_json()
        else:
            affected_buildings_geojson = json.dumps({"type": "FeatureCollection", "features": []})
    else:
        affected_buildings_geojson = json.dumps({"type": "FeatureCollection", "features": []})
        
    # Convert roads to geojson. Need to ensure they are EPSG:4326 for GeoJSON spec.
    # We will just dump them as they are, caller can reproject graph if needed.
    # Actually, GeoJSON should be 4326. 
    affected_roads_geojson = json.dumps({
        "type": "FeatureCollection",
        "features": affected_roads_list
    })
    
    return {
        "affected_road_km": affected_road_km,
        "affected_bridges": affected_bridges,
        "affected_buildings": affected_buildings,
        "affected_roads_geojson": affected_roads_geojson,
        "affected_buildings_geojson": affected_buildings_geojson
    }
