#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
set -e

# Load configuration
bashio::log.info "Loading configuration from Home Assistant add-on..."

PIXOO_HOST_AUTO=$(bashio::config 'PIXOO_HOST_AUTO')
PIXOO_DEVICE_TYPE=$(bashio::config 'PIXOO_DEVICE_TYPE')
PIXOO_DEBUG=$(bashio::config 'PIXOO_DEBUG')
PIXOO_SCREEN_SIZE=$(bashio::config 'PIXOO_SCREEN_SIZE')
PIXOO_CONNECTION_RETRIES=$(bashio::config 'PIXOO_CONNECTION_RETRIES')
PIXOO_REST_DEBUG=$(bashio::config 'PIXOO_REST_DEBUG')

if [ -z "${PIXOO_DEVICE_TYPE}" ]; then
    PIXOO_DEVICE_TYPE="auto"
fi

if [ -z "${PIXOO_SCREEN_SIZE}" ] || [ "${PIXOO_SCREEN_SIZE}" = "null" ]; then
    PIXOO_SCREEN_SIZE="64"
fi

if [ -z "${PIXOO_DEBUG}" ] || [ "${PIXOO_DEBUG}" = "null" ]; then
    PIXOO_DEBUG="false"
fi

if [ -z "${PIXOO_CONNECTION_RETRIES}" ] || [ "${PIXOO_CONNECTION_RETRIES}" = "null" ]; then
    PIXOO_CONNECTION_RETRIES="10"
fi

DISCOVERY_URL="https://app.divoom-gz.com/Device/ReturnSameLANDevice"
OPTIONS_FILE="/data/options.json"

DEVICE_LIST_JSON="[]"
if [ -f "${OPTIONS_FILE}" ]; then
    DEVICE_LIST_JSON=$(jq -c '.PIXOO_DEVICES // []' "${OPTIONS_FILE}")
fi
DEVICE_COUNT=$(echo "${DEVICE_LIST_JSON}" | jq 'length')

