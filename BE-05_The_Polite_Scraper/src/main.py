import os
import re
import time
import json
from datetime import datetime, timezone
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional

BASE_URL = "https://books.toscrape.com/"
START_URL = "https://books.toscrape.com/catalogue/page-1.html"
USER_AGENT = "FlyRankInternship-BE05/1.0 (+https://github.com/tushaxy/backend-ai-engineering-flyrank)"

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Pydantic Schema Validation (Stage 4)
class BookSchema(BaseModel):
    title: str = Field(..., min_length=1)
    product_url: str
    price_gbp: float = Field(..., ge=0)
    price_text: str
    availability_text: str
    rating_text: str
    description: Optional[str] = None
    source_page: str
    fetched_at: str

def fetch_page(url: str, is_detail: bool = False) -> tuple[str, bool]:
    url_hash = re.sub(r'[^a-zA-Z0-9]', '_', url)
    cache_path = os.path.join(CACHE_DIR, f"{url_hash}.html")

    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return f.read(), True

    headers = {"User-Agent": USER_AGENT}
    time.sleep(0.5)  # Politeness delay (500ms)

    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            return response.text, False
        else:
            raise Exception(f"HTTP Status {response.status_code}")
    except Exception as e:
        raise Exception(f"Failed to fetch {url}: {str(e)}")

def parse_rating(soup: BeautifulSoup) -> str:
    rating_elem = soup.find("p", class_=re.compile(r"^star-rating"))
    if rating_elem:
        classes = rating_elem.get("class", [])
        for c in classes:
            if c != "star-rating":
                return c
    return "Unknown"

def run_scraper():
    start_time = datetime.now(timezone.utc)
    current_page = START_URL
    pages_to_visit = 3
    discovered_urls = []
    
    total_fetched = 0
    cache_hits = 0
    failed_pages = 0

    # Stage 2: Crawl 3 Catalogue Pages
    for page_num in range(pages_to_visit):
        try:
            html, from_cache = fetch_page(current_page)
            if from_cache:
                cache_hits += 1
            else:
                total_fetched += 1

            soup = BeautifulSoup(html, "html.parser")
            articles = soup.find_all("article", class_="product_pod")

            for article in articles:
                link_tag = article.find("h3").find("a")
                rel_url = link_tag.get("href")
                abs_url = urljoin(current_page, rel_url)
                if abs_url not in discovered_urls:
                    discovered_urls.append(abs_url)

            next_button = soup.find("li", class_="next")
            if next_button and next_button.find("a"):
                next_rel = next_button.find("a").get("href")
                current_page = urljoin(current_page, next_rel)
            else:
                break
        except Exception as e:
            failed_pages += 1

    valid_records = []
    invalid_records = []

    # Inject one deliberately broken URL to test Stage 5 failure survival
    test_urls = list(discovered_urls)
    test_urls.append("https://books.toscrape.com/catalogue/broken_non_existent_book_9999.html")

    # Stage 3 & 4: Extract, Normalize, Validate
    for book_url in test_urls:
        try:
            html, from_cache = fetch_page(book_url, is_detail=True)
            if from_cache:
                cache_hits += 1
            else:
                total_fetched += 1

            soup = BeautifulSoup(html, "html.parser")
            title = soup.find("h1").text.strip() if soup.find("h1") else ""
            
            price_elem = soup.find("p", class_="price_color")
            price_text = price_elem.text.strip() if price_elem else "£0.00"
            price_match = re.search(r"[\d\.]+", price_text)
            price_gbp = float(price_match.group()) if price_match else 0.0

            avail_elem = soup.find("p", class_="instock availability")
            avail_text = avail_elem.text.strip() if avail_elem else ""

            desc_elem = soup.find("div", id="product_description")
            description = desc_elem.find_next_sibling("p").text.strip() if desc_elem else None

            raw_record = {
                "title": title,
                "product_url": book_url,
                "price_gbp": price_gbp,
                "price_text": price_text,
                "availability_text": avail_text,
                "rating_text": parse_rating(soup),
                "description": description,
                "source_page": book_url,
                "fetched_at": datetime.now(timezone.utc).isoformat()
            }

            validated = BookSchema(**raw_record)
            valid_records.append(validated.model_dump())

        except Exception as err:
            failed_pages += 1
            invalid_records.append({"url": book_url, "reason": str(err)})

    # Deduplicate valid records by canonical URL
    unique_books = {b["product_url"]: b for b in valid_records}.values()
    final_books = list(unique_books)

    with open(os.path.join(OUTPUT_DIR, "books.json"), "w", encoding="utf-8") as f:
        json.dump(final_books, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "errors.json"), "w", encoding="utf-8") as f:
        json.dump(invalid_records, f, indent=2)

    end_time = datetime.now(timezone.utc)
    duration_sec = round((end_time - start_time).total_seconds(), 2)

    report = {
        "start_time": start_time.isoformat(),
        "duration_seconds": duration_sec,
        "catalogue_pages_crawled": 3,
        "total_urls_discovered": len(discovered_urls),
        "total_requests_made": total_fetched,
        "cache_hits": cache_hits,
        "valid_records_stored": len(final_books),
        "invalid_records": len(invalid_records),
        "failed_pages": failed_pages
    }

    with open(os.path.join(OUTPUT_DIR, "run-report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"Scrape Complete! Stored {len(final_books)} books in output/books.json. Failed: {failed_pages}")

if __name__ == "__main__":
    run_scraper()
