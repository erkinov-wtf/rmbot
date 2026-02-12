#!/bin/sh
set -e

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Configuring bot webhook..."
python manage.py botwebhook set

echo "Starting server..."
python -m uvicorn config.server.asgi:application --host 0.0.0.0 --port 8000 --workers 4 --lifespan off
