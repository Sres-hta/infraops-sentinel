"""
MUFG Bank, Ltd. - Operations Infrastructure & Systems Management
Project: InfraOps-Sentinel (Phase 1: Automated Housekeeping Engine)
Module:  housekeeping_engine.py
Purpose: Cross-platform housekeeping orchestrator across Unix RHEL, Windows Server,
         and AS400 / IBM iSeries banking systems. Computes reclaimed deltas,
         enforces Active File Protection, evaluates SLA compliance, generates
         ServiceNow P2 incident escalations, and persists audit ledgers to SQLite.
"""

import json
import os
import sys
import subprocess
import hashlib
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Tuple
import pandas as pd

# Setup project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.db_manager import SentinelDBManager
except ImportError:
    from db_manager import SentinelDBManager


# Setup project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "housekeeping_policy.json"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DATA_DIR = PROJECT_ROOT / "data"
SANDBOX_DIR = PROJECT_ROOT / "sandbox_fs"

# Timezone helper for IST (Asia/Kolkata +05:30)
IST = timezone(timedelta(hours=5, minutes=30))


def get_current_ist_str() -> str:
    """Returns current timestamp formatted in IST standard."""
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")


class HousekeepingEngine:
    """Multi-platform housekeeping and storage governance orchestrator."""

    def __init__(self, config_path: Path = CONFIG_PATH):
        self.config_path = config_path
        self.policy = self._load_policy()
        self.db = SentinelDBManager()

    def _load_policy(self) -> Dict[str, Any]:
        """Loads SLA and retention thresholds from configuration JSON."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def execute_unix_node(
        self,
        run_id: str,
        hostname: str,
        target_subpath: str,
        display_mount: str,
        capacity_mb: float,
        base_used_mb: float
    ) -> Dict[str, Any]:
        """Invokes scripts/unix_housekeeping.sh to perform real RHEL housekeeping."""
        target_dir = SANDBOX_DIR / target_subpath
        target_dir.mkdir(parents=True, exist_ok=True)

        telemetry_json = DATA_DIR / f"telemetry_{hostname}_{run_id}.json"
        ledger_csv = DATA_DIR / f"ledger_{hostname}_{run_id}.csv"
        script_path = SCRIPTS_DIR / "unix_housekeeping.sh"

        cmd = [
            "bash",
            str(script_path),
            "--target-dir", str(target_dir),
            "--run-id", run_id,
            "--hostname", hostname,
            "--output-json", str(telemetry_json),
            "--output-csv", str(ledger_csv),
            "--capacity-mb", str(capacity_mb),
            "--base-used-mb", str(base_used_mb),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"unix_housekeeping.sh failed on {hostname}: {result.stderr}")

        if not telemetry_json.exists():
            raise FileNotFoundError(f"Expected telemetry output missing: {telemetry_json}")

        with open(telemetry_json, "r", encoding="utf-8") as f:
            telemetry = json.load(f)

        # Replace sandbox path with display banking mount for audit log clarity
        telemetry["filesystem_path"] = display_mount

        # Read ledger CSV and convert to file action items
        ledger_items = []
        if ledger_csv.exists():
            df_ledger = pd.read_csv(ledger_csv)
            for _, row in df_ledger.iterrows():
                ledger_items.append({
                    "run_id": run_id,
                    "file_path": str(row["file_path"]),
                    "file_age_days": int(row["file_age_days"]),
                    "action_taken": str(row["action_taken"]),
                    "size_kb": float(row["size_kb"]),
                    "timestamp_ist": str(row["timestamp_ist"])
                })

        return {
            "telemetry": telemetry,
            "ledger_items": ledger_items
        }

    def execute_windows_node(
        self,
        run_id: str,
        hostname: str,
        target_subpath: str,
        display_mount: str,
        capacity_mb: float,
        base_used_mb: float,
        purge_age_days: int = 3,
        force_critical_breach: bool = False
    ) -> Dict[str, Any]:
        """Executes Windows Server housekeeping on mock directory with banking governance rules."""
        target_dir = SANDBOX_DIR / target_subpath
        target_dir.mkdir(parents=True, exist_ok=True)

        now_epoch = time.time()
        timestamp_ist = get_current_ist_str()

        # Measure directory size before
        before_bytes = sum(f.stat().st_size for f in target_dir.rglob("*") if f.is_file())
        before_dir_mb = before_bytes / (1024 * 1024)

        total_used_before_mb = base_used_mb + before_dir_mb
        before_used_pct = round((total_used_before_mb / capacity_mb) * 100, 1)

        ledger_items = []
        files_purged = 0
        files_compressed = 0
        files_skipped = 0

        # Process each file
        for file_path in sorted(target_dir.rglob("*")):
            if not file_path.is_file():
                continue

            stat_res = file_path.stat()
            file_bytes = stat_res.st_size
            file_kb = round(file_bytes / 1024, 1)
            age_days = max(0, int((now_epoch - stat_res.st_mtime) / 86400))

            # Active file protection rule (<= 1 day)
            if age_days <= 1:
                action = "SKIPPED_ACTIVE"
                files_skipped += 1
            elif file_path.suffix.lower() in [".tmp", ".dmp", ".bak"] and age_days > purge_age_days:
                # Purge expired dump or scratch files
                file_path.unlink()
                action = "PURGED_RETENTION"
                files_purged += 1
            else:
                action = "SKIPPED_ACTIVE"
                files_skipped += 1

            ledger_items.append({
                "run_id": run_id,
                "file_path": str(file_path).replace(str(SANDBOX_DIR), display_mount),
                "file_age_days": age_days,
                "action_taken": action,
                "size_kb": file_kb,
                "timestamp_ist": timestamp_ist
            })

        after_bytes = sum(f.stat().st_size for f in target_dir.rglob("*") if f.is_file())
        after_dir_mb = after_bytes / (1024 * 1024)
        space_reclaimed_mb = round((before_bytes - after_bytes) / (1024 * 1024), 2)

        total_used_after_mb = base_used_mb + after_dir_mb
        after_used_pct = round((total_used_after_mb / capacity_mb) * 100, 1)

        # Handle threshold breach check
        warn_thresh = self.policy["sla_thresholds"]["disk_warning_pct"]
        crit_thresh = self.policy["sla_thresholds"]["disk_critical_pct"]

        sla_status = "COMPLIANT"
        servicenow_inc_ref = ""
        incident_record = None

        if after_used_pct >= crit_thresh or force_critical_breach:
            sla_status = "CRITICAL_ESCALATED"
            inc_prefix = self.policy["sla_thresholds"]["escalation"]["servicenow_incident_prefix"]
            servicenow_inc_ref = f"{inc_prefix}4821"
            incident_record = {
                "incident_ref": servicenow_inc_ref,
                "run_id": run_id,
                "hostname": hostname,
                "filesystem_path": display_mount,
                "severity": "P2 - High",
                "category": "Storage / Filesystem Threshold Breach",
                "short_description": (
                    f"CRITICAL: Mount {display_mount} on {hostname} remains at {after_used_pct}% "
                    f"post-housekeeping (Critical SLA: {crit_thresh}%). Immediate L2 action required."
                ),
                "assignment_group": self.policy["sla_thresholds"]["escalation"]["servicenow_assignment_group"],
                "status": "OPEN",
                "created_at_ist": timestamp_ist
            }
        elif after_used_pct >= warn_thresh:
            sla_status = "WARNING"

        # Manifest hash computation
        manifest_raw = "".join(f"{it['file_path']}:{it['action_taken']}" for it in ledger_items)
        sha256_hash = hashlib.sha256(manifest_raw.encode("utf-8")).hexdigest()

        telemetry = {
            "run_id": run_id,
            "timestamp_ist": timestamp_ist,
            "hostname": hostname,
            "platform": "WINDOWS_SVR",
            "filesystem_path": display_mount,
            "before_used_pct": before_used_pct,
            "after_used_pct": after_used_pct,
            "inodes_used_pct": 34.2,  # MFT usage equivalent on Windows
            "files_compressed": files_compressed,
            "files_purged": files_purged,
            "files_skipped": files_skipped,
            "space_reclaimed_mb": space_reclaimed_mb,
            "sha256_manifest_hash": sha256_hash,
            "sla_status": sla_status,
            "servicenow_inc_ref": servicenow_inc_ref
        }

        return {
            "telemetry": telemetry,
            "ledger_items": ledger_items,
            "incident_record": incident_record
        }

    def execute_as400_node(
        self,
        run_id: str,
        hostname: str,
        target_subpath: str,
        display_mount: str,
        capacity_mb: float,
        base_used_mb: float,
        spool_archive_days: int = 14,
        joblog_purge_days: int = 30,
        force_critical_breach: bool = False
    ) -> Dict[str, Any]:
        """Executes AS400 / IBM iSeries spool archiving & joblog purge on mock directory."""
        target_dir = SANDBOX_DIR / target_subpath
        target_dir.mkdir(parents=True, exist_ok=True)

        now_epoch = time.time()
        timestamp_ist = get_current_ist_str()

        before_bytes = sum(f.stat().st_size for f in target_dir.rglob("*") if f.is_file())
        before_dir_mb = before_bytes / (1024 * 1024)

        total_used_before_mb = base_used_mb + before_dir_mb
        before_used_pct = round((total_used_before_mb / capacity_mb) * 100, 1)

        ledger_items = []
        files_purged = 0
        files_compressed = 0
        files_skipped = 0

        for file_path in sorted(target_dir.rglob("*")):
            if not file_path.is_file():
                continue

            stat_res = file_path.stat()
            file_bytes = stat_res.st_size
            file_kb = round(file_bytes / 1024, 1)
            age_days = max(0, int((now_epoch - stat_res.st_mtime) / 86400))
            filename = file_path.name

            # Active file protection (<= 1 day)
            if age_days <= 1:
                action = "SKIPPED_ACTIVE"
                files_skipped += 1
            elif (filename.startswith("JOBLOG_") or file_path.suffix.upper() == ".LOG") and age_days > joblog_purge_days:
                # Expired joblogs older than 30 days are purged
                file_path.unlink()
                action = "PURGED_RETENTION"
                files_purged += 1
            elif (filename.startswith("SPL_") or file_path.suffix.upper() == ".SPL") and age_days > spool_archive_days:
                # Spool files older than 14 days are compressed/archived
                subprocess.run(["gzip", "-f", str(file_path)], check=True)
                action = "COMPRESSED_GZ"
                files_compressed += 1
            else:
                action = "SKIPPED_ACTIVE"
                files_skipped += 1

            ledger_items.append({
                "run_id": run_id,
                "file_path": str(file_path).replace(str(SANDBOX_DIR), display_mount),
                "file_age_days": age_days,
                "action_taken": action,
                "size_kb": file_kb,
                "timestamp_ist": timestamp_ist
            })

        after_bytes = sum(f.stat().st_size for f in target_dir.rglob("*") if f.is_file())
        after_dir_mb = after_bytes / (1024 * 1024)
        space_reclaimed_mb = round((before_bytes - after_bytes) / (1024 * 1024), 2)

        total_used_after_mb = base_used_mb + after_dir_mb
        after_used_pct = round((total_used_after_mb / capacity_mb) * 100, 1)

        crit_thresh = self.policy["sla_thresholds"]["disk_critical_pct"]
        warn_thresh = self.policy["sla_thresholds"]["disk_warning_pct"]

        sla_status = "COMPLIANT"
        servicenow_inc_ref = ""
        incident_record = None

        if after_used_pct >= crit_thresh or force_critical_breach:
            sla_status = "CRITICAL_ESCALATED"
            inc_prefix = self.policy["sla_thresholds"]["escalation"]["servicenow_incident_prefix"]
            servicenow_inc_ref = f"{inc_prefix}4822"
            incident_record = {
                "incident_ref": servicenow_inc_ref,
                "run_id": run_id,
                "hostname": hostname,
                "filesystem_path": display_mount,
                "severity": "P2 - High",
                "category": "AS400 Auxiliary Storage Pool (ASP) Threshold Breach",
                "short_description": (
                    f"CRITICAL: System ASP {display_mount} on {hostname} remains at {after_used_pct}% "
                    f"post-housekeeping (Critical SLA: {crit_thresh}%). Unattached journal receiver cleanup required."
                ),
                "assignment_group": self.policy["sla_thresholds"]["escalation"]["servicenow_assignment_group"],
                "status": "OPEN",
                "created_at_ist": timestamp_ist
            }
        elif after_used_pct >= warn_thresh:
            sla_status = "WARNING"

        manifest_raw = "".join(f"{it['file_path']}:{it['action_taken']}" for it in ledger_items)
        sha256_hash = hashlib.sha256(manifest_raw.encode("utf-8")).hexdigest()

        telemetry = {
            "run_id": run_id,
            "timestamp_ist": timestamp_ist,
            "hostname": hostname,
            "platform": "AS400_ISERIES",
            "filesystem_path": display_mount,
            "before_used_pct": before_used_pct,
            "after_used_pct": after_used_pct,
            "inodes_used_pct": 41.5,  # System ASP directory count equivalent
            "files_compressed": files_compressed,
            "files_purged": files_purged,
            "files_skipped": files_skipped,
            "space_reclaimed_mb": space_reclaimed_mb,
            "sha256_manifest_hash": sha256_hash,
            "sla_status": sla_status,
            "servicenow_inc_ref": servicenow_inc_ref
        }

        return {
            "telemetry": telemetry,
            "ledger_items": ledger_items,
            "incident_record": incident_record
        }

    def run_full_orchestration(self) -> Dict[str, Any]:
        """Runs automated housekeeping across Unix, Windows, and AS400 nodes."""
        run_id = f"HKP_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        start_time_ist = get_current_ist_str()

        print("=" * 80)
        print(" MUFG BANK - INFRAOPS-SENTINEL: AUTOMATED MULTI-PLATFORM HOUSEKEEPING")
        print(f" Run ID:             {run_id}")
        print(f" Execution Started:  {start_time_ist}")
        print(f" Target Inventory:   6 Enterprise Banking Nodes (Unix RHEL, Windows, AS400)")
        print("=" * 80)

        # Ensure sandbox is populated if missing
        if not SANDBOX_DIR.exists() or not any(SANDBOX_DIR.iterdir()):
            print("[INFO] Mock filesystem sandbox missing. Running seed_mock_filesystem.sh...")
            subprocess.run(["bash", str(SCRIPTS_DIR / "seed_mock_filesystem.sh")], check=True)

        audit_results = []
        all_ledger_items = []
        incident_records = []

        # ----------------------------------------------------------------------
        # NODE 1: Unix RHEL Core Banking (/var/log/mufg_app)
        # ----------------------------------------------------------------------
        print("\n>>> [1/6] Executing Housekeeping: mufg-rhel-core01 (UNIX_RHEL)")
        res_rhel1 = self.execute_unix_node(
            run_id=run_id,
            hostname="mufg-rhel-core01",
            target_subpath="var/log/mufg_app",
            display_mount="/var/log/mufg_app",
            capacity_mb=60.0,
            base_used_mb=36.0
        )
        audit_results.append(res_rhel1["telemetry"])
        all_ledger_items.extend(res_rhel1["ledger_items"])

        # ----------------------------------------------------------------------
        # NODE 2: Unix RHEL Batch Settlement (/var/log/mufg_batch)
        # ----------------------------------------------------------------------
        print("\n>>> [2/6] Executing Housekeeping: mufg-rhel-batch02 (UNIX_RHEL)")
        res_rhel2 = self.execute_unix_node(
            run_id=run_id,
            hostname="mufg-rhel-batch02",
            target_subpath="var/log/mufg_batch",
            display_mount="/var/log/mufg_batch",
            capacity_mb=25.0,
            base_used_mb=17.5
        )
        audit_results.append(res_rhel2["telemetry"])
        all_ledger_items.extend(res_rhel2["ledger_items"])

        # ----------------------------------------------------------------------
        # NODE 3: Windows Server Application Pool (C:\Temp\Dump)
        # ----------------------------------------------------------------------
        print("\n>>> [3/6] Executing Housekeeping: mufg-win-app01 (WINDOWS_SVR)")
        res_win1 = self.execute_windows_node(
            run_id=run_id,
            hostname="mufg-win-app01",
            target_subpath="win_temp_dump/C_Temp_Dump",
            display_mount="C:\\Temp\\Dump",
            capacity_mb=50.0,
            base_used_mb=32.0,
            purge_age_days=3,
            force_critical_breach=False
        )
        audit_results.append(res_win1["telemetry"])
        all_ledger_items.extend(res_win1["ledger_items"])
        if res_win1.get("incident_record"):
            incident_records.append(res_win1["incident_record"])

        # ----------------------------------------------------------------------
        # NODE 4: Windows Server High-Volume Payment DB (D:\SQLData) - Critical Escalation!
        # ----------------------------------------------------------------------
        print("\n>>> [4/6] Executing Housekeeping: mufg-win-pay01 (WINDOWS_SVR)")
        res_win2 = self.execute_windows_node(
            run_id=run_id,
            hostname="mufg-win-pay01",
            target_subpath="win_temp_dump/D_SQLData",
            display_mount="D:\\SQLData",
            capacity_mb=100.0,
            base_used_mb=64.7,  # Simulates 89.2% before -> 88.2% after (exceeds 85% SLA)
            purge_age_days=3,
            force_critical_breach=False
        )
        audit_results.append(res_win2["telemetry"])
        all_ledger_items.extend(res_win2["ledger_items"])
        if res_win2.get("incident_record"):
            incident_records.append(res_win2["incident_record"])

        # ----------------------------------------------------------------------
        # NODE 5: AS400 / IBM iSeries Spool Queues (QSYSPRT)
        # ----------------------------------------------------------------------
        print("\n>>> [5/6] Executing Housekeeping: mufg-as400-core01 (AS400_ISERIES)")
        res_as400_1 = self.execute_as400_node(
            run_id=run_id,
            hostname="mufg-as400-core01",
            target_subpath="as400_qsysprt/QSYSPRT",
            display_mount="/QSYS.LIB/QUSRSYS.LIB/QSYSPRT.OUTQ",
            capacity_mb=45.0,
            base_used_mb=28.0,
            spool_archive_days=14,
            joblog_purge_days=30,
            force_critical_breach=False
        )
        audit_results.append(res_as400_1["telemetry"])
        all_ledger_items.extend(res_as400_1["ledger_items"])
        if res_as400_1.get("incident_record"):
            incident_records.append(res_as400_1["incident_record"])

        # ----------------------------------------------------------------------
        # NODE 6: AS400 / IBM iSeries Production ASP (/QSYS.LIB) - Critical Escalation!
        # ----------------------------------------------------------------------
        print("\n>>> [6/6] Executing Housekeeping: mufg-as400-prd02 (AS400_ISERIES)")
        res_as400_2 = self.execute_as400_node(
            run_id=run_id,
            hostname="mufg-as400-prd02",
            target_subpath="as400_qsysprt/QSYS_LIB",
            display_mount="/QSYS.LIB",
            capacity_mb=100.0,
            base_used_mb=69.0,  # Heavy journal receiver consumption: 91.5% (exceeds 85% SLA)
            spool_archive_days=14,
            joblog_purge_days=30,
            force_critical_breach=False
        )
        audit_results.append(res_as400_2["telemetry"])
        all_ledger_items.extend(res_as400_2["ledger_items"])
        if res_as400_2.get("incident_record"):
            incident_records.append(res_as400_2["incident_record"])

        # ----------------------------------------------------------------------
        # DATABASE COMMIT PHASE
        # ----------------------------------------------------------------------
        print("\n[INFO] Persisting audit records into SQLite database...")
        for audit in audit_results:
            self.db.record_housekeeping_audit(audit)

        print(f"[INFO] Logging {len(all_ledger_items)} individual file actions to ledger...")
        self.db.record_file_actions(all_ledger_items)

        for inc in incident_records:
            print(f"[ESCALATION] Registering ServiceNow ticket: {inc['incident_ref']} -> {inc['assignment_group']}")
            self.db.record_servicenow_incident(inc)

        # ----------------------------------------------------------------------
        # EXECUTIVE TELEMETRY CONSOLE REPORT
        # ----------------------------------------------------------------------
        df_summary = pd.DataFrame(audit_results)
        print("\n" + "=" * 110)
        print(" MUFG INFRAOPS-SENTINEL: PHASE 1 MULTI-PLATFORM HOUSEKEEPING AUDIT REPORT")
        print("=" * 110)
        
        display_cols = [
            "hostname", "platform", "filesystem_path",
            "before_used_pct", "after_used_pct", "inodes_used_pct",
            "files_compressed", "files_purged", "files_skipped",
            "space_reclaimed_mb", "sla_status", "servicenow_inc_ref"
        ]
        print(df_summary[display_cols].to_string(index=False))
        print("=" * 110)

        # Summary Metrics
        total_compressed = sum(r["files_compressed"] for r in audit_results)
        total_purged = sum(r["files_purged"] for r in audit_results)
        total_skipped = sum(r["files_skipped"] for r in audit_results)
        total_reclaimed = round(sum(r["space_reclaimed_mb"] for r in audit_results), 2)
        critical_count = sum(1 for r in audit_results if r["sla_status"] == "CRITICAL_ESCALATED")

        print(f"\n[SUMMARY STATS]")
        print(f" - Total Nodes Audited:     {len(audit_results)}")
        print(f" - Total Storage Reclaimed: {total_reclaimed} MB")
        print(f" - Files Compressed (.gz):  {total_compressed}")
        print(f" - Files Purged:            {total_purged}")
        print(f" - Files Skipped (Active):  {total_skipped}")
        print(f" - SLA Critical Breaches:   {critical_count}")
        print(f" - Active ServiceNow Inc:   {len(incident_records)}")
        print("=" * 110)

        return {
            "run_id": run_id,
            "timestamp_ist": start_time_ist,
            "total_nodes": len(audit_results),
            "total_reclaimed_mb": total_reclaimed,
            "total_compressed": total_compressed,
            "total_purged": total_purged,
            "total_skipped": total_skipped,
            "audit_records": audit_results,
            "incident_records": incident_records
        }


if __name__ == "__main__":
    engine = HousekeepingEngine()
    engine.run_full_orchestration()
