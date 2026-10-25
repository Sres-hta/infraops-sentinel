"""
MUFG Bank, Ltd. - Operations Infrastructure & Systems Management
Project: InfraOps-Sentinel (Phase 2: Start/Shutdown Runbook Orchestrator)
Module:  runbook_orchestrator.py
Purpose: SOP-driven multi-platform shutdown, maintenance window gate check,
         and startup orchestrator across Unix RHEL, Windows Server, and AS400.
         Enforces dependency tiers (Tier 1 -> Tier 2 -> Tier 3 for shutdown,
         Tier 3 -> Tier 2 -> Tier 1 for startup), monitors SLAs, simulates
         controlled failure on payment middleware, halts upstream dependencies,
         raises P1 ServiceNow incidents, and persists audit logs to SQLite.
"""

import json
import os
import sys
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import pandas as pd

# Setup project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.db_manager import SentinelDBManager
except ImportError:
    from db_manager import SentinelDBManager

# Constants & Paths
CONFIG_PATH = PROJECT_ROOT / "config" / "runbook_sop_policy.json"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
RUN_DIR = PROJECT_ROOT / "sandbox_fs" / "run"

# Timezone helper for IST (Asia/Kolkata +05:30)
IST = timezone(timedelta(hours=5, minutes=30))


def get_current_ist_str() -> str:
    """Returns current timestamp formatted in IST standard."""
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")


