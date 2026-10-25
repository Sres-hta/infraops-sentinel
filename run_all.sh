#!/usr/bin/env bash
# ==============================================================================
# MUFG Bank, Ltd. - Operations Infrastructure & Systems Management
# Project: InfraOps-Sentinel (Master Pipeline Runner)
# Script:  run_all.sh
# Purpose: Single-command execution of Phase 1 (Housekeeping & Archive Engine),
#          Phase 2 (SOP Start/Shutdown Orchestrator & Failure Circuit-Breaker),
#          and Phase 3 (Multi-Tab Excel Daily Check-Sheet Generator).
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="${SCRIPT_DIR}/venv/bin/python3"

if [[ ! -x "${VENV_PYTHON}" ]]; then
    echo "[ERROR] Virtual environment Python not found at: ${VENV_PYTHON}" >&2
    echo "[ERROR] Please initialize venv before executing run_all.sh" >&2
    exit 1
fi

echo "=================================================================================="
echo " MUFG BANK | INFRAOPS-SENTINEL: MASTER AUTOMATION PIPELINE"
echo " Target JD:  MUFG Operation Analyst (Requisition: 10078906-WD)"
echo " Governance: CAB Change Window CHG0049210 & Global Storage SLA Policy"
echo " Timestamp:  $(TZ="Asia/Kolkata" date +"%Y-%m-%d %H:%M:%S IST")"
echo "=================================================================================="

# ------------------------------------------------------------------------------
# STEP 0: Reset Database and Seed Multi-Platform Filesystem Sandbox
# ------------------------------------------------------------------------------
echo -e "\n>>> [STEP 0/3] Seeding Multi-Platform Sandbox & Refreshing SQLite State..."
rm -f "${SCRIPT_DIR}/data/infraops_sentinel.db"
"${SCRIPT_DIR}/scripts/seed_mock_filesystem.sh"

# ------------------------------------------------------------------------------
# STEP 1: Phase 1 - Automated Multi-Platform Housekeeping & Archive Engine
# ------------------------------------------------------------------------------
echo -e "\n>>> [STEP 1/3] Executing Phase 1: Storage Housekeeping & Telemetry Engine..."
"${VENV_PYTHON}" "${SCRIPT_DIR}/src/housekeeping_engine.py"

# ------------------------------------------------------------------------------
# STEP 2: Phase 2 - SOP-Driven System Shutdown & Startup Runbook Orchestrator
# ------------------------------------------------------------------------------
echo -e "\n>>> [STEP 2/3] Executing Phase 2: Start/Shutdown Runbook & Failure Circuit-Breaker..."
"${VENV_PYTHON}" "${SCRIPT_DIR}/src/runbook_orchestrator.py"

# ------------------------------------------------------------------------------
# STEP 3: Phase 3 - Corporate Multi-Tab Excel Daily Check-Sheet Generator
# ------------------------------------------------------------------------------
echo -e "\n>>> [STEP 3/3] Executing Phase 3: Generating Corporate Multi-Tab Excel Check-Sheet..."
"${VENV_PYTHON}" "${SCRIPT_DIR}/src/checksheet_excel_generator.py"

echo -e "\n=================================================================================="
echo " MUFG INFRAOPS-SENTINEL: MASTER PIPELINE EXECUTION COMPLETED SUCCESSFULLY"
echo "=================================================================================="
echo " [DELIVERABLES SUMMARY]"
echo "  - SQLite Database:      ${SCRIPT_DIR}/data/infraops_sentinel.db"
echo "  - Excel Check-Sheet:    $(ls -t "${SCRIPT_DIR}/reports/"*.xlsx | head -n 1)"
echo "  - Audit Telemetry:      ${SCRIPT_DIR}/data/"
echo "  - Active Incidents:     INC0094821 (P2), INC0094822 (P2), INC0094899 (P1)"
echo "=================================================================================="

