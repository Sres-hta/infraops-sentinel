# InfraOps-Sentinel: Automated Multi-Platform System Housekeeping, Start/Shutdown Runbook Orchestrator & Excel Check-Sheet Suite

**Candidate:** Sreshta Sarkar | **Target Role:** Operation Analyst | **MUFG Requisition:** `10078906-WD`  
**Core Mandate:** *"System housekeeping, shutdown and start in accordance with defined procedures and SLAs; Complete daily check sheet and reporting."*  
**Platforms Covered:** Unix (RHEL 9), Windows Server 2022, IBM iSeries / AS400  
**Change Governance:** ServiceNow CAB Change `CHG0049210` (Monthly Patching & IPL Maintenance Window)

---

## 1. Executive Summary

In tier-1 financial institutions like **MUFG Bank, Ltd.**, core banking systems, payment routing engines, and interbank batch processors operate across heterogeneous mainframe, Unix, and Windows environments. Production operations analysts must guarantee 99.999% availability while strictly adhering to change management governance, rigorous storage retention policies, and ordered startup/shutdown procedures.

**`InfraOps-Sentinel`** is an enterprise-grade automation engine designed to solve three critical operational workflows:
1. **Automated Multi-Platform Housekeeping & Storage Governance:** Safely purges aged crash dumps, compresses eligible transaction logs (`gzip`), enforces active file protection (`<= 24h` locks), and automatically escalates persistent storage breaches via ServiceNow P2 tickets.
2. **SOP-Driven Start/Shutdown Runbook Orchestration:** Automates complex top-down shutdown (`Tier 1 -> Tier 2 -> Tier 3`) and bottom-up startup (`Tier 3 -> Tier 2 -> Tier 1`) procedures with millisecond-accurate SLA tracking, automated retry backoff, and upstream ingress circuit-breaking.
3. **Automated Corporate Check-Sheet & Shift Handover Engine:** Automatically queries audit telemetry from SQLite and formats a 5-tab, color-coded executive Excel check-sheet (`.xlsx`) adhering to MUFG Operations Risk & Governance standards.

---

## 2. System Architecture

```
                               +-----------------------------------------------------+
                               |           CAB CHANGE WINDOW: CHG0049210             |
                               | (Monthly Operating System Patching & IPL Lifecycle) |
                               +-----------------------------------------------------+
                                                          |
                 +----------------------------------------+----------------------------------------+
                 |                                        |                                        |
                 v                                        v                                        v
     +-----------------------+                +-----------------------+                +-----------------------+
     |   TIER 1: DMZ EDGE    |                |  TIER 2: MIDDLEWARE   |                |    TIER 3: CORE DB    |
     |   mufg-rhel-core01    |                |     mufg-win-pay01    |                |   mufg-as400-core01   |
     |  (SWIFT Net Gateway)  |                | (ISO20022 Pay Engine) |                |   (QBATCH / QINTER)   |
     |                       |                |   mufg-rhel-batch02   |                |   mufg-as400-prd02    |
     |                       |                |  (Settlement Daemon)  |                |   (MUFGCORE Ledger)   |
     +-----------------------+                +-----------------------+                +-----------------------+
                 |                                        |                                        |
                 +----------------------------------------+----------------------------------------+
                                                          |
                                                          v
                                     +-----------------------------------------+
                                     |        INFRAOPS-SENTINEL CORE           |
                                     +-----------------------------------------+
                                     |  1. Storage Housekeeping Engine         |
                                     |  2. Start/Shutdown Runbook Orchestrator |
                                     |  3. Circuit-Breaker & ServiceNow Engine |
                                     |  4. SQLite Audit Ledger (5 Tables)      |
                                     |  5. Multi-Tab Excel Checksheet Gen      |
                                     +-----------------------------------------+
                                                          |
                                +-------------------------+-------------------------+
                                |                                                   |
                                v                                                   v
               +----------------------------------+               +----------------------------------+
               |  MUFG Daily Operations Workbook  |               |  ServiceNow Incident Escalation  |
               | (MUFG_Daily_Ops_CheckSheet.xlsx) |               |  INC0094821 (P2), INC0094822(P2) |
               |    5 Color-Coded Audit Tabs      |               |  INC0094899 (P1 Critical Alert)  |
               +----------------------------------+               +----------------------------------+
```

