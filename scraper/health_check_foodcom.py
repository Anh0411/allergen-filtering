import logging
import sys
import os
from datetime import datetime

# Setup logging to file (with timestamp in filename)
log_dir = os.path.join(os.path.dirname(__file__), 'health_logs')
os.makedirs(log_dir, exist_ok=True)
log_filename = os.path.join(log_dir, f"foodcom_health_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import scrape_recipe from scrape_foodcom.py
sys.path.append(os.path.dirname(__file__))
from scrape_foodcom import scrape_recipe

def run_health_check():
    """
    Automated health check for the Food.com scraper.
    Scrapes a few known recipes and checks for missing/empty fields.
    Logs anomalies for monitoring and review.
    """
    test_urls = [
        "https://www.food.com/recipe/best-chocolate-chip-cookies-54225",
        "https://www.food.com/recipe/slow-cooker-chicken-tortilla-soup-33671",
        "https://www.food.com/recipe/banana-banana-bread-35861"
    ]
    anomalies = []
    for url in test_urls:
        logger.info(f"[HEALTH CHECK] Testing {url}")
        data = scrape_recipe(url)
        if not data:
            anomalies.append((url, "Failed to scrape"))
            logger.error(f"[HEALTH CHECK] Failed to scrape: {url}")
            continue
        for field in ['title', 'scraped_ingredients_text', 'instructions']:
            value = data.get(field, "")
            if not value or (isinstance(value, list) and len(value) == 0) or (isinstance(value, str) and len(value.strip()) < 10):
                anomalies.append((url, f"Missing or short field: {field}"))
                logger.error(f"[HEALTH CHECK] {url} - Missing or short field: {field}")
    if anomalies:
        logger.error(f"[HEALTH CHECK] Anomalies detected: {anomalies}")
    else:
        logger.info("[HEALTH CHECK] All test recipes scraped successfully.")
    logger.info(f"[HEALTH CHECK] Completed at {datetime.now().isoformat()}")
    logger.info(f"[HEALTH CHECK] Total URLs checked: {len(test_urls)}")
    logger.info(f"[HEALTH CHECK] Total anomalies: {len(anomalies)}")
    if anomalies:
        logger.info(f"[HEALTH CHECK] See log file {log_filename} for details.")

if __name__ == "__main__":
    run_health_check() 