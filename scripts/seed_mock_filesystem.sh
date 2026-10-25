#!/usr/bin/env bash
# ==============================================================================
# MUFG Bank, Ltd. - Operations Infrastructure & Systems Management
# Project: InfraOps-Sentinel (Housekeeping Engine)
# Script:  seed_mock_filesystem.sh
# Purpose: Generates a realistic multi-platform mock filesystem sandbox with
#          backdated timestamps (1-45+ days) and active (<24h) locked files.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SANDBOX_DIR="${PROJECT_ROOT}/sandbox_fs"

echo "[INFO] Initializing MUFG InfraOps-Sentinel Mock Filesystem at: ${SANDBOX_DIR}"

# Clean existing sandbox for deterministic test runs
if [[ -d "${SANDBOX_DIR}" ]]; then
    echo "[INFO] Cleaning previous sandbox directory..."
    rm -rf "${SANDBOX_DIR}"
fi

# Define directory structures
UNIX_LOG_DIR="${SANDBOX_DIR}/var/log/mufg_app"
UNIX_BATCH_DIR="${SANDBOX_DIR}/var/log/mufg_batch"
WIN_DUMP_DIR="${SANDBOX_DIR}/win_temp_dump/C_Temp_Dump"
WIN_SQL_DIR="${SANDBOX_DIR}/win_temp_dump/D_SQLData"
AS400_SPOOL_DIR="${SANDBOX_DIR}/as400_qsysprt/QSYSPRT"
AS400_ASP_DIR="${SANDBOX_DIR}/as400_qsysprt/QSYS_LIB"

mkdir -p "${UNIX_LOG_DIR}"
mkdir -p "${UNIX_BATCH_DIR}"
mkdir -p "${WIN_DUMP_DIR}"
mkdir -p "${WIN_SQL_DIR}"
mkdir -p "${AS400_SPOOL_DIR}"
mkdir -p "${AS400_ASP_DIR}"

# Helper function to generate mock payload files
generate_file() {
    local filepath="$1"
    local size_kb="$2"
    local days_ago="$3"
    local header_msg="$4"

    # Create dummy content with repeating text to simulate log data
    {
        echo "=== [MUFG INFRA-SENTINEL AUDIT RECORD] ==="
        echo "File: $(basename "${filepath}")"
        echo "Created Timestamp Reference: ${days_ago} days ago"
        echo "Header: ${header_msg}"
        echo "System: MUFG Core Banking Production Service"
        echo "----------------------------------------"
    } > "${filepath}"

    # Pad with realistic log text lines
    local current_size
    current_size=$(wc -c < "${filepath}")
    local target_bytes=$(( size_kb * 1024 ))
    local remaining=$(( target_bytes - current_size ))

    if (( remaining > 0 )); then
        # Pad with filler characters without triggering SIGPIPE in set -eo pipefail
        head -c "${remaining}" /dev/zero | tr '\0' 'L' >> "${filepath}"
    fi

    # Set backdated modification and access timestamps
    touch -d "${days_ago} days ago" "${filepath}"
}

# Helper function to create gzipped files with backdated timestamps
generate_gz_file() {
    local filepath_uncompressed="$1"
    local size_kb="$2"
    local days_ago="$3"
    local header_msg="$4"

    generate_file "${filepath_uncompressed}" "${size_kb}" "${days_ago}" "${header_msg}"
    gzip -f "${filepath_uncompressed}"
    touch -d "${days_ago} days ago" "${filepath_uncompressed}.gz"
}

echo "[INFO] Seeding Unix RHEL (/var/log/mufg_app) filesystem mock..."

# 1. Active files (0 to 1 day old - MUST BE PRESERVED)
generate_file "${UNIX_LOG_DIR}/core_banking_txn.log" 250 0 "ACTIVE LIVE TRANSACTION LOG - DO NOT TOUCH"
generate_file "${UNIX_LOG_DIR}/swift_fin_gateway.log" 300 0 "ACTIVE SWIFT FINANCIAL GATEWAY MESSAGES"
generate_file "${UNIX_LOG_DIR}/ebanking_api_current.log" 180 1 "CURRENT E-BANKING REST API LOG"
generate_file "${UNIX_LOG_DIR}/active_scratch_proc.tmp" 80 0 "ACTIVE WORKER TMP FILE - EXEMPT FROM IMMEDIATE PURGE"

