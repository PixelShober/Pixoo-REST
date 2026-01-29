#!/usr/bin/with-contenv bash
set -e

# Standalone Docker entrypoint for pixoo-rest
# This bypasses Home Assistant Supervisor dependencies

echo "======================================"
echo "  Pixoo REST - Standalone Mode"
echo "======================================"
echo ""

# Check if running in Home Assistant Supervisor
if [ -n "${SUPERVISOR_TOKEN}" ] || [ -f /run/s6/container_environment/SUPERVISOR_TOKEN ] || [ -f /data/options.json ]; then
    echo "Running in Home Assistant mode, using run.sh..."
    exec /run.sh
fi

# Standalone mode - use environment variables directly
PIXOO_DEVICE_TYPE="${PIXOO_DEVICE_TYPE:-auto}"

if [ -n "${PIXOO_DEVICES_JSON}" ]; then
    echo "Multi-device configuration detected via PIXOO_DEVICES_JSON."

    if ! echo "${PIXOO_DEVICES_JSON}" | jq -e '. | length > 0' >/dev/null 2>&1; then
        echo "ERROR: PIXOO_DEVICES_JSON is invalid or empty"
        exit 1
    fi

    PIXOO_HOST=$(echo "${PIXOO_DEVICES_JSON}" | jq -r '.[0].host')
    PIXOO_DEVICE_TYPE=$(echo "${PIXOO_DEVICES_JSON}" | jq -r '.[0].device_type // "pixoo"')
    PIXOO_SCREEN_SIZE=$(echo "${PIXOO_DEVICES_JSON}" | jq -r '.[0].screen_size // 64')
    PIXOO_DEBUG=$(echo "${PIXOO_DEVICES_JSON}" | jq -r '.[0].debug // false')
    PIXOO_CONNECTION_RETRIES=$(echo "${PIXOO_DEVICES_JSON}" | jq -r '.[0].connection_retries // 10')
fi

echo "Configuration:"
echo "  PIXOO_HOST: ${PIXOO_HOST:-not set}"
echo "  PIXOO_DEVICE_TYPE: ${PIXOO_DEVICE_TYPE}"
echo "  PIXOO_SCREEN_SIZE: ${PIXOO_SCREEN_SIZE:-64}"
echo "  PIXOO_DEBUG: ${PIXOO_DEBUG:-false}"
echo "  PIXOO_REST_DEBUG: ${PIXOO_REST_DEBUG:-false}"
echo "  PIXOO_CONNECTION_RETRIES: ${PIXOO_CONNECTION_RETRIES:-10}"
echo ""

# Validate PIXOO_HOST is set
if [ -z "${PIXOO_HOST}" ]; then
    echo "ERROR: PIXOO_HOST environment variable is required"
    echo "Please set it in your docker-compose.yml or with -e PIXOO_HOST=<ip>"
    exit 1
fi

# Export required variables
export PIXOO_HOST
export PIXOO_DEVICE_TYPE
export PIXOO_SCREEN_SIZE="${PIXOO_SCREEN_SIZE:-64}"
export PIXOO_DEBUG="${PIXOO_DEBUG:-false}"
export PIXOO_CONNECTION_RETRIES="${PIXOO_CONNECTION_RETRIES:-10}"

if [ -z "${PIXOO_DEVICES_JSON}" ] && [ "${PIXOO_DEVICE_TYPE}" = "auto" ]; then
    DISCOVERY_URL="https://app.divoom-gz.com/Device/ReturnSameLANDevice"
    DETECT_RESULT=$(curl -s -X POST "${DISCOVERY_URL}" || echo "")
    DEVICE_NAME=$(echo "${DETECT_RESULT}" | jq -r --arg ip "${PIXOO_HOST}" '.DeviceList[] | select(.DevicePrivateIP==$ip) | .DeviceName' | head -n1)

    if echo "${DEVICE_NAME}" | grep -qiE "time[ _-]?gate"; then
        PIXOO_DEVICE_TYPE="time_gate"
    else
        PIXOO_DEVICE_TYPE="pixoo"
    fi

    if [ -n "${DEVICE_NAME}" ] && [ "${DEVICE_NAME}" != "null" ]; then
        echo "Detected device name: ${DEVICE_NAME}"
    else
        echo "Could not detect device name; defaulting to ${PIXOO_DEVICE_TYPE}"
    fi

    echo "Device type set to: ${PIXOO_DEVICE_TYPE}"

    export PIXOO_DEVICE_TYPE
fi

# Verify app directory exists
if [ ! -d "/app/pixoo_rest" ]; then
    echo "ERROR: pixoo-rest application files not found in /app"
    echo "Container may not have been built correctly"
    exit 1
fi

cd /app || {
    echo "ERROR: Failed to change to /app directory"
    exit 1
}

echo "Pixoo REST v2.0.13 ready (FastAPI)"
echo ""

# Start Uvicorn server (FastAPI)
echo "Starting Pixoo REST server on port 5000..."
echo ""

UVICORN_OPTS="--host 0.0.0.0"
UVICORN_OPTS="${UVICORN_OPTS} --port 5000"
UVICORN_OPTS="${UVICORN_OPTS} --workers 1"

if [ "${PIXOO_REST_DEBUG}" = "true" ]; then
    UVICORN_OPTS="${UVICORN_OPTS} --log-level debug"
else
    UVICORN_OPTS="${UVICORN_OPTS} --log-level info"
fi

# shellcheck disable=SC2086
exec uvicorn pixoo_rest_entrypoint:app ${UVICORN_OPTS}