if [ "${DEVICE_COUNT}" -gt 0 ]; then
    bashio::log.info "Multi-device configuration detected (${DEVICE_COUNT} devices)."

    NEED_HOST_AUTO=$(echo "${DEVICE_LIST_JSON}" | jq '[.[] | select((.host_auto // false) == true)] | length')
    NEED_TYPE_AUTO=$(echo "${DEVICE_LIST_JSON}" | jq '[.[] | select((.device_type // "auto") == "auto")] | length')

    DISCOVERY_RESULT=""
    if [ "${NEED_HOST_AUTO}" -gt 0 ] || [ "${NEED_TYPE_AUTO}" -gt 0 ]; then
        DISCOVERY_RESULT=$(curl -s -X POST "${DISCOVERY_URL}" || echo "")

        if [ -z "${DISCOVERY_RESULT}" ] && [ "${NEED_HOST_AUTO}" -gt 0 ]; then
            bashio::log.error "Failed to connect to Divoom discovery service"
            bashio::log.error "Auto-discovery is required for at least one device"
            exit 1
        fi

        if [ -z "${DISCOVERY_RESULT}" ]; then
            bashio::log.warning "Divoom discovery service unavailable; auto device type will default to pixoo."
        fi
    fi

    DEVICES_JSON="[]"
    USED_HOSTS=()
    USED_KEYS=()
    INDEX=0
    FIRST_HOST=""
    FIRST_DEVICE_TYPE=""
    FIRST_SCREEN_SIZE=""
    FIRST_DEBUG=""
    FIRST_RETRIES=""

    for device in $(echo "${DEVICE_LIST_JSON}" | jq -c '.[]'); do
        name=$(echo "${device}" | jq -r '.name // empty')
        host_auto=$(echo "${device}" | jq -r '.host_auto // false')
        host=$(echo "${device}" | jq -r '.host // empty')
        device_type=$(echo "${device}" | jq -r '.device_type // "auto"')
        screen_size=$(echo "${device}" | jq -r '.screen_size // empty')
        debug=$(echo "${device}" | jq -r '.debug // empty')
        retries=$(echo "${device}" | jq -r '.connection_retries // empty')

        if [ -z "${screen_size}" ] || [ "${screen_size}" = "null" ]; then
            screen_size="${PIXOO_SCREEN_SIZE}"
        fi
        if ! [[ "${screen_size}" =~ ^[0-9]+$ ]]; then
            screen_size="64"
        fi

        if [ -z "${debug}" ] || [ "${debug}" = "null" ]; then
            debug="${PIXOO_DEBUG}"
        fi

        if [ -z "${retries}" ] || [ "${retries}" = "null" ]; then
            retries="${PIXOO_CONNECTION_RETRIES}"
        fi
        if ! [[ "${retries}" =~ ^[0-9]+$ ]]; then
            retries="${PIXOO_CONNECTION_RETRIES}"
        fi

        host_auto=$(echo "${host_auto}" | tr '[:upper:]' '[:lower:]')
        debug=$(echo "${debug}" | tr '[:upper:]' '[:lower:]')

        if [ "${debug}" != "true" ] && [ "${debug}" != "false" ]; then
            debug="false"
        fi

        if [ "${host_auto}" = "true" ]; then
            if [ -z "${DISCOVERY_RESULT}" ]; then
                bashio::log.error "Discovery is required but not available for device ${name:-${INDEX}}"
                exit 1
            fi

            if [ -n "${name}" ]; then
                host=$(echo "${DISCOVERY_RESULT}" | jq -r --arg name "${name}" '.DeviceList[] | select((.DeviceName // "" | ascii_downcase | gsub("[ _-]";"")) == ($name | ascii_downcase | gsub("[ _-]";""))) | .DevicePrivateIP' | head -n1)
            fi

            if [ -z "${host}" ] || [ "${host}" = "null" ]; then
                for candidate in $(echo "${DISCOVERY_RESULT}" | jq -r '.DeviceList[].DevicePrivateIP'); do
                    if ! printf '%s\n' "${USED_HOSTS[@]}" | grep -qx "${candidate}"; then
                        host="${candidate}"
                        break
                    fi
                done
            fi

            if [ -z "${host}" ] || [ "${host}" = "null" ]; then
                bashio::log.error "Failed to auto-detect host for device ${name:-${INDEX}}"
                exit 1
            fi

            bashio::log.info "Auto-detected device host for ${name:-device ${INDEX}}: ${host}"
        else
            if [ -z "${host}" ] || [ "${host}" = "null" ]; then
                bashio::log.error "Device host is required when host_auto is false"
                exit 1
            fi
        fi

        if [ "${device_type}" = "auto" ]; then
            device_name=""
            if [ -n "${DISCOVERY_RESULT}" ]; then
                device_name=$(echo "${DISCOVERY_RESULT}" | jq -r --arg ip "${host}" '.DeviceList[] | select(.DevicePrivateIP==$ip) | .DeviceName' | head -n1)
            fi

            if echo "${device_name}" | grep -qiE "time[ _-]?gate"; then
                device_type="time_gate"
            else
                device_type="pixoo"
            fi

            if [ -n "${device_name}" ] && [ "${device_name}" != "null" ]; then
                bashio::log.info "Detected device type for ${host}: ${device_type} (${device_name})"
            else
                bashio::log.warning "Could not detect device type for ${host}; defaulting to ${device_type}"
            fi
        fi

        if [ "${device_type}" = "time_gate" ]; then
            if ! [[ "${screen_size}" =~ ^[0-9]+$ ]]; then
                screen_size="128"
            elif [ "${screen_size}" -lt 128 ]; then
                screen_size="128"
            fi
        fi

        key="${name}"
        if [ -z "${key}" ]; then
            key="${host}"
        fi
        if printf '%s\n' "${USED_KEYS[@]}" | grep -qx "${key}"; then
            key="${key}-${INDEX}"
        fi

        USED_KEYS+=("${key}")
        USED_HOSTS+=("${host}")

        DEVICES_JSON=$(jq -c \
            --argjson devices "${DEVICES_JSON}" \
            --arg key "${key}" \
            --arg name "${name}" \
            --arg host "${host}" \
            --arg device_type "${device_type}" \
            --arg screen_size "${screen_size}" \
            --arg debug "${debug}" \
            --arg connection_retries "${retries}" \
            '$devices + [{"key":$key,"name":$name,"host":$host,"device_type":$device_type,"screen_size":($screen_size|tonumber? // 64),"debug":($debug == "true"),"connection_retries":($connection_retries|tonumber? // 10)}]'
        )

        if [ -z "${FIRST_HOST}" ]; then
            FIRST_HOST="${host}"
            FIRST_DEVICE_TYPE="${device_type}"
            FIRST_SCREEN_SIZE="${screen_size}"
            FIRST_DEBUG="${debug}"
            FIRST_RETRIES="${retries}"
        fi

        INDEX=$((INDEX + 1))
    done

    if [ -z "${FIRST_HOST}" ]; then
        bashio::log.error "No valid devices found in PIXOO_DEVICES configuration"
        exit 1
    fi

    export PIXOO_DEVICES_JSON="${DEVICES_JSON}"

    PIXOO_HOST="${FIRST_HOST}"
    PIXOO_DEVICE_TYPE="${FIRST_DEVICE_TYPE}"
    PIXOO_SCREEN_SIZE="${FIRST_SCREEN_SIZE}"
    PIXOO_DEBUG="${FIRST_DEBUG}"
    PIXOO_CONNECTION_RETRIES="${FIRST_RETRIES}"

    export PIXOO_HOST
    export PIXOO_DEVICE_TYPE
    export PIXOO_SCREEN_SIZE
    export PIXOO_DEBUG
    export PIXOO_CONNECTION_RETRIES

    for device in $(echo "${DEVICES_JSON}" | jq -c '.[]'); do
        key=$(echo "${device}" | jq -r '.key')
        host=$(echo "${device}" | jq -r '.host')
        dtype=$(echo "${device}" | jq -r '.device_type')
        size=$(echo "${device}" | jq -r '.screen_size')
        bashio::log.info "Device '${key}': ${host} (${dtype}, ${size}px)"
    done
