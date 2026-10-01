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
    # This is a skeleton. Logic will be wired to pipeline.py later.
    raise HTTPException(status_code=501, detail="Not Implemented")
