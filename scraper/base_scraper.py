import requests
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class BaseRecipeScraper(ABC):
    """
    Abstract base class for recipe website scrapers.
    Subclass this for each supported site and override methods as needed.
    """
    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None):
        self.base_url = base_url
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (compatible; RecipeScraperBot/1.0)'
        }

    def fetch_page(self, url: str) -> Optional[str]:
        """
        Fetch the HTML content of a page.
        Returns the HTML as a string, or None on failure.
        """
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    @abstractmethod
    def get_recipe_links(self, page_html: str) -> List[str]:
        """
        Extract recipe links from a listing/search page.
        Should be implemented by each site-specific scraper.
        """
        pass

    @abstractmethod
    def parse_ingredients(self, recipe_html: str) -> List[str]:
        """
        Extract the list of ingredients from a recipe page.
        Should be implemented by each site-specific scraper.
        """
        pass

    def parse_metadata(self, recipe_html: str) -> Dict[str, Any]:
        """
        Optionally extract metadata (title, image, times, etc.) from a recipe page.
        Can be overridden by subclasses.
        """
        return {}

    def handle_pagination(self, current_page_html: str) -> Optional[str]:
        """
        Optionally extract the next page URL from a listing/search page.
        Can be overridden by subclasses.
        """
        return None

    def scrape_recipe(self, url: str) -> Dict[str, Any]:
        """
        Scrape a single recipe page and return structured data.
        """
        html = self.fetch_page(url)
        if not html:
            return {}
        ingredients = self.parse_ingredients(html)
        metadata = self.parse_metadata(html)
        return {
            'url': url,
            'ingredients': ingredients,
            **metadata
        }

# Example subclass for a hypothetical site
class ExampleSiteScraper(BaseRecipeScraper):
    """
    Example implementation for a fictional recipe site.
    """
    def get_recipe_links(self, page_html: str) -> List[str]:
        soup = BeautifulSoup(page_html, 'html.parser')
        # Example: find all <a> tags with class 'recipe-link'
        return [a['href'] for a in soup.find_all('a', class_='recipe-link') if 'href' in a.attrs]

    def parse_ingredients(self, recipe_html: str) -> List[str]:
        soup = BeautifulSoup(recipe_html, 'html.parser')
        # Example: find all <li> tags within a <ul class='ingredients'>
        ul = soup.find('ul', class_='ingredients')
        if not ul:
            return []
        return [li.get_text(strip=True) for li in ul.find_all('li')]

    def parse_metadata(self, recipe_html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(recipe_html, 'html.parser')
        title = soup.find('h1').get_text(strip=True) if soup.find('h1') else ''
        image = soup.find('img', class_='main-image')['src'] if soup.find('img', class_='main-image') else ''
        return {
            'title': title,
            'image_url': image
        }

    def handle_pagination(self, current_page_html: str) -> Optional[str]:
        soup = BeautifulSoup(current_page_html, 'html.parser')
        next_link = soup.find('a', class_='next-page')
        if next_link and 'href' in next_link.attrs:
            return next_link['href']
        return None 