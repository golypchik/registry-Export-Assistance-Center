#!/usr/bin/env bash
# exit on error
set -o errexit

echo "Starting build process..."

# Download Liberation Serif fonts for certificate generation
echo "Setting up fonts for certificate generation..."
mkdir -p static/fonts

if [ ! -f "static/fonts/LiberationSerif-Regular.ttf" ]; then
    echo "Downloading Liberation Serif fonts..."
    # Скачиваем шрифты напрямую из GitHub releases
    wget -q https://github.com/liberationfonts/liberation-fonts/files/7261482/liberation-fonts-ttf-2.1.5.tar.gz -O /tmp/liberation-fonts.tar.gz
    
    if [ -f "/tmp/liberation-fonts.tar.gz" ]; then
        tar -xzf /tmp/liberation-fonts.tar.gz -C /tmp/
        cp /tmp/liberation-fonts-ttf-2.1.5/LiberationSerif-Regular.ttf static/fonts/ 2>/dev/null || true
        cp /tmp/liberation-fonts-ttf-2.1.5/LiberationSerif-Bold.ttf static/fonts/ 2>/dev/null || true
        rm -rf /tmp/liberation-fonts*
        echo "✓ Liberation Serif fonts installed"
    else
        echo "⚠ Could not download fonts, will use system fonts"
    fi
else
    echo "✓ Fonts already present"
fi

# Install dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Collect static files
echo "Collecting static files..."
export DEBUG=False
export RENDER=1
python manage.py collectstatic --no-input --clear

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