---

## 3. Technical Phase Breakdown

### Phase 1: Automated Multi-Platform Housekeeping & Archive Engine
- **Active File Protection Rule:** Any file modified within the last 24 hours (`<= 1 day`) is strictly marked `SKIPPED_ACTIVE` to prevent corrupting in-flight core banking processes.
- **Tiered Retention Lifecycle:**
  - **Unix RHEL (`/var/log/mufg_app`):** Logs `> 7 days` compressed to `.gz`; archives `> 30 days` and orphan crash dumps (`.core`, `.dmp`, `.tmp` `> 1 day`) purged.
  - **Windows Server (`C:\Temp\Dump`):** Temporary crash dumps and diagnostic traces `> 3 days` purged.
  - **AS400 / IBM iSeries (`QSYSPRT`):** Spool files `> 14 days` archived; expired job logs (`> 30 days`) purged.
- **SLA Telemetry & Escalation:**
  - Evaluates post-housekeeping disk & inode utilization against SLA thresholds (Warning: `75%`, Critical: `85%`).
  - Automatically raises **ServiceNow P2 Storage Alert tickets** (`INC0094821`, `INC0094822`) assigned to `MUFG-GLOBAL-STORAGE-L2` when disk usage remains above `85%` after purging.
  - Generates SHA-256 cryptographic checksums for every audit execution ledger.

### Phase 2: SOP-Driven Shutdown, Gate Check & Startup Orchestrator
- **Top-Down Shutdown (`Tier 1 -> Tier 2 -> Tier 3`):**
  1. *Tier 1 (mufg-rhel-core01):* Drains active inbound sockets (`:8443 == 0`), stops `mufg-swift-gateway.service` (SLA: `30s`).
  2. *Tier 2 (mufg-win-pay01):* Drains MSMQ queues (`Depth == 0`), stops `MUFG_ISO20022_PaymentEngine` (SLA: `45s`).
  3. *Tier 2 (mufg-rhel-batch02):* Verifies zero active PID locks, stops `mufg-settlement-daemon.service` (SLA: `30s`).
  4. *Tier 3 (mufg-as400-core01):* Drains teller sessions, issues `ENDSBS SBS(QBATCH/QINTER) OPTION(*CNTRLD) DELAY(60)` (SLA: `90s`).
  5. *Tier 3 (mufg-as400-prd02):* Verifies journal receiver sync, issues `ENDSBS SBS(MUFGCORE) OPTION(*CNTRLD) DELAY(60)` (SLA: `90s`).
- **Maintenance Gate Verification:** Verifies all 5 subsystems are in `STOPPED_VERIFIED` state before permitting maintenance window operations.
- **Bottom-Up Startup (`Tier 3 -> Tier 2 -> Tier 1`) & Circuit-Breaker:**
  - Subsystems `QBATCH`, `QINTER`, `MUFGCORE`, and `mufg-settlement-daemon` start cleanly.
  - **Injected Failure Scenario:** `mufg-win-pay01` fails port `9443` HSM crypto handshake (48.4s elapsed vs 45s SLA limit). Automated SOP retry also fails (49.1s elapsed).
  - **Upstream Dependency Circuit-Breaker:** Automatically marks payment engine `FAILED_SLA_BREACH`, halts dependent Tier 1 SWIFT Gateway startup (`HALTED_DEPENDENCY_BLOCK`), and triggers a **P1 Critical ServiceNow Incident (`INC0094899`)** assigned to `MUFG-WIN-MIDDLEWARE-L2`.