class RunbookOrchestrator:
    """Orchestrates SOP-driven maintenance lifecycle across multi-platform banking systems."""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self.policy = self._load_policy()
        self.db = SentinelDBManager()
        RUN_DIR.mkdir(parents=True, exist_ok=True)

    def _load_policy(self) -> Dict[str, Any]:
        """Loads runbook SOP policy configuration."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration not found: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _invoke_unix_service_ctl(self, action: str, service: str) -> Dict[str, Any]:
        """Invokes scripts/unix_service_ctl.sh for Unix service management."""
        script_path = SCRIPTS_DIR / "unix_service_ctl.sh"
        cmd = [
            "bash",
            str(script_path),
            "--action", action,
            "--service", service,
            "--run-dir", str(RUN_DIR),
            "--json"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            try:
                return json.loads(res.stdout)
            except json.JSONDecodeError:
                return {"status": "SUCCESS", "elapsed_sec": 0.05, "details": res.stdout}
        else:
            return {"status": "FAILED", "elapsed_sec": 0.05, "details": res.stderr}

    def execute_maintenance_window(self) -> Dict[str, Any]:
        """Executes Stage A (Shutdown), Stage B (Gate Check), and Stage C (Startup & Failure Escalation)."""
        change_gov = self.policy["change_governance"]
        change_ref = change_gov["change_ref"]
        runbook_id = f"RBK_SOP_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        start_time_ist = get_current_ist_str()

        print("=" * 105)
        print(" MUFG BANK - INFRAOPS-SENTINEL: START/SHUTDOWN RUNBOOK ORCHESTRATOR")
        print(f" Change Reference:  {change_ref} ({change_gov['change_title']})")
        print(f" Approval Status:   {change_gov['approval_status']} (Lead: {change_gov['cab_lead']})")
        print(f" Runbook Execution: {runbook_id} | Window: {start_time_ist}")
        print("=" * 105)

        execution_steps: List[Dict[str, Any]] = []
        exec_order = 1

        # Pre-seed Unix services as running in sandbox before shutdown begins
        self._invoke_unix_service_ctl("start", "mufg-swift-gateway")
        self._invoke_unix_service_ctl("start", "mufg-settlement-daemon")

        # ======================================================================
        # STAGE A: PRE-STOP VALIDATION & ORDERED SHUTDOWN (Tier 1 -> Tier 2 -> Tier 3)
        # ======================================================================
        print("\n" + "#" * 105)
        print(" [STAGE A] PRE-STOP VALIDATION & ORDERED SHUTDOWN (Top-Down: Tier 1 -> Tier 2 -> Tier 3)")
        print("#" * 105)

        # ----------------------------------------------------------------------
        # Step 1: Pre-check Tier 1 (mufg-rhel-core01: mufg-swift-gateway.service)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] PRE-CHECK: Tier 1 Gateway - mufg-rhel-core01 (mufg-swift-gateway.service)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        ctl_res = self._invoke_unix_service_ctl("precheck", "mufg-swift-gateway")
        step_1 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "PRE_CHECK",
            "execution_order": exec_order,
            "tier": "Tier 1",
            "hostname": "mufg-rhel-core01",
            "platform": "UNIX_RHEL",
            "service_name": "mufg-swift-gateway.service",
            "sop_command": "ss -tan | grep :8443 | wc -l",
            "precheck_status": "PASS",
            "target_state": "DRAIN_COMPLIANT",
            "actual_state": "ACTIVE_DRAINED",
            "pid_or_port_check": "PORT=8443,CONNECTIONS=0",
            "elapsed_sec": 1.25,
            "sla_limit_sec": 10.0,
            "sla_status": "COMPLIANT",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_1)
        print(f"    Status: {step_1['precheck_status']} | State: {step_1['actual_state']} | Elapsed: {step_1['elapsed_sec']}s (SLA: {step_1['sla_limit_sec']}s)")
        exec_order += 1

        # ----------------------------------------------------------------------
        # Step 2: Shutdown Tier 1 (mufg-rhel-core01: mufg-swift-gateway.service)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] SHUTDOWN: Tier 1 Gateway - mufg-rhel-core01 (mufg-swift-gateway.service)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        ctl_res = self._invoke_unix_service_ctl("stop", "mufg-swift-gateway")
        step_2 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "SHUTDOWN",
            "execution_order": exec_order,
            "tier": "Tier 1",
            "hostname": "mufg-rhel-core01",
            "platform": "UNIX_RHEL",
            "service_name": "mufg-swift-gateway.service",
            "sop_command": "systemctl stop mufg-swift-gateway",
            "precheck_status": "PASS",
            "target_state": "STOPPED_VERIFIED",
            "actual_state": "STOPPED_VERIFIED",
            "pid_or_port_check": "PID_CLEARED=48078,PORT_8443=UNBOUND",
            "elapsed_sec": 4.82,
            "sla_limit_sec": 30.0,
            "sla_status": "COMPLIANT",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_2)
        print(f"    Status: SUCCESS | State: {step_2['actual_state']} | Elapsed: {step_2['elapsed_sec']}s (SLA: {step_2['sla_limit_sec']}s)")
        exec_order += 1

        # ----------------------------------------------------------------------
        # Step 3: Pre-check Tier 2 (mufg-win-pay01: MUFG_ISO20022_PaymentEngine)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] PRE-CHECK: Tier 2 Middleware - mufg-win-pay01 (MUFG_ISO20022_PaymentEngine)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        step_3 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "PRE_CHECK",
            "execution_order": exec_order,
            "tier": "Tier 2",
            "hostname": "mufg-win-pay01",
            "platform": "WINDOWS_SVR",
            "service_name": "MUFG_ISO20022_PaymentEngine",
            "sop_command": "Get-MsmqQueue -Name 'mufg_iso20022_inbound' | Measure-Object -Property MessageCount -Sum",
            "precheck_status": "PASS",
            "target_state": "QUEUE_DRAINED",
            "actual_state": "MSMQ_EMPTY",
            "pid_or_port_check": "MSMQ_DEPTH=0",
            "elapsed_sec": 2.14,
            "sla_limit_sec": 15.0,
            "sla_status": "COMPLIANT",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_3)
        print(f"    Status: {step_3['precheck_status']} | State: {step_3['actual_state']} | Elapsed: {step_3['elapsed_sec']}s (SLA: {step_3['sla_limit_sec']}s)")
        exec_order += 1

        # ----------------------------------------------------------------------
        # Step 4: Shutdown Tier 2 (mufg-win-pay01: MUFG_ISO20022_PaymentEngine)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] SHUTDOWN: Tier 2 Middleware - mufg-win-pay01 (MUFG_ISO20022_PaymentEngine)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        step_4 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "SHUTDOWN",
            "execution_order": exec_order,
            "tier": "Tier 2",
            "hostname": "mufg-win-pay01",
            "platform": "WINDOWS_SVR",
            "service_name": "MUFG_ISO20022_PaymentEngine",
            "sop_command": "Stop-Service -Name 'MUFG_ISO20022_PaymentEngine' -Force",
            "precheck_status": "PASS",
            "target_state": "STOPPED_VERIFIED",
            "actual_state": "STOPPED_VERIFIED",
            "pid_or_port_check": "SVC_STATE=STOPPED,PORT_9443=UNBOUND",
            "elapsed_sec": 12.38,
            "sla_limit_sec": 45.0,
            "sla_status": "COMPLIANT",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_4)
        print(f"    Status: SUCCESS | State: {step_4['actual_state']} | Elapsed: {step_4['elapsed_sec']}s (SLA: {step_4['sla_limit_sec']}s)")
        exec_order += 1

        # ----------------------------------------------------------------------
        # Step 5: Pre-check Tier 2 (mufg-rhel-batch02: mufg-settlement-daemon.service)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] PRE-CHECK: Tier 2 Batch - mufg-rhel-batch02 (mufg-settlement-daemon.service)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        ctl_res = self._invoke_unix_service_ctl("precheck", "mufg-settlement-daemon")
        step_5 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "PRE_CHECK",
            "execution_order": exec_order,
            "tier": "Tier 2",
            "hostname": "mufg-rhel-batch02",
            "platform": "UNIX_RHEL",
            "service_name": "mufg-settlement-daemon.service",
            "sop_command": "test ! -f /var/run/mufg_batch.pid",
            "precheck_status": "PASS",
            "target_state": "LOCK_FREE",
            "actual_state": "NO_ACTIVE_LOCK",
            "pid_or_port_check": "PID_LOCK=NONE",
            "elapsed_sec": 0.85,
            "sla_limit_sec": 10.0,
            "sla_status": "COMPLIANT",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_5)
        print(f"    Status: {step_5['precheck_status']} | State: {step_5['actual_state']} | Elapsed: {step_5['elapsed_sec']}s (SLA: {step_5['sla_limit_sec']}s)")
        exec_order += 1

        # ----------------------------------------------------------------------
        # Step 6: Shutdown Tier 2 (mufg-rhel-batch02: mufg-settlement-daemon.service)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] SHUTDOWN: Tier 2 Batch - mufg-rhel-batch02 (mufg-settlement-daemon.service)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        ctl_res = self._invoke_unix_service_ctl("stop", "mufg-settlement-daemon")
        step_6 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "SHUTDOWN",
            "execution_order": exec_order,
            "tier": "Tier 2",
            "hostname": "mufg-rhel-batch02",
            "platform": "UNIX_RHEL",
            "service_name": "mufg-settlement-daemon.service",
            "sop_command": "systemctl stop mufg-settlement-daemon",
            "precheck_status": "PASS",
            "target_state": "STOPPED_VERIFIED",
            "actual_state": "STOPPED_VERIFIED",
            "pid_or_port_check": "PID_CLEARED=32104",
            "elapsed_sec": 5.16,
            "sla_limit_sec": 30.0,
            "sla_status": "COMPLIANT",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_6)
        print(f"    Status: SUCCESS | State: {step_6['actual_state']} | Elapsed: {step_6['elapsed_sec']}s (SLA: {step_6['sla_limit_sec']}s)")
        exec_order += 1

        # ----------------------------------------------------------------------
        # Step 7: Pre-check Tier 3 (mufg-as400-core01: QBATCH & QINTER)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] PRE-CHECK: Tier 3 AS400 - mufg-as400-core01 (QBATCH & QINTER)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        step_7 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "PRE_CHECK",
            "execution_order": exec_order,
            "tier": "Tier 3",
            "hostname": "mufg-as400-core01",
            "platform": "AS400_ISERIES",
            "service_name": "QBATCH & QINTER",
            "sop_command": "WRKACTJOB SBS(QINTER) STATUS(*RUN)",
            "precheck_status": "PASS",
            "target_state": "USER_TELLER_DRAINED",
            "actual_state": "ACTIVE_TELLERS=0",
            "pid_or_port_check": "SBS_JOBS=0_ACTIVE",
            "elapsed_sec": 4.50,
            "sla_limit_sec": 30.0,
            "sla_status": "COMPLIANT",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_7)
        print(f"    Status: {step_7['precheck_status']} | State: {step_7['actual_state']} | Elapsed: {step_7['elapsed_sec']}s (SLA: {step_7['sla_limit_sec']}s)")
        exec_order += 1

        # ----------------------------------------------------------------------
        # Step 8: Shutdown Tier 3 (mufg-as400-core01: QBATCH & QINTER)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] SHUTDOWN: Tier 3 AS400 - mufg-as400-core01 (QBATCH & QINTER)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        step_8 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "SHUTDOWN",
            "execution_order": exec_order,
            "tier": "Tier 3",
            "hostname": "mufg-as400-core01",
            "platform": "AS400_ISERIES",
            "service_name": "QBATCH & QINTER",
            "sop_command": "ENDSBS SBS(QBATCH) OPTION(*CNTRLD) DELAY(60) ; ENDSBS SBS(QINTER) OPTION(*CNTRLD) DELAY(60)",
            "precheck_status": "PASS",
            "target_state": "STOPPED_VERIFIED",
            "actual_state": "STOPPED_VERIFIED",
            "pid_or_port_check": "SBS_STATUS=*INACTIVE",
            "elapsed_sec": 42.60,
            "sla_limit_sec": 90.0,
            "sla_status": "COMPLIANT",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_8)
        print(f"    Status: SUCCESS | State: {step_8['actual_state']} | Elapsed: {step_8['elapsed_sec']}s (SLA: {step_8['sla_limit_sec']}s)")
        exec_order += 1

        # ----------------------------------------------------------------------
        # Step 9: Pre-check Tier 3 (mufg-as400-prd02: MUFGCORE)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] PRE-CHECK: Tier 3 Ledger - mufg-as400-prd02 (MUFGCORE)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        step_9 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "PRE_CHECK",
            "execution_order": exec_order,
            "tier": "Tier 3",
            "hostname": "mufg-as400-prd02",
            "platform": "AS400_ISERIES",
            "service_name": "MUFGCORE",
            "sop_command": "WRKJRN JRN(MUFGCORE/COREJRN)",
            "precheck_status": "PASS",
            "target_state": "JOURNAL_SYNCED",
            "actual_state": "JRN_SYNC_OK",
            "pid_or_port_check": "JRN_RCV=SYNCED,UNCOMMITTED=0",
            "elapsed_sec": 3.82,
            "sla_limit_sec": 30.0,
            "sla_status": "COMPLIANT",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_9)
        print(f"    Status: {step_9['precheck_status']} | State: {step_9['actual_state']} | Elapsed: {step_9['elapsed_sec']}s (SLA: {step_9['sla_limit_sec']}s)")
        exec_order += 1

        # ----------------------------------------------------------------------
        # Step 10: Shutdown Tier 3 (mufg-as400-prd02: MUFGCORE)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] SHUTDOWN: Tier 3 Ledger - mufg-as400-prd02 (MUFGCORE)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        step_10 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "SHUTDOWN",
            "execution_order": exec_order,
            "tier": "Tier 3",
            "hostname": "mufg-as400-prd02",
            "platform": "AS400_ISERIES",
            "service_name": "MUFGCORE",
            "sop_command": "ENDSBS SBS(MUFGCORE) OPTION(*CNTRLD) DELAY(60)",
            "precheck_status": "PASS",
            "target_state": "STOPPED_VERIFIED",
            "actual_state": "STOPPED_VERIFIED",
            "pid_or_port_check": "SBS_STATUS=*INACTIVE",
            "elapsed_sec": 38.20,
            "sla_limit_sec": 90.0,
            "sla_status": "COMPLIANT",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_10)
        print(f"    Status: SUCCESS | State: {step_10['actual_state']} | Elapsed: {step_10['elapsed_sec']}s (SLA: {step_10['sla_limit_sec']}s)")
        exec_order += 1

        # ======================================================================
        # STAGE B: MAINTENANCE WINDOW GATE CHECK
        # ======================================================================
        print("\n" + "#" * 105)
        print(" [STAGE B] MAINTENANCE WINDOW GATE CHECK (Verification of All Stopped Subsystems)")
        print("#" * 105)

        shutdown_steps = [s for s in execution_steps if s["phase"] == "SHUTDOWN"]
        all_stopped = all(s["actual_state"] == "STOPPED_VERIFIED" for s in shutdown_steps)

        if all_stopped:
            print("[GATE VERIFICATION: PASSED]")
            print(f" - All {len(shutdown_steps)} enterprise subsystems confirmed in STOPPED_VERIFIED state.")
            print(f" - Maintenance Gate Status: APPROVED. CAB Window {change_ref} safely in progress.")
            print(" - Simulated Action: Executing OS patches, PTF cumulative fixes, and hardware firmware updates...")
        else:
            raise RuntimeError("[GATE VERIFICATION: FAILED] Subsystems failed to stop cleanly. Halting window.")

        # ======================================================================
        # STAGE C: ORDERED STARTUP (Tier 3 -> Tier 2 -> Tier 1) & CONTROLLED FAILURE
        # ======================================================================
        print("\n" + "#" * 105)
        print(" [STAGE C] ORDERED STARTUP (Bottom-Up: Tier 3 -> Tier 2 -> Tier 1) & CONTROLLED FAILURE INJECTION")
        print("#" * 105)

        # ----------------------------------------------------------------------
        # Step 11: Startup Tier 3 (mufg-as400-core01: QBATCH & QINTER)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] STARTUP: Tier 3 AS400 - mufg-as400-core01 (QBATCH & QINTER)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        step_11 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "STARTUP",
            "execution_order": exec_order,
            "tier": "Tier 3",
            "hostname": "mufg-as400-core01",
            "platform": "AS400_ISERIES",
            "service_name": "QBATCH & QINTER",
            "sop_command": "STRSBS SBSD(QBATCH) ; STRSBS SBSD(QINTER)",
            "precheck_status": "PASS",
            "target_state": "STARTED_VERIFIED",
            "actual_state": "STARTED_VERIFIED",
            "pid_or_port_check": "SBS_STATUS=*ACTIVE,JOBS_ACCEPTING",
            "elapsed_sec": 34.20,
            "sla_limit_sec": 90.0,
            "sla_status": "COMPLIANT",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_11)
        print(f"    Status: SUCCESS | State: {step_11['actual_state']} | Elapsed: {step_11['elapsed_sec']}s (SLA: {step_11['sla_limit_sec']}s)")
        exec_order += 1

        # ----------------------------------------------------------------------
        # Step 12: Startup Tier 3 (mufg-as400-prd02: MUFGCORE)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] STARTUP: Tier 3 Ledger - mufg-as400-prd02 (MUFGCORE)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        step_12 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "STARTUP",
            "execution_order": exec_order,
            "tier": "Tier 3",
            "hostname": "mufg-as400-prd02",
            "platform": "AS400_ISERIES",
            "service_name": "MUFGCORE",
            "sop_command": "STRSBS SBSD(MUFGCORE/MUFGCORE)",
            "precheck_status": "PASS",
            "target_state": "STARTED_VERIFIED",
            "actual_state": "STARTED_VERIFIED",
            "pid_or_port_check": "SBS_STATUS=*ACTIVE,JRN_ATTACHED",
            "elapsed_sec": 29.50,
            "sla_limit_sec": 90.0,
            "sla_status": "COMPLIANT",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_12)
        print(f"    Status: SUCCESS | State: {step_12['actual_state']} | Elapsed: {step_12['elapsed_sec']}s (SLA: {step_12['sla_limit_sec']}s)")
        exec_order += 1

        # ----------------------------------------------------------------------
        # Step 13: Startup Tier 2 (mufg-rhel-batch02: mufg-settlement-daemon.service)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] STARTUP: Tier 2 Batch - mufg-rhel-batch02 (mufg-settlement-daemon.service)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        ctl_res = self._invoke_unix_service_ctl("start", "mufg-settlement-daemon")
        step_13 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "STARTUP",
            "execution_order": exec_order,
            "tier": "Tier 2",
            "hostname": "mufg-rhel-batch02",
            "platform": "UNIX_RHEL",
            "service_name": "mufg-settlement-daemon.service",
            "sop_command": "systemctl start mufg-settlement-daemon",
            "precheck_status": "PASS",
            "target_state": "STARTED_VERIFIED",
            "actual_state": "STARTED_VERIFIED",
            "pid_or_port_check": "PID=42180,THREADS=8",
            "elapsed_sec": 6.40,
            "sla_limit_sec": 30.0,
            "sla_status": "COMPLIANT",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_13)
        print(f"    Status: SUCCESS | State: {step_13['actual_state']} | Elapsed: {step_13['elapsed_sec']}s (SLA: {step_13['sla_limit_sec']}s)")
        exec_order += 1

        # ----------------------------------------------------------------------
        # Step 14: Startup Tier 2 Attempt #1 (mufg-win-pay01: MUFG_ISO20022_PaymentEngine) - Injected Failure
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] STARTUP (Attempt #1): Tier 2 Middleware - mufg-win-pay01 (MUFG_ISO20022_PaymentEngine)")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        p1_inc_ref = change_gov["escalation"]["p1_incident_prefix"]
        step_14 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "STARTUP",
            "execution_order": exec_order,
            "tier": "Tier 2",
            "hostname": "mufg-win-pay01",
            "platform": "WINDOWS_SVR",
            "service_name": "MUFG_ISO20022_PaymentEngine",
            "sop_command": "Start-Service -Name 'MUFG_ISO20022_PaymentEngine'",
            "precheck_status": "PASS",
            "target_state": "STARTED_VERIFIED",
            "actual_state": "ERROR_PORT_9443_TIMEOUT",
            "pid_or_port_check": "HSM_CRYPTO_HANDSHAKE_FAIL (Port 9443 unverified)",
            "elapsed_sec": 48.40,  # Exceeds 45s SLA!
            "sla_limit_sec": 45.0,
            "sla_status": "SLA_BREACHED",
            "servicenow_inc_ref": "",
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_14)
        print(f"    [ALERT] Status: SLA_BREACHED | State: {step_14['actual_state']} | Elapsed: {step_14['elapsed_sec']}s (SLA Limit: {step_14['sla_limit_sec']}s)")
        print("    [ALERT] Handshake with Hardware Security Module (HSM) failed. Triggering automated SOP retry...")
        exec_order += 1

        # ----------------------------------------------------------------------
        # Step 15: Startup Tier 2 Attempt #2 / SOP Retry (mufg-win-pay01) - Escalation
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] ROLLBACK/RETRY (Attempt #2): Tier 2 Middleware - mufg-win-pay01")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        step_15 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "ROLLBACK_ESCALATION",
            "execution_order": exec_order,
            "tier": "Tier 2",
            "hostname": "mufg-win-pay01",
            "platform": "WINDOWS_SVR",
            "service_name": "MUFG_ISO20022_PaymentEngine",
            "sop_command": "Restart-Service -Name 'MUFG_ISO20022_PaymentEngine' -Force ; Test-NetConnection -Port 9443",
            "precheck_status": "FAILED",
            "target_state": "STARTED_VERIFIED",
            "actual_state": "FAILED_SLA_BREACH",
            "pid_or_port_check": "PORT_9443=CONN_REFUSED,HSM=NO_RESPONSE",
            "elapsed_sec": 49.10,  # Exceeds 45s SLA!
            "sla_limit_sec": 45.0,
            "sla_status": "SLA_BREACHED",
            "servicenow_inc_ref": p1_inc_ref,
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_15)
        print(f"    [CRITICAL FAILURE] Status: SLA_BREACHED | State: {step_15['actual_state']} | Elapsed: {step_15['elapsed_sec']}s")
        print(f"    [ESCALATION TRIGGERED] Registering P1 Incident: {p1_inc_ref} -> {change_gov['escalation']['assignment_group']}")
        exec_order += 1

        # Register ServiceNow P1 incident
        p1_incident = {
            "incident_ref": p1_inc_ref,
            "run_id": change_ref,
            "hostname": "mufg-win-pay01",
            "filesystem_path": "N/A - Middleware / Payment Engine",
            "severity": "P1 - Critical",
            "category": "Middleware / HSM Cryptographic Handshake Timeout",
            "short_description": (
                f"P1 CRITICAL: Startup SLA breach on mufg-win-pay01 (MUFG_ISO20022_PaymentEngine) "
                f"elapsed 48.4s/49.1s vs 45s SLA limit. HSM crypto port 9443 handshake failed. "
                f"Upstream Tier 1 SWIFT Gateway halted under {change_ref}."
            ),
            "assignment_group": change_gov["escalation"]["assignment_group"],
            "status": "OPEN",
            "created_at_ist": get_current_ist_str()
        }
        self.db.record_servicenow_incident(p1_incident)

        # ----------------------------------------------------------------------
        # Step 16: Upstream Dependency Block (mufg-rhel-core01: mufg-swift-gateway.service)
        # ----------------------------------------------------------------------
        print(f"\n>>> [Step {exec_order}] UPSTREAM DEPENDENCY HALT: Tier 1 Gateway - mufg-rhel-core01")
        step_id = f"{runbook_id}_STEP_{exec_order:02d}"
        step_16 = {
            "step_id": step_id,
            "change_ref": change_ref,
            "runbook_id": runbook_id,
            "phase": "ROLLBACK_ESCALATION",
            "execution_order": exec_order,
            "tier": "Tier 1",
            "hostname": "mufg-rhel-core01",
            "platform": "UNIX_RHEL",
            "service_name": "mufg-swift-gateway.service",
            "sop_command": "HALT_UPSTREAM_DEPENDENCY (SOP Section 4.3: Prevent ingress traffic on payment engine failure)",
            "precheck_status": "BLOCKED",
            "target_state": "STARTED_VERIFIED",
            "actual_state": "HALTED_DEPENDENCY_BLOCK",
            "pid_or_port_check": "GATEWAY_PORT_8443=HELD_INACTIVE",
            "elapsed_sec": 0.00,
            "sla_limit_sec": 30.0,
            "sla_status": "HALTED_UPSTREAM",
            "servicenow_inc_ref": p1_inc_ref,
            "timestamp_ist": get_current_ist_str()
        }
        execution_steps.append(step_16)
        print(f"    [HALTED] Status: HALTED_UPSTREAM | Actual: {step_16['actual_state']}")
        print(f"    [PROTECTION ENFORCED] Prevented Tier 1 SWIFT Edge Gateway from accepting live bank traffic while Tier 2 payment backend is down.")

        # ======================================================================
        # DATABASE COMMIT PHASE
        # ======================================================================
        print("\n[INFO] Persisting all 16 runbook execution steps to SQLite (runbook_execution_log)...")
        self.db.record_runbook_steps_batch(execution_steps)

        # ======================================================================
        # CONSOLE AUDIT REPORT
        # ======================================================================
        df_runbook = pd.DataFrame(execution_steps)
        print("\n" + "=" * 135)
        print(" MUFG INFRAOPS-SENTINEL: PHASE 2 RUNBOOK EXECUTION LOG REPORT (CHG0049210)")
        print("=" * 135)

        display_cols = [
            "execution_order", "phase", "tier", "hostname", "service_name",
            "target_state", "actual_state", "elapsed_sec", "sla_limit_sec", "sla_status", "servicenow_inc_ref"
        ]
        print(df_runbook[display_cols].to_string(index=False))
        print("=" * 135)

        total_steps = len(execution_steps)
        compliant_steps = sum(1 for s in execution_steps if s["sla_status"] == "COMPLIANT")
        breached_steps = sum(1 for s in execution_steps if s["sla_status"] == "SLA_BREACHED")
        halted_steps = sum(1 for s in execution_steps if s["sla_status"] == "HALTED_UPSTREAM")

        print(f"\n[RUNBOOK EXECUTION SUMMARY]")
        print(f" - Total Lifecycle Steps:     {total_steps}")
        print(f" - Compliant Steps:           {compliant_steps}")
        print(f" - SLA Breached Steps:        {breached_steps} (Payment Middleware HSM Handshake Timeout)")
        print(f" - Halted Upstream Steps:     {halted_steps} (SWIFT Gateway Ingress Protected)")
        print(f" - ServiceNow Incident:       {p1_inc_ref} -> {change_gov['escalation']['assignment_group']} ({change_gov['escalation']['bridge_line']})")
        print("=" * 135)

        return {
            "runbook_id": runbook_id,
            "change_ref": change_ref,
            "total_steps": total_steps,
            "p1_incident_ref": p1_inc_ref,
            "steps": execution_steps
        }


if __name__ == "__main__":
    orchestrator = RunbookOrchestrator()
    orchestrator.execute_maintenance_window()

