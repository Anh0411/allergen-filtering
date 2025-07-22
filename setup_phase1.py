#!/usr/bin/env python3
"""
Phase 1 Setup Script for Allergen Filtering Project
This script sets up the critical infrastructure components.
"""

import os
import sys
import subprocess
import logging
import json
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Phase1Setup:
    """Setup class for Phase 1 implementation"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.requirements_files = [
            'requirements_api.txt',
            'requirements_nlp.txt'
        ]
    
    def run_command(self, command, description):
        """Run a shell command with error handling"""
        logger.info(f"Running: {description}")
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                check=True, 
                capture_output=True, 
                text=True
            )
            logger.info(f"✓ {description} completed successfully")
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"✗ {description} failed: {e}")
            logger.error(f"Error output: {e.stderr}")
            return None
    
    def check_python_version(self):
        """Check if Python version is compatible"""
        logger.info("Checking Python version...")
        version = sys.version_info
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            logger.error("Python 3.8 or higher is required")
            return False
        logger.info(f"✓ Python {version.major}.{version.minor}.{version.micro} is compatible")
        return True
    
    def install_dependencies(self):
        """Install required dependencies"""
        logger.info("Installing dependencies...")
        
        # Install base requirements
        for req_file in self.requirements_files:
            if os.path.exists(req_file):
                logger.info(f"Installing from {req_file}")
                self.run_command(
                    f"pip install -r {req_file}",
                    f"Installing dependencies from {req_file}"
                )
        
        # Install additional packages
        additional_packages = [
            "django-redis",
            "psycopg2-binary",
            "gunicorn",
            "whitenoise",
        ]
        
        for package in additional_packages:
            self.run_command(
                f"pip install {package}",
                f"Installing {package}"
            )
        
        return True
    
    def setup_database(self):
        """Setup database and run migrations"""
        logger.info("Setting up database...")
        
        # Run migrations
        self.run_command(
            "python manage.py makemigrations",
            "Creating database migrations"
        )
        
        self.run_command(
            "python manage.py migrate",
            "Applying database migrations"
        )
        
        # Create superuser if needed
        logger.info("Creating superuser...")
        self.run_command(
            "python manage.py createsuperuser --noinput --username admin --email admin@example.com",
            "Creating admin user"
        )
        
        return True
    
    def setup_static_files(self):
        """Setup static files"""
        logger.info("Setting up static files...")
        
        self.run_command(
            "python manage.py collectstatic --noinput",
            "Collecting static files"
        )
        
        return True
    
    def create_directories(self):
        """Create necessary directories"""
        logger.info("Creating directories...")
        
        directories = [
            "logs",
            "media",
            "static",
            "exports",
            "cache",
        ]
        
        for directory in directories:
            dir_path = self.project_root / directory
            dir_path.mkdir(exist_ok=True)
            logger.info(f"✓ Created directory: {directory}")
        
        return True
    
    def setup_environment(self):
        """Setup environment variables"""
        logger.info("Setting up environment...")
        
        env_file = self.project_root / ".env"
        if not env_file.exists():
            env_content = """# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database Settings
DATABASE_URL=sqlite:///db.sqlite3

# Redis Settings
REDIS_URL=redis://localhost:6379

# API Settings
API_VERSION=v1
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Security Settings
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
"""
            with open(env_file, 'w') as f:
                f.write(env_content)
            logger.info("✓ Created .env file")
        
        return True
    
    def setup_redis(self):
        """Setup Redis configuration"""
        logger.info("Setting up Redis...")
        
        # Check if Redis is running
        try:
            import redis
            r = redis.Redis(host='localhost', port=6379, db=0)
            r.ping()
            logger.info("✓ Redis is running")
        except Exception as e:
            logger.warning(f"Redis not available: {e}")
            logger.info("Please install and start Redis manually")
        
        return True
    
    def setup_celery(self):
        """Setup Celery configuration"""
        logger.info("Setting up Celery...")
        
        # Create Celery configuration
        celery_config = """# Celery Configuration
from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allergen_filtering.settings_api')

