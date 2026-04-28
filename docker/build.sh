#!/bin/bash

# build.sh - Build script for rover deployment image
# This script builds the deployment Docker image with the source code baked in

set -e

echo "Building rover deployment image..."

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the docker directory
cd "$SCRIPT_DIR"

# Build the deployment image
docker compose --file docker-compose.yaml build rover-deploy

echo "✅ Rover deployment image built successfully!"
echo ""
echo "To run the deployment container:"
echo "  docker-compose up rover-deploy"
echo ""
echo "To run in detached mode:"
echo "  docker-compose up -d rover-deploy"
echo ""
echo "To stop the deployment container:"
echo "  docker-compose down rover-deploy"
echo ""
echo "Available commands for the container:"
echo "  - autostart: Automatically start the teleop bringup"
echo "  - bringup: Start the standard bringup"
echo "  - bash: Interactive shell"
