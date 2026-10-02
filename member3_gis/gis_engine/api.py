from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import date
from .schemas import AnalysisResult

app = FastAPI(title="GIS Engine API", description="Flood impact analysis engine")

class AnalyzeRequest(BaseModel):
    bbox: list[float]
    event_date: date
    flood_mask_path: str
    valid_mask_path: str
    prob_path: Optional[str] = None
    snapshot_date: Optional[date] = None
    params: Optional[Dict[str, Any]] = None

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/analyze", response_model=AnalysisResult)
def analyze_endpoint(request: AnalyzeRequest):
    """
    Runs the full flood impact pipeline on the specified bounding box and mask.
    """
    import os
    if not os.path.exists(request.flood_mask_path) or not os.path.exists(request.valid_mask_path):
        raise HTTPException(status_code=400, detail="Mask files do not exist")
        
    try:
        from .pipeline import analyze_full
        
        result_dict = analyze_full(
            bbox=tuple(request.bbox),
            event_date=request.event_date,
            flood_mask_path=request.flood_mask_path,
            valid_mask_path=request.valid_mask_path,
            snapshot_date=request.snapshot_date
        )
        return AnalysisResult(**result_dict)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
