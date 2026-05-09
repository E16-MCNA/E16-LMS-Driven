#!/bin/bash

# E16 LMS Startup Script for Linux/macOS

echo "--- Starting E16 LMS Setup ---"

# Check if .env exists
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

# Install dependencies
echo "Installing requirements..."
pip install -r requirements.txt

# Run migrations
echo "Running database migrations..."
export FLASK_APP=app.py
flask db upgrade

# Run smoke test / verification
echo "Running verification script..."
python verify.py

# Start the application
echo "Starting Flask server..."
python app.py