# 2. Medium-aged logs (>7 days, <=30 days - MUST BE COMPRESSED TO .gz)
generate_file "${UNIX_LOG_DIR}/core_banking_txn_20261005.log" 750 10 "AGED TRANSACTION LOG (10 DAYS) - ELIGIBLE FOR GZIP"
generate_file "${UNIX_LOG_DIR}/swift_fin_gateway_20261001.log" 900 14 "AGED SWIFT GATEWAY LOG (14 DAYS) - ELIGIBLE FOR GZIP"
generate_file "${UNIX_LOG_DIR}/securities_settlement_20260925.log" 1200 20 "AGED SECURITIES SETTLEMENT LOG (20 DAYS) - ELIGIBLE FOR GZIP"
generate_file "${UNIX_LOG_DIR}/forex_rate_feed_20260918.log" 550 27 "AGED FOREX RATE FEED LOG (27 DAYS) - ELIGIBLE FOR GZIP"

# 3. Old archives (>30 days - MUST BE PURGED)
generate_gz_file "${UNIX_LOG_DIR}/core_banking_txn_20260825.log" 600 35 "EXPIRED ARCHIVE (35 DAYS) - ELIGIBLE FOR PURGE"
generate_gz_file "${UNIX_LOG_DIR}/swift_fin_gateway_20260815.log" 800 42 "EXPIRED ARCHIVE (42 DAYS) - ELIGIBLE FOR PURGE"
generate_gz_file "${UNIX_LOG_DIR}/ebanking_audit_20260805.log" 1100 50 "EXPIRED ARCHIVE (50 DAYS) - ELIGIBLE FOR PURGE"
generate_file "${UNIX_LOG_DIR}/uncompressed_legacy_20260810.log" 1500 45 "EXPIRED UNCOMPRESSED LOG (45 DAYS) - ELIGIBLE FOR PURGE"

# 4. Crash dumps and temporary files (>1 day old - MUST BE PURGED)
generate_file "${UNIX_LOG_DIR}/mufg_core_txn_worker.core" 2048 5 "ORPHANED CORE DUMP (5 DAYS) - ELIGIBLE FOR PURGE"
generate_file "${UNIX_LOG_DIR}/jvm_fatal_crash.dmp" 1500 12 "JVM FATAL ERROR DUMP (12 DAYS) - ELIGIBLE FOR PURGE"
generate_file "${UNIX_LOG_DIR}/batch_import_session_01.tmp" 400 4 "AGED TMP SCRATCH FILE (4 DAYS) - ELIGIBLE FOR PURGE"
generate_file "${UNIX_LOG_DIR}/batch_import_session_02.tmp" 600 9 "AGED TMP SCRATCH FILE (9 DAYS) - ELIGIBLE FOR PURGE"

# 5. Unix batch directory (/var/log/mufg_app/batch_jobs)
generate_file "${UNIX_BATCH_DIR}/eod_reconcile_active.log" 120 0 "ACTIVE BATCH RUN LOG"
generate_file "${UNIX_BATCH_DIR}/eod_reconcile_20261006.log" 650 9 "BATCH RECON LOG (9 DAYS) - ELIGIBLE FOR GZIP"
generate_gz_file "${UNIX_BATCH_DIR}/eod_reconcile_20260828.log" 500 38 "EXPIRED BATCH ARCHIVE (38 DAYS) - ELIGIBLE FOR PURGE"
generate_file "${UNIX_BATCH_DIR}/scratch_sort.tmp" 350 3 "AGED BATCH TEMP (3 DAYS) - ELIGIBLE FOR PURGE"

