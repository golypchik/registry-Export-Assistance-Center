#!/usr/bin/env bash
# File: c:\Users\User\Desktop\cert_checker\cert_checker\build.sh

# Exit on error
set -o errexit

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Collect static files
python manage.py collectstatic --noinput

# Run migrations
python manage.py migrate

# Create superuser if it doesn't exist
python create_superuser.py