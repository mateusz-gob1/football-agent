import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

app = FastAPI(title="Football Agent Intelligence System")

DEMO_DATA = json.loads(Path("data/demo_data.json").read_text(encoding="utf-8"))

app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
def index():
    return FileResponse("frontend/index.html")


@app.get("/api/agent")
def get_agent():
    return DEMO_DATA["agent"]


@app.get("/api/players")
def get_players():
    return DEMO_DATA["players"]


@app.get("/api/players/{name}")
def get_player(name: str):
    for p in DEMO_DATA["players"]:
        if p["name"].lower() == name.lower():
            return p
    return JSONResponse(status_code=404, content={"error": "Player not found"})


@app.get("/api/system")
def get_system_info():
    return DEMO_DATA["system_info"]


@app.post("/api/generate")
def generate_briefing():
    return JSONResponse(
        status_code=403,
        content={
            "demo_mode": True,
            "message": "Live generation is disabled in the public demo.",
            "instructions": "Clone the repo and add your own API keys to run the full system."
        }
    )
