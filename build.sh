#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Starting build process..."

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --no-input

# Run migrations
echo "Running database migrations..."
python manage.py migrate

# Import ISO standards if file exists
echo "Checking for ISO standards file..."
if [ -f "iso_standards.xlsx" ]; then
    echo "ISO standards file found. Importing..."
    python manage.py import_iso_standards iso_standards.xlsx
    echo "ISO standards import completed."
else
    echo "ISO standards file not found, skipping import"
fi

# Create superuser if it doesn't exist
echo "Creating superuser..."
python create_superuser.py

echo "Build process completed successfully!"