echo "[INFO] Seeding Windows Server (C:\\Temp\\Dump and D:\\SQLData) mock..."

# Windows C:\Temp\Dump (Retention > 3 days purge)
generate_file "${WIN_DUMP_DIR}/active_iis_session.tmp" 100 0 "ACTIVE WINDOWS SESSION TEMP"
generate_file "${WIN_DUMP_DIR}/current_apppool.dmp" 150 1 "CURRENT LIVE MINIDUMP (1 DAY) - PRESERVE"
generate_file "${WIN_DUMP_DIR}/iis_w3wp_crash_20261009.dmp" 4096 6 "EXPIRED IIS CRASH DUMP (6 DAYS) - ELIGIBLE FOR PURGE"
generate_file "${WIN_DUMP_DIR}/sql_diag_dump_20261006.dmp" 3072 9 "EXPIRED SQL DIAGNOSTIC DUMP (9 DAYS) - ELIGIBLE FOR PURGE"
generate_file "${WIN_DUMP_DIR}/report_generator_temp_20261007.tmp" 1800 8 "EXPIRED REPORT SCRATCH (8 DAYS) - ELIGIBLE FOR PURGE"

# Windows D:\SQLData (Simulated high disk usage partition)
generate_file "${WIN_SQL_DIR}/MUFG_PAYMENT_PROD.mdf" 10240 2 "PRIMARY DATABASE FILE - CRITICAL PRODUCTION"
generate_file "${WIN_SQL_DIR}/MUFG_PAYMENT_PROD_1.ndf" 8192 2 "SECONDARY DATABASE FILE - CRITICAL PRODUCTION"
generate_file "${WIN_SQL_DIR}/MUFG_PAYMENT_PROD_log.ldf" 5120 0 "ACTIVE SQL TRANSACTION LOG"
generate_file "${WIN_SQL_DIR}/temp_diff_backup_scratch.tmp" 1024 4 "SQL DIFF SCRATCH TMP (4 DAYS) - PURGEABLE"

echo "[INFO] Seeding AS400 / IBM iSeries (QSYSPRT Spool & QSYS.LIB) mock..."

# AS400 Spool Files (Retention > 14 days archive, Job logs > 30 days purge)
generate_file "${AS400_SPOOL_DIR}/SPL_DAILY_POSTING_20261014.SPL" 400 1 "ACTIVE SPOOL FILE (1 DAY) - PRESERVE"
generate_file "${AS400_SPOOL_DIR}/SPL_MONTH_END_GL_20260925.SPL" 2500 20 "AGED SPOOL FILE (20 DAYS) - ELIGIBLE FOR ARCHIVE"
generate_file "${AS400_SPOOL_DIR}/SPL_SWIFT_OUTWARD_20260918.SPL" 1800 27 "AGED SPOOL FILE (27 DAYS) - ELIGIBLE FOR ARCHIVE"
generate_file "${AS400_SPOOL_DIR}/JOBLOG_QP0ZSPWP_20260830.LOG" 1400 46 "EXPIRED JOBLOG (46 DAYS) - ELIGIBLE FOR PURGE"
generate_file "${AS400_SPOOL_DIR}/JOBLOG_QZDASOINIT_20260815.LOG" 1600 61 "EXPIRED JOBLOG (61 DAYS) - ELIGIBLE FOR PURGE"

# AS400 QSYS.LIB (Simulated ASP high consumption)
generate_file "${AS400_ASP_DIR}/JRNRCV_PRD_00412.JRN" 12288 3 "ACTIVE PRODUCTION JOURNAL RECEIVER"
generate_file "${AS400_ASP_DIR}/JRNRCV_PRD_00413.JRN" 10240 1 "CURRENT PRODUCTION JOURNAL RECEIVER"

echo "[INFO] Mock filesystem seeding completed successfully."
echo "[INFO] Summary of seeded directories:"
find "${SANDBOX_DIR}" -type d -exec echo " - {}" \;
echo "[INFO] Total seeded files: $(find "${SANDBOX_DIR}" -type f | wc -l)"
