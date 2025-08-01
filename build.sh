#!/usr/bin/env bash
set -o errexit

echo "Starting build process..."

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Changing to project directory..."
cd cert_checker

echo "Making migrations..."
python manage.py makemigrations --no-input

echo "Running database migrations..."
python manage.py migrate --no-input

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Creating superuser if needed..."
python create_superuser.py

echo "Build completed successfully!"