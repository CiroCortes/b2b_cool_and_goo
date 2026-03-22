#!/usr/bin/env bash
# exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Convert static files
python manage.py collectstatic --no-input

# Run migrations
python manage.py migrate

# Cargar datos iniciales (SOLO PARA EL PRIMER DESPLIEGUE EN FREE TIER)
python manage.py loaddata initial_data.json
