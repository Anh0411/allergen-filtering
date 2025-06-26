# Allergen Detection Integration with Web Scraping

This document describes how allergen detection has been integrated into the web scraping workflow for Food.com recipes.

## Overview

The integrated system combines:
- **Web scraping** of Food.com recipes using Playwright and BeautifulSoup
- **NLP-based allergen detection** using spaCy and custom allergen dictionaries
- **Database storage** with Django models for recipes and allergen analysis results
- **Real-time analysis** during the scraping process

## Key Features

### 1. Integrated Scraping and Analysis
- Scrapes recipe data (title, ingredients, instructions, etc.)
- Performs allergen analysis in real-time during scraping
- Saves both recipe data and allergen analysis results to database
- Handles duplicate detection and updates existing recipes

### 2. Comprehensive Allergen Detection
- Uses the advanced NLP processor with spaCy integration
- Detects major allergens (milk, eggs, peanuts, tree nuts, soy, wheat, fish, shellfish, sesame, sulfites)
- Identifies hidden sources and scientific names
- Provides confidence scores and risk levels
- Generates recommendations for each recipe

### 3. Database Integration
- Stores recipes in the `Recipe` model
- Saves detailed allergen analysis in `AllergenAnalysisResult` model
- Tracks risk levels, confidence scores, and processing times
- Maintains audit trail of detection activities

## Files Structure

```
scraper/
├── scrape_foodcom_with_allergen_detection.py  # Main integrated scraper
├── test_allergen_scraper.py                   # Test script
└── README_allergen_integration.md             # This file

recipes/management/commands/
└── scrape_with_allergens.py                   # Django management command
```

## Usage

### 1. Using the Django Management Command (Recommended)

```bash
# Test mode - scrape 3 recipes from page 1
python manage.py scrape_with_allergens --test-mode

# Scrape pages 1-5 with 3 concurrent workers
python manage.py scrape_with_allergens --start-page 1 --end-page 5 --max-workers 3

# Scrape a larger range
python manage.py scrape_with_allergens --start-page 10 --end-page 20 --max-workers 5
```

### 2. Using the Python Script Directly

```bash
# Test with a small range
python scraper/scrape_foodcom_with_allergen_detection.py --start-page 1 --end-page 3 --max-workers 2

# Run the test script
python scraper/test_allergen_scraper.py
```

### 3. Programmatic Usage

```python
from scraper.scrape_foodcom_with_allergen_detection import FoodComAllergenScraper

# Initialize scraper
scraper = FoodComAllergenScraper()

# Scrape a single recipe with allergen analysis
success = scraper.scrape_recipe_with_allergens("https://www.food.com/recipe/example-12345")

# Scrape a range of pages
successful, failed = scraper.scrape_page_range(1, 5, max_workers=3)
```

## Database Models

### Recipe Model
- `title`: Recipe title
- `instructions`: Cooking instructions
- `scraped_ingredients_text`: Raw ingredient text
- `risk_level`: Overall allergen risk (low/medium/high/critical)
- `nlp_confidence_score`: Confidence score from NLP analysis
- `nlp_analysis_date`: When analysis was performed

### AllergenAnalysisResult Model
- `recipe`: One-to-one relationship with Recipe
- `risk_level`: Detailed risk assessment
- `confidence_scores`: JSON field with confidence per allergen category
- `detected_allergens`: JSON field with detected allergens and terms
- `recommendations`: List of recommendations
- `processing_time`: Time taken for analysis

## Configuration

### NLP Processor Settings
The scraper automatically initializes the NLP processor with:
- spaCy model: `en_core_web_sm`
- Allergen dictionary: Uses the populated database dictionary
- Confidence weights for different match types

### Scraping Settings
- **Delay range**: 2-5 seconds between requests
- **Max retries**: 3 attempts per URL
- **User agent rotation**: Multiple browser user agents
- **Concurrent workers**: Configurable (default: 3)

## Monitoring and Logging

### Log Files
- `foodcom_allergen_scraping.log`: Main scraping log
- Console output with real-time progress

