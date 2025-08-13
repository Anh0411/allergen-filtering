# Allergen Filtering System

A comprehensive system for filtering and analyzing allergens in recipes using NLP and machine learning techniques.

## Overview

This project provides an intelligent allergen detection and filtering system that can analyze recipe ingredients and identify potential allergens. It combines web scraping, natural language processing, and machine learning to provide accurate allergen information.

## Features

- **Allergen Detection**: Advanced NLP-based ingredient analysis
- **Recipe Scraping**: Automated collection from multiple recipe sources
- **Machine Learning**: Custom NER models for allergen identification
- **API Integration**: RESTful API for allergen analysis
- **Feedback Learning**: Continuous improvement through user feedback

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd allergen-filtering
```

2. Install dependencies (see Dependencies section below)

3. Set up the environment:
```bash
python manage.py migrate
python manage.py runserver
```

## Dependencies

### API Layer Dependencies
```
Django==4.2.7
djangorestframework==3.14.0
django-cors-headers==4.3.1
djangorestframework-simplejwt==5.3.0
drf-yasg==1.21.7
django-filter==23.3
django-cacheops==8.0.0
redis==5.0.1
celery==5.3.4
django-celery-beat==2.5.0
django-celery-results==2.5.1
psycopg2-binary==2.9.9
gunicorn==21.2.0
whitenoise==6.6.0
```

### NLP Dependencies for Allergen Filtering System

#### Core NLP Libraries
```
spacy>=3.7.0
nltk>=3.8.1
```

#### Text Processing and Analysis
```
textblob>=0.17.1
```

#### Machine Learning and Data Processing
```
scikit-learn>=1.3.0
pandas>=2.0.0
numpy>=1.24.0
```

#### Web Scraping Dependencies
```
beautifulsoup4>=4.12.0
requests>=2.31.0
selenium>=4.15.0
```

#### Django and Web Framework Dependencies
```
django>=4.2.0
djangorestframework>=3.14.0
```

#### Data Validation and Serialization
```
pydantic>=2.0.0
marshmallow>=3.20.0
```

#### Testing and Development
```
pytest>=7.4.0
pytest-django>=4.5.0
```

#### Logging and Monitoring
```
loguru>=0.7.0
```

#### Configuration Management
```
python-dotenv>=1.0.0
```

#### JSON and Data Handling
```
jsonschema>=4.19.0
```

#### Optional: Advanced NLP Models
```
# transformers>=4.30.0  # For BERT and other transformer models
# torch>=2.0.0          # PyTorch for deep learning models
# tensorflow>=2.13.0    # TensorFlow for deep learning models
```

## Project Structure

```
allergen-filtering/
├── allergen_filtering/          # Main Django app
├── recipes/                     # Recipe management app
├── scraper/                     # Web scraping functionality
├── allergen_ner_model_v1.1/    # NER model files
├── static/                      # Static assets
├── templates/                   # HTML templates
└── manage.py                    # Django management script
```

## Usage

### Running the Application

```bash
# Start the Django development server
python manage.py runserver

# Run Celery worker for background tasks
celery -A allergen_filtering worker -l info

# Run Celery beat for scheduled tasks
celery -A allergen_filtering beat -l info
```

### API Endpoints

The system provides RESTful API endpoints for:
- Recipe allergen analysis
- Allergen dictionary management
- User feedback collection
- Recipe search and filtering