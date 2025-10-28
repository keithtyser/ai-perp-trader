#!/bin/bash
set -e

echo "Running database migrations..."
python migrate.py

echo "Starting worker..."
python main.py
