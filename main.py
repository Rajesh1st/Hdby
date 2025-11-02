# main.py
import logging
from fastapi import FastAPI, Query, HTTPException
from urllib.parse import urlparse
from hub_bypasser_selenium import bypass_mediator_and_get_links

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hub_bypasser")

app = FastAPI(title="Hub Bypasser API", version="1.1")

@app.get("/")
async def home():
    return {"message": "🚀 Hub Bypasser API is Running Successfully!"}

def is_valid_http_url(u: str) -> bool:
    try:
        parsed = urlparse(u)
        return parsed.scheme in ("http", "https") and parsed.netloc != ""
    except Exception:
        return False

@app.get("/bypass")
async def bypass(url: str = Query(..., description="Mediator URL to bypass")):
    url = (url or "").strip()
    if not url:
        # Client passed ?url with no value -> return 400 instead of trying selenium
        raise HTTPException(status_code=400, detail="Missing 'url' query parameter.")
    if not is_valid_http_url(url):
        raise HTTPException(status_code=400, detail="Invalid URL. Use http:// or https://")
    logger.info("Received bypass request for: %s", url)
    try:
        links = bypass_mediator_and_get_links(url)
        if links:
            return {"status": "success", "count": len(links), "links": links}
        return {"status": "no_links_found"}
    except ValueError as ve:
        # our validation inside bypass may raise ValueError
        logger.warning("Bad request while processing URL %s: %s", url, ve)
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # Catch-all: log short message and return 500
        logger.exception("Error while bypassing %s", url)
        return {"status": "error", "error": "internal_server_error"}
