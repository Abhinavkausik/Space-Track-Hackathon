import json
import logging
from datetime import date, datetime, timedelta
from typing import Dict, Any, Tuple

from gis_engine.loaders.osm_loader import load_osm_data
from gis_engine.graph_builder import build_road_graph
from gis_engine.mask_adapter import process_masks
from gis_engine.impact import classify_infrastructure
from gis_engine.cutoff import analyze_cutoff
from gis_engine.schemas import AnalysisResult, Metadata, Statistics, Settlement

logger = logging.getLogger(__name__)

def analyze_full(bbox: Tuple[float, float, float, float], event_date: date, flood_mask_path: str, valid_mask_path: str, snapshot_date: date = None) -> dict:
    """
    Run the end-to-end flood impact analysis pipeline.
    Returns a dictionary matching the AnalysisResult Pydantic schema.
    """
    if snapshot_date is None:
        # Default snapshot to 1 day before event
        snapshot_date = event_date - timedelta(days=1)
        
    # Convert dates to datetimes for loaders that require it
    snapshot_dt = datetime.combine(snapshot_date, datetime.min.time())
    event_dt = datetime.combine(event_date, datetime.min.time())

    # 1. Load OSM Data
    osm_data = load_osm_data(bbox, snapshot_dt, event_dt)
    roads_gdf = osm_data["highways"]
    buildings_gdf = osm_data["buildings"]
    settlements_gdf = osm_data["places"]
    hospitals_gdf = osm_data["hospitals"]
    towns_gdf = osm_data["towns"]
    
    # 2. Build road graph
    graph, graph_summary = build_road_graph(roads_gdf)
    
    # 3. Process masks
    flood_gdf, unassessed_gdf, assessed_area_fraction = process_masks(flood_mask_path, valid_mask_path)
    
    # 4. Classify Infrastructure
    impact = classify_infrastructure(graph, buildings_gdf, flood_gdf)
    
    # Compute flood area km2
    if not flood_gdf.empty:
        # Assuming flood_gdf is in UTM based on mask_adapter
        flood_area_m2 = flood_gdf.geometry.area.sum()
        flood_area_km2 = flood_area_m2 / 1_000_000.0
    else:
        flood_area_km2 = 0.0
        
    # 5. Cut-off Analysis
    cutoff = analyze_cutoff(graph, settlements_gdf, towns_gdf, hospitals_gdf, flood_gdf, unassessed_gdf)
    
    # 6. Build Result
    metadata = Metadata(
        bbox=list(bbox),
        event_date=event_date,
        snapshot_date=snapshot_date,
        mask_source="Sentinel-1 SAR",
        parameters={"snap_tolerance_m": 5.0}
    )
    
    stats = Statistics(
        flood_area_km2=flood_area_km2,
        affected_road_km=impact["affected_road_km"],
        unassessed_road_km=0.0, # Not currently computed explicitly, default 0
        assessed_area_fraction=assessed_area_fraction,
        n_bridges=impact["affected_bridges"],
        n_buildings=impact["affected_buildings"],
        n_settlements_total=len(settlements_gdf),
        n_settlements_connected=cutoff["statistics"].get("CONNECTED", 0),
        n_settlements_cut_off=cutoff["statistics"].get("POTENTIALLY_CUT_OFF", 0),
        n_settlements_no_road=cutoff["statistics"].get("NO_MAPPED_ROAD_ACCESS", 0),
        n_settlements_unknown=cutoff["statistics"].get("UNKNOWN_NO_DATA", 0)
    )
    
    # Re-project to 4326 for GeoJSON output
    # Since roads might already be in 4326, we don't need to reproject graph
    # But flood_gdf is in UTM. Let's project it back.
    if not flood_gdf.empty:
        flood_gdf_4326 = flood_gdf.to_crs("EPSG:4326")
    else:
        flood_gdf_4326 = flood_gdf
        
    flood_layer = json.loads(flood_gdf_4326.to_json()) if not flood_gdf_4326.empty else {"type": "FeatureCollection", "features": []}
    
    result = AnalysisResult(
        metadata=metadata,
        statistics=stats,
        settlements=[Settlement(**s) for s in cutoff["settlements"]],
        flood_layer=flood_layer,
        roads_layer=json.loads(impact["affected_roads_geojson"]),
        bridges_layer={"type": "FeatureCollection", "features": []}, # To be populated if needed
        buildings_layer=json.loads(impact["affected_buildings_geojson"]),
        settlements_layer=json.loads(settlements_gdf.to_crs("EPSG:4326").to_json()) if not settlements_gdf.empty else {"type": "FeatureCollection", "features": []},
        destinations_layer={"type": "FeatureCollection", "features": []} # To be populated if needed
    )
    
    return result.model_dump(mode='json')
