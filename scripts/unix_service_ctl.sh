#!/usr/bin/env bash
# ==============================================================================
# MUFG Bank, Ltd. - Operations Infrastructure & Systems Management
# Project: InfraOps-Sentinel (Phase 2: Start/Shutdown Runbook Orchestrator)
# Script:  unix_service_ctl.sh
# Purpose: Simulates real Unix service lifecycle operations (precheck, stop,
#          start, verify, status) managing PIDs, locks, and socket listeners
#          inside ./sandbox_fs/run/ with high-precision latency telemetry.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUN_DIR="${PROJECT_ROOT}/sandbox_fs/run"

ACTION=""
SERVICE=""
JSON_MODE=false
SIMULATE_LATENCY=0.05

# Parse options
while [[ $# -gt 0 ]]; do
    case "$1" in
        --action)
            ACTION="$2"
            shift 2
            ;;
        --service)
            SERVICE="$2"
            shift 2
            ;;
        --run-dir)
            RUN_DIR="$2"
            shift 2
            ;;
        --latency)
            SIMULATE_LATENCY="$2"
            shift 2
            ;;
        --json)
            JSON_MODE=true
            shift
            ;;
        *)
            echo "[ERROR] Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

if [[ -z "${ACTION}" || -z "${SERVICE}" ]]; then
    echo "Usage: $0 --action <status|precheck|stop|start|verify> --service <name> [--json]" >&2
    exit 1
fi

mkdir -p "${RUN_DIR}"

# Normalize service name (strip .service if present)
SERVICE_BASE="${SERVICE%.service}"
PID_FILE="${RUN_DIR}/${SERVICE_BASE}.pid"
LOCK_FILE="${RUN_DIR}/${SERVICE_BASE}.lock"
LISTENER_FILE="${RUN_DIR}/${SERVICE_BASE}.listener"

START_NS=$(date +%s%N)

# Helper function to compute elapsed seconds
get_elapsed() {
    local end_ns
    end_ns=$(date +%s%N)
    local diff_ns=$(( end_ns - START_NS ))
    awk "BEGIN {printf \"%.2f\", ${diff_ns} / 1000000000}"
}

# Helper to output result
output_result() {
    local status="$1"
    local state="$2"
    local pid_info="$3"
    local details="$4"
    local elapsed
    elapsed=$(get_elapsed)

    if [[ "${JSON_MODE}" == true ]]; then
        cat <<EOF
{
  "service": "${SERVICE}",
  "action": "${ACTION}",
  "status": "${status}",
  "state": "${state}",
  "pid_info": "${pid_info}",
  "elapsed_sec": ${elapsed},
  "details": "${details}"
}
EOF
    else
        echo "[${status}] Service: ${SERVICE} | Action: ${ACTION} | State: ${state} | Info: ${pid_info} | Elapsed: ${elapsed}s | ${details}"
    fi
}

# Simulate realistic I/O latency
if (( $(awk "BEGIN {print (${SIMULATE_LATENCY} > 0) ? 1 : 0}") )); then
    sleep "${SIMULATE_LATENCY}"
fi

case "${ACTION}" in
    status)
        if [[ -f "${PID_FILE}" ]]; then
            PID_VAL=$(cat "${PID_FILE}")
            output_result "SUCCESS" "ACTIVE_RUNNING" "PID=${PID_VAL}" "Service is running normally."
            exit 0
        else
            output_result "SUCCESS" "INACTIVE_STOPPED" "PID=NONE" "Service is stopped."
            exit 0
        fi
        ;;

    precheck)
        if [[ "${SERVICE_BASE}" == "mufg-swift-gateway" ]]; then
            # Check for active socket listener
            if [[ -f "${LISTENER_FILE}" ]]; then
                # Simulate active sockets drained check
                output_result "SUCCESS" "DRAIN_COMPLIANT" "SOCKET=:8443" "Active inbound SWIFT sockets drained to 0 connections."
            else
                output_result "SUCCESS" "DRAIN_COMPLIANT" "SOCKET=INACTIVE" "No active socket bindings detected."
            fi
            exit 0
        elif [[ "${SERVICE_BASE}" == "mufg-settlement-daemon" ]]; then
            # Verify no settlement lock file
            if [[ -f "${LOCK_FILE}" ]]; then
                output_result "BLOCKED" "LOCK_ACTIVE" "LOCK=${LOCK_FILE}" "Active settlement batch running. Lockfile present."
                exit 2
            else
                output_result "SUCCESS" "LOCK_FREE" "LOCK=NONE" "Settlement queue idle. Zero active batch locks."
                exit 0
            fi
        else
            output_result "SUCCESS" "READY" "PRECHECK=PASS" "Generic precheck passed."
            exit 0
        fi
        ;;

    stop)
        if [[ -f "${PID_FILE}" ]]; then
            PID_VAL=$(cat "${PID_FILE}")
            rm -f "${PID_FILE}"
            rm -f "${LOCK_FILE}"
            rm -f "${LISTENER_FILE}"
            output_result "SUCCESS" "STOPPED_VERIFIED" "PID_CLEARED=${PID_VAL}" "Graceful termination signal acknowledged. Resources unmapped."
            exit 0
        else
            rm -f "${LOCK_FILE}" "${LISTENER_FILE}"
            output_result "SUCCESS" "STOPPED_VERIFIED" "PID=NONE" "Service was already stopped."
            exit 0
        fi
        ;;

    start)
        # Generate realistic 5-digit PID
        NEW_PID=$(( 30000 + RANDOM % 40000 ))
        echo "${NEW_PID}" > "${PID_FILE}"

        if [[ "${SERVICE_BASE}" == "mufg-swift-gateway" ]]; then
            echo "BIND=0.0.0.0:8443 TLS=1.3 PROTOCOL=SWIFTNet" > "${LISTENER_FILE}"
            output_result "SUCCESS" "STARTED_VERIFIED" "PID=${NEW_PID},PORT=8443" "SWIFTNet Edge Gateway listener bound on :8443."
            exit 0
        elif [[ "${SERVICE_BASE}" == "mufg-settlement-daemon" ]]; then
            echo "STATE=IDLE THREADS=8 DB_POOL=CONNECTED" > "${LISTENER_FILE}"
            output_result "SUCCESS" "STARTED_VERIFIED" "PID=${NEW_PID},THREADS=8" "Settlement daemon initialized with 8 worker threads."
            exit 0
        else
            echo "STATE=RUNNING" > "${LISTENER_FILE}"
            output_result "SUCCESS" "STARTED_VERIFIED" "PID=${NEW_PID}" "Service started successfully."
            exit 0
        fi
        ;;

    verify)
        if [[ -f "${PID_FILE}" ]]; then
            PID_VAL=$(cat "${PID_FILE}")
            if [[ -f "${LISTENER_FILE}" ]]; then
                LISTENER_INFO=$(cat "${LISTENER_FILE}")
                output_result "SUCCESS" "HEALTHY" "PID=${PID_VAL}" "Process alive and listener responsive (${LISTENER_INFO})."
                exit 0
            else
                output_result "SUCCESS" "HEALTHY" "PID=${PID_VAL}" "Process PID is alive and healthy."
                exit 0
            fi
        else
            output_result "FAILED" "DOWN" "PID=MISSING" "Process is not running or PID file is missing."
            exit 1
        fi
        ;;

    *)
        echo "[ERROR] Invalid action: ${ACTION}" >&2
        exit 1
        ;;
esac

