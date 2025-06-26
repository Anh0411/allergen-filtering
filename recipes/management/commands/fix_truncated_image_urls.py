import sys
import os
import django
from django.core.management.base import BaseCommand
from recipes.models import Recipe

# Setup path to use the scraper
SCRAPER_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'scraper')
sys.path.append(SCRAPER_PATH)

from scraper.scrape_simplyrecipes import scrape_recipe

class Command(BaseCommand):
    help = 'Fix recipes with truncated image URLs by re-scraping and updating them.'

    def handle(self, *args, **options):
        # Find all recipes with image_url length exactly 200 and from simplyrecipes.com
        affected = Recipe.objects.filter(image_url__isnull=False, original_url__icontains='simplyrecipes.com')
        affected = [r for r in affected if len(r.image_url) == 200]
        self.stdout.write(f"Found {len(affected)} recipes with truncated image URLs.")
        fixed = 0
        for recipe in affected:
            self.stdout.write(f"Re-scraping: {recipe.title} ({recipe.original_url})")
            data = scrape_recipe(recipe.original_url)
            if data and data.get('image_url') and len(data['image_url']) > 200:
                old_url = recipe.image_url
                recipe.image_url = data['image_url'][:500]
                recipe.save(update_fields=['image_url'])
                self.stdout.write(self.style.SUCCESS(f"Updated image URL for '{recipe.title}'\nOld: {old_url}\nNew: {recipe.image_url}"))
                fixed += 1
            else:
                self.stdout.write(self.style.WARNING(f"Could not update image for '{recipe.title}'. Scraper returned: {data.get('image_url') if data else 'None'}"))
        self.stdout.write(self.style.SUCCESS(f"Done. Updated {fixed} recipes.")) 