### Phase 3: Corporate Multi-Tab Excel Check-Sheet Engine
- Generates a polished, corporate-formatted Excel workbook (`reports/MUFG_Daily_Ops_CheckSheet_20261015.xlsx`) using `openpyxl`.
- Adheres to MUFG Operations Risk & Governance standards:
  - **Tab 1 (`01_Shift_SignOff_Summary`):** Executive shift metadata, RAG indicator, KPI summary cards, and formal L1 -> L2 handover checklist.
  - **Tab 2 (`02_Start_Shutdown_SOP_Audit`):** Complete 16-step execution log ordered by dependency hierarchy with elapsed latency and SLA status.
  - **Tab 3 (`03_Storage_Housekeeping_SLA`):** 6-node storage audit showing before/after capacity, reclaimed MB, and SHA-256 manifest hash.
  - **Tab 4 (`04_File_Action_Audit_Ledger`):** All 36 file actions with **canonical enterprise path normalization** (`/var/log/...`, `C:\Temp\Dump\...`, `/QSYS.LIB/...`).
  - **Tab 5 (`05_L2_L3_Escalation_Tracker`):** ServiceNow incident tracker detailing root cause, severity, assignment group, and L1 action plan.

---

## 4. SQLite Schema Reference (`data/infraops_sentinel.db`)

```sql
-- 1. Housekeeping Audit Log
CREATE TABLE housekeeping_audit_log (
    run_id TEXT NOT NULL,
    timestamp_ist TEXT NOT NULL,
    hostname TEXT NOT NULL,
    platform TEXT NOT NULL CHECK(platform IN ('UNIX_RHEL', 'WINDOWS_SVR', 'AS400_ISERIES')),
    filesystem_path TEXT NOT NULL,
    before_used_pct REAL NOT NULL,
    after_used_pct REAL NOT NULL,
    inodes_used_pct REAL NOT NULL,
    files_compressed INTEGER NOT NULL DEFAULT 0,
    files_purged INTEGER NOT NULL DEFAULT 0,
    files_skipped INTEGER NOT NULL DEFAULT 0,
    space_reclaimed_mb REAL NOT NULL DEFAULT 0.0,
    sha256_manifest_hash TEXT NOT NULL,
    sla_status TEXT NOT NULL CHECK(sla_status IN ('COMPLIANT', 'WARNING', 'CRITICAL_ESCALATED')),
    servicenow_inc_ref TEXT,
    PRIMARY KEY (run_id, hostname, filesystem_path)
);

-- 2. File Action Ledger
CREATE TABLE file_action_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_age_days INTEGER NOT NULL,
    action_taken TEXT NOT NULL CHECK(action_taken IN ('COMPRESSED_GZ', 'PURGED_RETENTION', 'SKIPPED_ACTIVE')),
    size_kb REAL NOT NULL,
    timestamp_ist TEXT NOT NULL
);

-- 3. Runbook SOP Execution Log
CREATE TABLE runbook_execution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    step_id TEXT NOT NULL UNIQUE,
    change_ref TEXT NOT NULL,
    runbook_id TEXT NOT NULL,
    phase TEXT NOT NULL CHECK(phase IN ('PRE_CHECK', 'SHUTDOWN', 'STARTUP', 'ROLLBACK_ESCALATION')),
    execution_order INTEGER NOT NULL,
    tier TEXT NOT NULL,
    hostname TEXT NOT NULL,
    platform TEXT NOT NULL CHECK(platform IN ('UNIX_RHEL', 'WINDOWS_SVR', 'AS400_ISERIES')),
    service_name TEXT NOT NULL,
    sop_command TEXT NOT NULL,
    precheck_status TEXT NOT NULL,
    target_state TEXT NOT NULL,
    actual_state TEXT NOT NULL,
    pid_or_port_check TEXT NOT NULL,
    elapsed_sec REAL NOT NULL DEFAULT 0.0,
    sla_limit_sec REAL NOT NULL DEFAULT 0.0,
    sla_status TEXT NOT NULL CHECK(sla_status IN ('COMPLIANT', 'SLA_BREACHED', 'HALTED_UPSTREAM')),
    servicenow_inc_ref TEXT,
    timestamp_ist TEXT NOT NULL
);

-- 4. ServiceNow Incidents Table
CREATE TABLE servicenow_incidents (
    incident_ref TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    hostname TEXT NOT NULL,
    filesystem_path TEXT DEFAULT '',
    severity TEXT NOT NULL,
    category TEXT NOT NULL,
    short_description TEXT NOT NULL,
    assignment_group TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    created_at_ist TEXT NOT NULL
);

-- 5. Daily Check-Sheet Manifest Table
CREATE TABLE daily_checksheet_manifest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sheet_id TEXT NOT NULL UNIQUE,
    report_date TEXT NOT NULL,
    shift TEXT NOT NULL CHECK(shift IN ('APAC_MORNING', 'EMEA_AFTERNOON', 'US_EVENING')),
    total_systems_checked INTEGER NOT NULL DEFAULT 0,
    healthy_count INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    critical_count INTEGER NOT NULL DEFAULT 0,
    excel_file_path TEXT,
    pdf_file_path TEXT,
    generated_at_ist TEXT NOT NULL,
    approved_by TEXT
);
```

