from datetime import date
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class Metadata(BaseModel):
    bbox: List[float] = Field(..., description="[minx, miny, maxx, maxy]")
    event_date: date
    snapshot_date: date
    mask_source: str
    parameters: Dict[str, Any]
    attributions: List[str] = Field(
        default=["© OpenStreetMap contributors"], 
        description="Data attributions"
    )

class Statistics(BaseModel):
    flood_area_km2: float
    affected_road_km: float
    unassessed_road_km: float
    assessed_area_fraction: float
    n_bridges: int
    n_buildings: int
    n_settlements_total: int
    n_settlements_connected: int
    n_settlements_cut_off: int
    n_settlements_no_road: int
    n_settlements_unknown: int

class Settlement(BaseModel):
    id: str
    name: Optional[str] = None
    name_ne: Optional[str] = None
    status: str = Field(..., description="CONNECTED, POTENTIALLY_CUT_OFF, NO_MAPPED_ROAD_ACCESS, INSIDE_FLOOD_ZONE, UNKNOWN_NO_DATA")
    confidence: Optional[float] = None
    destination_name: Optional[str] = None
    detour_ratio: Optional[float] = None
    baseline_distance_m: Optional[float] = None

class AnalysisResult(BaseModel):
    metadata: Metadata
    statistics: Statistics
    settlements: List[Settlement]
    flood_layer: Dict[str, Any] = Field(..., description="GeoJSON FeatureCollection")
    roads_layer: Dict[str, Any] = Field(..., description="GeoJSON FeatureCollection")
    bridges_layer: Dict[str, Any] = Field(..., description="GeoJSON FeatureCollection")
    buildings_layer: Dict[str, Any] = Field(..., description="GeoJSON FeatureCollection")
    settlements_layer: Dict[str, Any] = Field(..., description="GeoJSON FeatureCollection")
    destinations_layer: Dict[str, Any] = Field(..., description="GeoJSON FeatureCollection")
