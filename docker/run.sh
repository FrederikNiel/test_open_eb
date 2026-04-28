#!/usr/bin/env bash

# Enhanced run script for Docker Compose services
# Requires a specific service, a mode (--dev or --prod), and supports optional add-ons.

# --- Configuration ---
COMPOSE_FILE="docker-compose.yaml"

# --- Functions ---
print_usage() {
    echo "Usage: $0 [SERVICE] [OPTIONS]"
    echo ""
    echo "This script runs specified services using Docker Compose."
    echo ""
    echo "REQUIRED:"
    echo "  SERVICE           The main service to run (e.g., rover, cameras)."
    echo ""
    echo "OPTIONS:"
    echo "  --help, -h        Show this help message."
    echo ""
    echo "EXAMPLES:"
    echo "  $0 rover"
}

# --- Argument Parsing ---

# Check for no arguments or help flag
if [[ $# -eq 0 ]] || [[ "$1" == "--help" ]] || [[ "$1" == "-h" ]]; then
    print_usage
    exit 0
fi

# --- Main Logic ---

# Initialize variables
SERVICE_NAME="$1"
CONTAINER_NAME="$SERVICE_NAME"
if [[ "$SERVICE_NAME" == "rover" ]]; then
    CONTAINER_NAME="openeb"
fi
shift # Consume the service name argument
SERVICES="$SERVICE_NAME"


# --- Service Assembly & Execution ---

echo "[INFO] Running service '$SERVICE_NAME'..."

echo "[INFO] Starting services: $SERVICES"

# Ensure iptable_raw module is loaded (often needed for Docker networking)
sudo modprobe iptable_raw 2>/dev/null || true

# Execute docker compose
docker compose -f "$COMPOSE_FILE" up $SERVICES --detach --build --remove-orphans

# --- Post-run Information ---
echo ""
echo "[INFO] ✅ Launch complete!"
echo "[INFO] Use 'docker compose -f $COMPOSE_FILE logs -f' to view logs of all running services."
echo "[INFO] Use 'docker compose -f $COMPOSE_FILE down' to stop all services."
echo "[INFO] To access the main container, run: docker exec -it ${CONTAINER_NAME} bash"