---

## 5. Quick Start & Execution

### Prerequisites
- Debian/Ubuntu Linux or compatible POSIX environment
- Python 3.10+
- Standard coreutils: `bash`, `gzip`, `stat`, `sha256sum`, `awk`

### Single-Command Master Run
To execute all 3 phases in an automated end-to-end sequence:

```bash
cd ./infraops-sentinel
./run_all.sh
```

### Modular Execution
```bash
# 1. Seed mock multi-platform filesystem
./scripts/seed_mock_filesystem.sh

# 2. Run Phase 1: Storage Housekeeping Engine
./venv/bin/python3 src/housekeeping_engine.py

# 3. Run Phase 2: Start/Shutdown Runbook Orchestrator
./venv/bin/python3 src/runbook_orchestrator.py

# 4. Run Phase 3: Excel Check-Sheet Generator
./venv/bin/python3 src/checksheet_excel_generator.py
```

---

## 6. Verification & Sample Output

### SQLite Audit Verification
```bash
./venv/bin/python3 -c "
import sqlite3, pandas as pd
conn = sqlite3.connect('data/infraops_sentinel.db')
print('=== SERVICENOW INCIDENTS ===')
print(pd.read_sql_query('SELECT incident_ref, severity, hostname, assignment_group, short_description FROM servicenow_incidents', conn).to_string(index=False))
"
```

**Output:**
```
incident_ref      severity         hostname       assignment_group                                                                 short_description
  INC0094821     P2 - High   mufg-win-pay01 MUFG-GLOBAL-STORAGE-L2 CRITICAL: Mount D:\SQLData on mufg-win-pay01 remains at 87.7% post-housekeeping...
  INC0094822     P2 - High mufg-as400-prd02 MUFG-GLOBAL-STORAGE-L2 CRITICAL: System ASP /QSYS.LIB on mufg-as400-prd02 remains at 91.0% post-housekeeping...
  INC0094899 P1 - Critical   mufg-win-pay01 MUFG-WIN-MIDDLEWARE-L2 P1 CRITICAL: Startup SLA breach on mufg-win-pay01 (MUFG_ISO20022_PaymentEngine)...
```

---

## 7. Deliverables & Documentation Index
- `reports/MUFG_Daily_Ops_CheckSheet_20261015.xlsx`: Master 5-tab corporate Excel report.
- `docs/InfraOps_Sentinel_MUFG_Interview_Guide.pdf`: Pocket mobile study guide (`4.5 x 8.0 inch`).
- `docs/Sreshta_Sarkar_MUFG_Resume.docx`: Dual-project professional resume.