else
    # Device discovery and validation (single device)
    if [ "${PIXOO_HOST_AUTO}" = true ]; then
        bashio::log.info "Starting automatic device discovery..."

        DISCOVERY_RESULT=$(curl -s -X POST "${DISCOVERY_URL}" || echo "")

        if [ -z "${DISCOVERY_RESULT}" ]; then
            bashio::log.error "Failed to connect to Divoom discovery service"
            bashio::log.error "Please check your internet connection or set PIXOO_HOST manually"
            exit 1
        fi

        DEVICE_IP=$(echo "${DISCOVERY_RESULT}" | jq -r '.DeviceList[0].DevicePrivateIP // empty')

        if [ -z "${DEVICE_IP}" ] || [ "${DEVICE_IP}" = "null" ]; then
            bashio::log.error "No Pixoo device found on local network"
            bashio::log.error "Make sure your device is powered on and connected to WiFi"
            bashio::log.info "You can also manually set PIXOO_HOST in the configuration"
            exit 1
        fi

        PIXOO_HOST="${DEVICE_IP}"
        bashio::log.info "Discovered Pixoo device at: ${PIXOO_HOST}"
    else
        PIXOO_HOST=$(bashio::config 'PIXOO_HOST')

        if [ -z "${PIXOO_HOST}" ]; then
            bashio::log.error "PIXOO_HOST is not configured"
            bashio::log.error "Either enable PIXOO_HOST_AUTO or provide a valid PIXOO_HOST"
            exit 1
        fi

        bashio::log.info "Using manually configured device: ${PIXOO_HOST}"
    fi

    # Auto-detect device type (Pixoo vs Time Gate)
    if [ "${PIXOO_DEVICE_TYPE}" = "auto" ]; then
        DEVICE_NAME=""

        if [ -n "${DISCOVERY_RESULT}" ]; then
            DEVICE_NAME=$(echo "${DISCOVERY_RESULT}" | jq -r --arg ip "${PIXOO_HOST}" '.DeviceList[] | select(.DevicePrivateIP==$ip) | .DeviceName' | head -n1)
            if [ -z "${DEVICE_NAME}" ] || [ "${DEVICE_NAME}" = "null" ]; then
                DEVICE_NAME=$(echo "${DISCOVERY_RESULT}" | jq -r '.DeviceList[0].DeviceName // empty')
            fi
        else
            DETECT_RESULT=$(curl -s -X POST "${DISCOVERY_URL}" || echo "")
            if [ -n "${DETECT_RESULT}" ]; then
                DEVICE_NAME=$(echo "${DETECT_RESULT}" | jq -r --arg ip "${PIXOO_HOST}" '.DeviceList[] | select(.DevicePrivateIP==$ip) | .DeviceName' | head -n1)
            fi
        fi

        if echo "${DEVICE_NAME}" | grep -qiE "time[ _-]?gate"; then
            PIXOO_DEVICE_TYPE="time_gate"
        else
            PIXOO_DEVICE_TYPE="pixoo"
        fi

        if [ -n "${DEVICE_NAME}" ] && [ "${DEVICE_NAME}" != "null" ]; then
            bashio::log.info "Detected device name: ${DEVICE_NAME}"
        else
            bashio::log.warning "Could not detect device name; defaulting to ${PIXOO_DEVICE_TYPE}"
        fi
    fi

    # Validate host format (basic IP validation)
    if ! echo "${PIXOO_HOST}" | grep -qE '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'; then
        bashio::log.warning "PIXOO_HOST does not appear to be a valid IP address: ${PIXOO_HOST}"
    fi

    export PIXOO_HOST
    export PIXOO_DEVICE_TYPE
