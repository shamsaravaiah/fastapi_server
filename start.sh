#!/bin/bash

# Optional: show each command in logs for debugging
set -x

# Start the FastAPI app using uvicorn
exec uvicorn app.main:app --host 0.0.0.0 --port 10000