app = Celery('allergen_filtering')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
"""
        
        celery_file = self.project_root / "celery.py"
        if not celery_file.exists():
            with open(celery_file, 'w') as f:
                f.write(celery_config)
            logger.info("✓ Created Celery configuration")
        
        return True
    
    def create_management_commands(self):
        """Create custom management commands"""
        logger.info("Creating management commands...")
        
        commands_dir = self.project_root / "recipes" / "management" / "commands"
        commands_dir.mkdir(parents=True, exist_ok=True)
        
        # Create __init__.py files
        init_files = [
            self.project_root / "recipes" / "management" / "__init__.py",
            commands_dir / "__init__.py",
        ]
        
        for init_file in init_files:
            if not init_file.exists():
                init_file.touch()
        
        # Create setup command
        setup_command = '''from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from recipes.models import AllergenCategory, AllergenSynonym
from allergen_filtering.fsa_allergen_dictionary import get_fsa_allergen_dictionary

class Command(BaseCommand):
    help = 'Setup initial data for the allergen filtering system'

    def handle(self, *args, **options):
        self.stdout.write('Setting up initial data...')
        
        # Create default allergen categories
        fsa_dict = get_fsa_allergen_dictionary()
        
        for category_name, allergen in fsa_dict.allergens.items():
            category, created = AllergenCategory.objects.get_or_create(
                name=allergen.name,
                defaults={'description': allergen.description}
            )
            
            if created:
                self.stdout.write(f'Created category: {category.name}')
            
            # Add synonyms
            for synonym in allergen.synonyms:
                AllergenSynonym.objects.get_or_create(
                    allergen_category=category,
                    term=synonym,
                    defaults={'term_type': 'synonym', 'confidence_score': 0.9}
                )
        
        self.stdout.write(self.style.SUCCESS('Setup completed successfully'))
'''
        
        setup_file = commands_dir / "setup_initial_data.py"
        if not setup_file.exists():
            with open(setup_file, 'w') as f:
                f.write(setup_command)
            logger.info("✓ Created setup management command")
        
        return True
    
    def run_initial_setup(self):
        """Run initial data setup"""
        logger.info("Running initial setup...")
        
        self.run_command(
            "python manage.py setup_initial_data",
            "Setting up initial data"
        )
        
        return True
    
    def create_docker_files(self):
        """Create Docker configuration files"""
        logger.info("Creating Docker files...")
        
        # Dockerfile
        dockerfile_content = """FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    postgresql-client \\
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements*.txt ./
RUN pip install --no-cache-dir -r requirements_api.txt
RUN pip install --no-cache-dir -r requirements_nlp.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "allergen_filtering.wsgi:application"]
"""
        
        dockerfile_path = self.project_root / "Dockerfile"
        if not dockerfile_path.exists():
            with open(dockerfile_path, 'w') as f:
                f.write(dockerfile_content)
            logger.info("✓ Created Dockerfile")
        
        # docker-compose.yml
        compose_content = """version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=True
      - DATABASE_URL=postgresql://postgres:password@db:5432/allergen_filtering
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    volumes:
      - .:/app
      - static_volume:/app/static
      - media_volume:/app/media

  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=allergen_filtering
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"

  celery:
    build: .
    command: celery -A allergen_filtering worker -l info
    environment:
      - DEBUG=True
      - DATABASE_URL=postgresql://postgres:password@db:5432/allergen_filtering
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    volumes:
      - .:/app

volumes:
  postgres_data:
  static_volume:
  media_volume:
"""
        
        compose_path = self.project_root / "docker-compose.yml"
        if not compose_path.exists():
            with open(compose_path, 'w') as f:
                f.write(compose_content)
            logger.info("✓ Created docker-compose.yml")
        
        return True
    
    def create_nginx_config(self):
        """Create Nginx configuration"""
        logger.info("Creating Nginx configuration...")
        
        nginx_config = """server {
    listen 80;
    server_name localhost;

    location /static/ {
        alias /app/static/;
    }

    location /media/ {
        alias /app/media/;
    }

    location / {
        proxy_pass http://web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
"""
        
        nginx_path = self.project_root / "nginx.conf"
        if not nginx_path.exists():
            with open(nginx_path, 'w') as f:
                f.write(nginx_config)
            logger.info("✓ Created Nginx configuration")
        
        return True
    
    def create_health_check(self):
        """Create health check script"""
        logger.info("Creating health check script...")
        
        health_check = """#!/usr/bin/env python3
import requests
import sys
import time

def check_health():
    try:
        response = requests.get('http://localhost:8000/api/v1/health/health/', timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"Health check passed: {data['status']}")
            return True
        else:
            print(f"Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"Health check error: {e}")
        return False

if __name__ == "__main__":
    max_retries = 5
    for i in range(max_retries):
        if check_health():
            sys.exit(0)
        if i < max_retries - 1:
            time.sleep(5)
    sys.exit(1)
"""
        
        health_path = self.project_root / "health_check.py"
        if not health_path.exists():
            with open(health_path, 'w') as f:
                f.write(health_check)
            os.chmod(health_path, 0o755)
            logger.info("✓ Created health check script")
        
        return True
    
    def run_tests(self):
        """Run basic tests"""
        logger.info("Running tests...")
        
        self.run_command(
            "python manage.py test recipes.tests",
            "Running recipe tests"
        )
        
        return True
    
    def print_next_steps(self):
        """Print next steps for the user"""
        logger.info("=" * 60)
        logger.info("PHASE 1 SETUP COMPLETED SUCCESSFULLY!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("Next steps:")
        logger.info("1. Start the development server:")
        logger.info("   python manage.py runserver")
        logger.info("")
        logger.info("2. Access the application:")
        logger.info("   - Web interface: http://localhost:8000")
        logger.info("   - API documentation: http://localhost:8000/api/docs/")
        logger.info("   - Admin interface: http://localhost:8000/admin/")
        logger.info("")
        logger.info("3. Start Celery worker (in a new terminal):")
        logger.info("   celery -A allergen_filtering worker -l info")
        logger.info("")
        logger.info("4. Start Celery beat (in another terminal):")
        logger.info("   celery -A allergen_filtering beat -l info")
        logger.info("")
        logger.info("5. For production deployment:")
        logger.info("   docker-compose up -d")
        logger.info("")
        logger.info("6. Monitor the application:")
        logger.info("   python health_check.py")
        logger.info("")
        logger.info("Documentation and configuration files have been created.")
        logger.info("Check the logs/ directory for application logs.")
        logger.info("=" * 60)
    
    def run_full_setup(self):
        """Run the complete Phase 1 setup"""
        logger.info("Starting Phase 1 setup...")
        
        steps = [
            ("Checking Python version", self.check_python_version),
            ("Installing dependencies", self.install_dependencies),
            ("Creating directories", self.create_directories),
            ("Setting up environment", self.setup_environment),
            ("Setting up database", self.setup_database),
            ("Setting up static files", self.setup_static_files),
            ("Setting up Redis", self.setup_redis),
            ("Setting up Celery", self.setup_celery),
            ("Creating management commands", self.create_management_commands),
            ("Running initial setup", self.run_initial_setup),
            ("Creating Docker files", self.create_docker_files),
            ("Creating Nginx config", self.create_nginx_config),
            ("Creating health check", self.create_health_check),
            ("Running tests", self.run_tests),
        ]
        
        for step_name, step_func in steps:
            logger.info(f"\n--- {step_name} ---")
            if not step_func():
                logger.error(f"Setup failed at: {step_name}")
                return False
        
        self.print_next_steps()
        return True


def main():
    """Main setup function"""
    setup = Phase1Setup()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("Phase 1 Setup Script")
        print("Usage: python setup_phase1.py [--help]")
        print("")
        print("This script sets up the critical infrastructure for the allergen filtering project.")
        return
    
    success = setup.run_full_setup()
    
    if success:
        logger.info("Phase 1 setup completed successfully!")
        sys.exit(0)
    else:
        logger.error("Phase 1 setup failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 