### Database Statistics
The system tracks:
- Total recipes scraped
- Recipes with allergen analysis
- Risk level distribution
- Processing times and success rates

### Example Log Output
```
2024-01-15 10:30:15 - INFO - Starting Food.com scraper with allergen detection
2024-01-15 10:30:16 - INFO - NLP processor initialized successfully
2024-01-15 10:30:17 - INFO - Found 25 unique recipe URLs on page 1
2024-01-15 10:30:20 - INFO - Scraping recipe: https://www.food.com/recipe/example-12345
2024-01-15 10:30:25 - INFO - Successfully extracted from JSON-LD: Chocolate Chip Cookies
2024-01-15 10:30:26 - INFO - Allergen analysis completed for Chocolate Chip Cookies
2024-01-15 10:30:26 - INFO -   Risk Level: high
2024-01-15 10:30:26 - INFO -   Detected Allergens: ['milk', 'eggs', 'wheat']
2024-01-15 10:30:26 - INFO -   Processing Time: 0.85s
2024-01-15 10:30:26 - INFO - Saved allergen analysis for Chocolate Chip Cookies
```

## Error Handling

### Common Issues and Solutions

1. **NLP Processor Not Available**
   - Ensure spaCy is installed: `pip install spacy`
   - Download the English model: `python -m spacy download en_core_web_sm`
   - Check that the allergen dictionary is populated

2. **Rate Limiting**
   - The scraper includes built-in delays and user agent rotation
   - Reduce `max_workers` if experiencing rate limiting
   - Increase delay range if needed

3. **Database Connection Issues**
   - Ensure Django is properly configured
   - Check database migrations are applied
   - Verify the allergen dictionary is populated

4. **Memory Issues**
   - Reduce `max_workers` for large scraping jobs
   - Monitor system resources during scraping

## Performance Optimization

### For Large-Scale Scraping
1. **Batch Processing**: Process pages in smaller batches
2. **Database Optimization**: Use bulk operations for large datasets
3. **Resource Management**: Monitor memory and CPU usage
4. **Error Recovery**: Implement resume functionality for interrupted jobs

### Recommended Settings
- **Small jobs** (< 100 recipes): 3 workers, 2-5s delays
- **Medium jobs** (100-1000 recipes): 5 workers, 3-7s delays
- **Large jobs** (> 1000 recipes): 3-5 workers, 5-10s delays

## Integration with Existing Workflows

### Adding to Existing Scrapers
The allergen detection can be integrated into other scrapers by:

1. Importing the NLP processor:
```python
from allergen_filtering.nlp_processor import get_nlp_processor
```

2. Adding analysis to the scraping workflow:
```python
def scrape_with_allergens(self, url):
    recipe_data = self.scrape_recipe(url)
    if recipe_data:
        allergen_analysis = self.analyze_allergens(recipe_data)
        self.save_recipe_with_allergens(recipe_data, allergen_analysis)
```

### API Integration
The system can be extended to provide API endpoints for:
- Recipe search with allergen filtering
- Risk level queries
- Allergen-specific recipe recommendations

## Future Enhancements

1. **Machine Learning Integration**: Train custom models on scraped data
2. **Cross-Contamination Detection**: Analyze processing methods
3. **Allergen-Free Alternatives**: Suggest substitutions
4. **User Preference Integration**: Filter based on user allergen profiles
5. **Real-time Updates**: Monitor recipe changes and re-analyze

## Support and Troubleshooting

For issues or questions:
1. Check the log files for detailed error messages
2. Verify all dependencies are installed correctly
3. Ensure the allergen dictionary is populated
4. Test with the provided test scripts
5. Monitor system resources during scraping

## Dependencies

Required packages (see `requirements_nlp.txt`):
- `spacy>=3.7.0`
- `nltk>=3.8.1`
- `playwright`
- `beautifulsoup4`
- `django>=4.2.0`
- `requests`
- `loguru`

Install with:
```bash
pip install -r requirements_nlp.txt
python -m spacy download en_core_web_sm
``` 