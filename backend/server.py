from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from backend.central_agent import run_agent
from fastapi.middleware.cors import CORSMiddleware
import database.repository as repo
from retrieval.urbex_location_agent import geocode_candidates
import retrieval.crawler as crawler

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    raw_query: str
    locations: list = []

@app.post("/chat")
def chat(req: ChatRequest):
    result = run_agent(req.raw_query, req.locations)
    return result

@app.get("/locations")
def list_locations():
    return repo.get_locations()

class LocationCorrection(BaseModel):
    entity: str

@app.patch("/locations/{location_id}")
def correct_location(location_id: str, req: LocationCorrection):
    if not repo.location_exists(location_id):
        raise HTTPException(status_code=404, detail="Location not found")
    repo.update_location(location_id, entity=req.entity, verified=True)
    return repo.get_location(location_id)

@app.get("/locations/{location_id}/geocode-candidates")
def search_geocode_candidates(location_id: str, q: str):
    if not repo.location_exists(location_id):
        raise HTTPException(status_code=404, detail="Location not found")
    return {"candidates": geocode_candidates(q)}

class GeocodeCorrection(BaseModel):
    lat: float
    lon: float
    display_name: Optional[str] = None
    osm_type: Optional[str] = None
    osm_id: Optional[int] = None

@app.patch("/locations/{location_id}/geocode")
def correct_location_geocode(location_id: str, req: GeocodeCorrection):
    if not repo.location_exists(location_id):
        raise HTTPException(status_code=404, detail="Location not found")
    repo.update_location_geocode(
        location_id, req.lat, req.lon, req.display_name, req.osm_type, req.osm_id
    )
    return repo.get_location(location_id)

@app.get("/crawler/status")
def crawler_status():
    return crawler.get_status()

@app.post("/crawler/start")
def crawler_start():
    return crawler.start_crawler()

@app.post("/crawler/stop")
def crawler_stop():
    return crawler.stop_crawler()