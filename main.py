# main.py
from fastapi import FastAPI, Query
from hub_bypasser_selenium import bypass_mediator_and_get_links

app = FastAPI(title="Hub Bypasser API", version="1.0")

@app.get("/")
async def home():
    return {"message": "🚀 Hub Bypasser API is Running Successfully!"}

@app.get("/bypass")
async def bypass(url: str = Query(..., description="Mediator URL to bypass")):
    try:
        links = bypass_mediator_and_get_links(url)
        if links:
            return {"status": "success", "count": len(links), "links": links}
        return {"status": "no_links_found"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