fi

# Export environment variables
export PIXOO_DEBUG
export PIXOO_SCREEN_SIZE
export PIXOO_CONNECTION_RETRIES

# Log configuration summary
bashio::log.info "===== Pixoo REST Configuration ====="
bashio::log.info "Device IP: ${PIXOO_HOST}"
bashio::log.info "Device Type: ${PIXOO_DEVICE_TYPE}"
bashio::log.info "Screen Size: ${PIXOO_SCREEN_SIZE}"
bashio::log.info "Debug Mode: ${PIXOO_DEBUG}"
bashio::log.info "Connection Retries: ${PIXOO_CONNECTION_RETRIES}"
bashio::log.info "REST Debug: ${PIXOO_REST_DEBUG}"
bashio::log.info "===================================="

# Change to app directory
cd /app || {
    bashio::log.error "Failed to change to /app directory"
    exit 1
}

# pixoo-rest v2.0.13 is already included in the Docker image
bashio::log.info "Using pixoo-rest v2.0.13 (FastAPI)"

# Set additional environment variables for uvicorn
export PIXOO_REST_HOST="0.0.0.0"
export PIXOO_REST_PORT="5000"

# Start Uvicorn server (FastAPI)
bashio::log.info "Starting Pixoo REST server on port 5000..."

UVICORN_OPTS="--host 0.0.0.0"
UVICORN_OPTS="${UVICORN_OPTS} --port 5000"
UVICORN_OPTS="${UVICORN_OPTS} --workers 1"

if [ "${PIXOO_REST_DEBUG}" = true ]; then
    UVICORN_OPTS="${UVICORN_OPTS} --log-level debug"
else
    UVICORN_OPTS="${UVICORN_OPTS} --log-level info"
fi

# shellcheck disable=SC2086
exec uvicorn pixoo_rest_entrypoint:app ${UVICORN_OPTS}
