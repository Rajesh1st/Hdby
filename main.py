# main.py
import time
import re
from typing import List, Optional
from fastapi import FastAPI, Query
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from urllib.parse import urlparse

app = FastAPI(title="Hub Bypasser API", version="1.1")

# -----------------------
# Selenium Setup
# -----------------------
def setup_selenium() -> webdriver.Chrome:
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=chrome_options)
    return driver

# -----------------------
# Helpers
# -----------------------
def extract_hub_links_from_page(html_content: str) -> List[str]:
    soup = BeautifulSoup(html_content, "lxml")
    hub_links: List[str] = []

    hub_patterns = [
        r"https?://hubdrive\.[^/\"']+(/[^\"'\s]*)?",
        r"https?://hubcdn\.[^/\"']+(/[^\"'\s]*)?",
        r"https?://hubcloud\.[^/\"']+(/[^\"'\s]*)?",
        r"https?://[^/\"']*hubdrive[^/\"']*",
        r"https?://[^/\"']*hubcdn[^/\"']*",
        r"https?://[^/\"']*hubcloud[^/\"']*",
    ]

    text_content = soup.get_text(separator=" ")
    for pattern in hub_patterns:
        hub_links.extend(re.findall(pattern, text_content, re.IGNORECASE))

    for script in soup.find_all("script"):
        script_text = script.string or ""
        for pattern in hub_patterns:
            hub_links.extend(re.findall(pattern, script_text, re.IGNORECASE))

    for tag in soup.find_all(href=True):
        href = tag["href"]
        if any(k in href.lower() for k in ("hubdrive", "hubcdn", "hubcloud")):
            hub_links.append(href)

    # Normalize matches: some regex groups produce tuples, handle that
    normalized: List[str] = []
    for l in hub_links:
        if isinstance(l, tuple):
            # regex groups returned: join first non-empty
            candidate = next((part for part in l if part), "")
        else:
            candidate = l
        candidate = candidate.strip()
        if candidate and candidate.startswith("http"):
            if candidate not in normalized:
                normalized.append(candidate)
    return normalized

def _is_valid_http_url(u: str) -> bool:
    try:
        p = urlparse(u or "")
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def select_preferred_link(links: List[str]) -> Optional[str]:
    """Return single preferred link:
       Priority: hubcloud > hubdrive > hubcdn > first available"""
    if not links:
        return None
    lower = [l.lower() for l in links]
    for i, l in enumerate(lower):
        if "hubcloud" in l:
            return links[i]
    for i, l in enumerate(lower):
        if "hubdrive" in l:
            return links[i]
    for i, l in enumerate(lower):
        if "hubcdn" in l:
            return links[i]
    # fallback
    return links[0]

# -----------------------
# Bypass Logic
# -----------------------
def bypass_mediator_and_get_links(mediator_url: str, wait_after_load: int = 5) -> List[str]:
    mediator_url = (mediator_url or "").strip()
    print("Starting mediator bypass for:", mediator_url)
    if not _is_valid_http_url(mediator_url):
        print("Invalid URL passed to bypass.")
        return []

    driver = setup_selenium()
    try:
        driver.get(mediator_url)
        time.sleep(wait_after_load)

        # Try clicking verify buttons
        try:
            verify_btn = driver.find_element(By.ID, "verify_btn")
            driver.execute_script("arguments[0].click();", verify_btn)
            time.sleep(3)
        except Exception:
            try:
                alt = driver.find_elements(
                    By.XPATH,
                    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'verify') "
                    "or contains(., 'continue') or contains(., 'proceed')]"
                )
                if alt:
                    driver.execute_script("arguments[0].click();", alt[0])
                    time.sleep(3)
            except Exception:
                pass

        # Optional: wait for countdown element
        try:
            timer = driver.find_element(By.ID, "timer")
            for _ in range(30):
                t_text = timer.text.strip()
                if t_text in ("0", "00"):
                    break
                time.sleep(1)
        except Exception:
            pass

        # Look for get/download links
        get_links_selectors = [
            ("css", "a[href*='get']"),
            ("css", "a[href*='link']"),
            ("css", "a[href*='download']"),
            ("xpath_text", "get links"),
            ("xpath_text", "download"),
            ("css", "button[onclick*='link']"),
            ("css", "button[onclick*='get']"),
        ]

        get_links_url = None
        for sel_type, sel in get_links_selectors:
            try:
                if sel_type == "css":
                    elems = driver.find_elements(By.CSS_SELECTOR, sel)
                else:
                    elems = driver.find_elements(
                        By.XPATH,
                        f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{sel}')]"
                    )
                if elems:
                    el = elems[0]
                    if el.tag_name.lower() == "a":
                        get_links_url = el.get_attribute("href") or driver.current_url
                    else:
                        driver.execute_script("arguments[0].click();", el)
                        time.sleep(3)
                        get_links_url = driver.current_url
                    break
            except Exception:
                continue

        if get_links_url and get_links_url != driver.current_url:
            driver.get(get_links_url)
            time.sleep(3)

        final_html = driver.page_source
        hub_links = extract_hub_links_from_page(final_html)
        print(f"Found {len(hub_links)} hub links.")
        return hub_links

    except Exception as e:
        print("Error during bypass:", str(e))
        return []
    finally:
        try:
            driver.quit()
        except Exception:
            pass

# -----------------------
# API Routes
# -----------------------
@app.get("/")
@app.head("/")
def home():
    return {"message": "🚀 Hub Bypasser API is Running Successfully!"}

@app.get("/bypass")
def bypass(url: str = Query(..., description="Mediator page URL")):
    """Bypass the given mediator URL and return a single preferred hub link."""
    links = bypass_mediator_and_get_links(url)
    preferred = select_preferred_link(links)
    if preferred:
        return {"success": True, "link": preferred}
    return {"success": False, "message": "No hub links found."}
