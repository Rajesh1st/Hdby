import time
import re
from typing import List
from fastapi import FastAPI, Query
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

app = FastAPI(title="Hub Bypasser API", version="1.0")

# -----------------------
# Selenium Setup
# -----------------------
def setup_selenium() -> webdriver.Chrome:
    """Setup Selenium WebDriver with appropriate options (headless)."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
    driver = webdriver.Chrome(options=chrome_options)
    return driver


# -----------------------
# Extract Hub Links
# -----------------------
def extract_hub_links_from_page(html_content: str) -> List[str]:
    soup = BeautifulSoup(html_content, "lxml")
    hub_links = []

    hub_patterns = [
        r"https?://hubdrive\.[^/\"']+",
        r"https?://hubcdn\.[^/\"']+",
        r"https?://hubcloud\.[^/\"']+",
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

    seen = set()
    unique = []
    for link in hub_links:
        if isinstance(link, str) and link.startswith("http") and link not in seen:
            seen.add(link)
            unique.append(link)
    return unique


# -----------------------
# Bypass Logic
# -----------------------
def bypass_mediator_and_get_links(mediator_url: str, wait_after_load: int = 5) -> List[str]:
    print("Starting mediator bypass for:", mediator_url)
    if not mediator_url.startswith("http"):
        print("Invalid URL passed.")
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
                alt = driver.find_elements(By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'verify') or contains(., 'continue') or contains(., 'proceed')]")
                if alt:
                    driver.execute_script("arguments[0].click();", alt[0])
                    time.sleep(3)
            except Exception:
                pass

        # Wait for timer
        try:
            timer = driver.find_element(By.ID, "timer")
            for _ in range(30):
                t_text = timer.text.strip()
                if t_text in ["0", "00"]:
                    break
                time.sleep(1)
        except Exception:
            pass

        # Find get/download buttons
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
                    elems = driver.find_elements(By.XPATH, f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{sel}')]")
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
        return hub_links

    except Exception as e:
        print("Error during bypass:", e)
        return []
    finally:
        driver.quit()


# -----------------------
# API Routes
# -----------------------
@app.get("/")
@app.head("/")
def home():
    return {"message": "🚀 Hub Bypasser API is Running Successfully!"}


@app.get("/bypass")
def bypass(url: str = Query(..., description="Mediator page URL")):
    """Bypass the given mediator URL and extract Hub links."""
    links = bypass_mediator_and_get_links(url)
    if not links:
        return {"success": False, "message": "No hub links found or invalid URL."}
    return {"success": True, "count": len(links), "links": links}
