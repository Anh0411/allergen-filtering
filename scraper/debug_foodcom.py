from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import sys
import os
import django

# Setup Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings')
django.setup()

def debug_foodcom_page():
    """Debug what links are actually on Food.com pagination pages"""
    url = "https://www.food.com/recipe?pn=101"
    
    print(f"Debugging: {url}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Show browser for debugging
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        
        # Navigate to page
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        
        # Wait a bit for content to load
        page.wait_for_timeout(5000)
        
        html = page.content()
        browser.close()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find ALL links containing /recipe/
    all_recipe_links = soup.select('a[href*="/recipe/"]')
    print(f"\nFound {len(all_recipe_links)} links containing '/recipe/':")
    
    for i, link in enumerate(all_recipe_links[:20]):  # Show first 20
        href = link.get('href')
        text = link.get_text(strip=True)[:50]  # First 50 chars of text
        print(f"{i+1}. {href} -> {text}")
    
    # Also try to find any recipe-related selectors
    print(f"\n=== All links on page ===")
    all_links = soup.select('a[href]')[:10]  # First 10 links
    for i, link in enumerate(all_links):
        href = link.get('href')
        text = link.get_text(strip=True)[:30]
        print(f"{i+1}. {href} -> {text}")

if __name__ == "__main__":
    debug_foodcom_page() 