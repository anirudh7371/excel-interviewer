#!/bin/bash

# Start Cloud SQL Proxy in background if DATABASE_URL contains cloudsql
if [[ $DATABASE_URL == *"cloudsql"* ]]; then
    echo "Starting Cloud SQL Proxy..."
    cloud_sql_proxy -instances=$CLOUD_SQL_CONNECTION_NAME=tcp:5432 &
    
    # Wait for Cloud SQL Proxy to be ready
    sleep 10
fi

# Start nginx in background
echo "Starting nginx..."
nginx -g "daemon on;"

# Initialize database
echo "Initializing database..."
python seed_database.py

# Start the application
echo "Starting application server..."
exec uvicorn main:app \
    --host 0.0.0.0 \
    --port ${PORT:-8080} \
    --workers ${WORKERS:-2} \
    --access-log \
    --log-level info