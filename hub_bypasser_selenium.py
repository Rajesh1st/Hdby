import time
import re
from typing import List
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from urllib.parse import urlparse

def setup_selenium() -> webdriver.Chrome:
    """Setup Selenium WebDriver with appropriate options (headless)."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # newer headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    )
    # If using chromedriver-binary, webdriver.Chrome() will find it automatically.
    driver = webdriver.Chrome(options=chrome_options)
    return driver

def _is_valid_http_url(u: str) -> bool:
    """Return True if u is a valid http or https URL with netloc."""
    try:
        p = urlparse(u or "")
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False

def extract_hub_links_from_page(html_content: str) -> List[str]:
    """Extract HubDrive/HubCDN/HubCloud links from page content."""
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

    # Search in visible text
    text_content = soup.get_text(separator=" ")
    for pattern in hub_patterns:
        hub_links.extend(re.findall(pattern, text_content, re.IGNORECASE))

    # Search inside <script> tags
    for script in soup.find_all("script"):
        script_text = script.string or ""
        for pattern in hub_patterns:
            hub_links.extend(re.findall(pattern, script_text, re.IGNORECASE))

    # Search href attributes
    for tag in soup.find_all(href=True):
        href = tag["href"]
        if any(k in href.lower() for k in ("hubdrive", "hubcdn", "hubcloud")):
            hub_links.append(href)

    # Deduplicate while preserving order and ensure valid http(s)
    seen = set()
    unique = []
    for link in hub_links:
        if not isinstance(link, str):
            continue
        link = link.strip()
        if link.startswith("http") and link not in seen:
            seen.add(link)
            unique.append(link)
    return unique

def bypass_mediator_and_get_links(mediator_url: str, wait_after_load: int = 5) -> List[str]:
    """
    Load mediator URL in headless Chrome, try clicks if present, return hub links.

    Raises:
        ValueError: if mediator_url is invalid (empty or not http/https).
    """
    mediator_url = (mediator_url or "").strip()
    print("Starting mediator bypass for:", mediator_url)

    # Validate before creating webdriver to avoid Chrome invalid-argument errors
    if not _is_valid_http_url(mediator_url):
        raise ValueError("Invalid mediator URL (must start with http:// or https://)")

    driver = setup_selenium()

    try:
        driver.get(mediator_url)
        time.sleep(wait_after_load)

        # Try clicking a typical 'verify' button (if present)
        try:
            verify_btn = driver.find_element(By.ID, "verify_btn")
            print("Clicking verify_btn...")
            driver.execute_script("arguments[0].click();", verify_btn)
            time.sleep(3)
        except Exception:
            # try other common button texts
            try:
                alt = driver.find_elements(
                    By.XPATH,
                    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'verify') "
                    "or contains(., 'Continue') or contains(., 'Proceed')]"
                )
                if alt:
                    print("Clicking alt verify button...")
                    driver.execute_script("arguments[0].click();", alt[0])
                    time.sleep(3)
            except Exception:
                pass

        # Optional: wait for countdown element with id 'timer'
        try:
            timer = driver.find_element(By.ID, "timer")
            print("Found timer element, waiting for it to reach 0 (max 30s)...")
            for _ in range(30):
                t_text = timer.text.strip()
                if t_text == "0" or t_text == "00":
                    break
                time.sleep(1)
        except Exception:
            # no timer found - continue
            pass

        # Try to find a "Get Links" link or button and click or navigate
        get_links_selectors = [
            ("css", "a[href*='get']"),
            ("css", "a[href*='link']"),
            ("css", "a[href*='download']"),
            ("xpath_text", "get links"),
            ("xpath_text", "get links".upper()),
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
                    # text-based xpath (case-insensitive)
                    elems = driver.find_elements(
                        By.XPATH,
                        f"//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{sel}')]"
                    )
                if elems:
                    el = elems[0]
                    if el.tag_name.lower() == "a":
                        get_links_url = el.get_attribute("href") or driver.current_url
                        print("Found link element, href:", get_links_url)
                    else:
                        print("Clicking element to open links...")
                        driver.execute_script("arguments[0].click();", el)
                        time.sleep(3)
                        get_links_url = driver.current_url
                    break
            except Exception:
                continue

        # If we have a get_links_url, navigate there to extract final page
        if get_links_url and get_links_url != driver.current_url:
            driver.get(get_links_url)
            time.sleep(3)

        final_html = driver.page_source
        hub_links = extract_hub_links_from_page(final_html)
        print(f"Found {len(hub_links)} hub links.")
        # Save optional
        if hub_links:
            with open("hub_links.txt", "w", encoding="utf-8") as f:
                for link in hub_links:
                    f.write(link + "\n")
        return hub_links

    except Exception as e:
        # Keep the logged message short to avoid noisy chrome stacktraces in logs
        print("Error during bypass:", str(e))
        return []
    finally:
        try:
            driver.quit()
        except Exception:
            pass

def main():
    url = input("Enter mediator URL: ").strip()
    if not url.startswith(("http://", "https://")):
        print("Invalid URL. Include http:// or https://")
        return
    links = bypass_mediator_and_get_links(url)
    if links:
        print("\nSUCCESS - hub links:")
        for i, l in enumerate(links, 1):
            print(f"{i}. {l}")
    else:
        print("\nNo hub links found.")

if __name__ == "__main__":
    main()
