"""
MUFG Bank, Ltd. - Operations Infrastructure & Systems Management
Project: InfraOps-Sentinel (Automated Housekeeping & Runbook Orchestrator)
Module:  db_manager.py
Purpose: SQLite Database Manager for audit logging, action ledger,
         ServiceNow escalation tracking, and Phase 2/3 forward compatibility.
"""

import sqlite3
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import pandas as pd


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "infraops_sentinel.db"


class SentinelDBManager:
    """Manages SQLite operations for InfraOps-Sentinel with strict banking audit compliance."""

    def __init__(self, db_path: Optional[str or Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Returns SQLite connection with row factory configured."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_schema(self) -> None:
        """Initializes database schema with Phase 1 tables and forward compatibility for Phase 2 & 3."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Housekeeping Audit Log (Phase 1)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS housekeeping_audit_log (
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
            """)

            # 2. File Action Ledger (Phase 1)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_action_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_age_days INTEGER NOT NULL,
                action_taken TEXT NOT NULL CHECK(action_taken IN ('COMPRESSED_GZ', 'PURGED_RETENTION', 'SKIPPED_ACTIVE')),
                size_kb REAL NOT NULL,
                timestamp_ist TEXT NOT NULL
            );
            """)

            # 3. ServiceNow Incident Tracking (Phase 1 escalation)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS servicenow_incidents (
                incident_ref TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                hostname TEXT NOT NULL,
                filesystem_path TEXT NOT NULL,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                short_description TEXT NOT NULL,
                assignment_group TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                created_at_ist TEXT NOT NULL
            );
            """)

            # Check if runbook_execution_log needs migration to Phase 2 schema
            cursor.execute("PRAGMA table_info(runbook_execution_log);")
            existing_cols = [c[1] for c in cursor.fetchall()]
            if "step_id" not in existing_cols:
                cursor.execute("DROP TABLE IF EXISTS runbook_execution_log;")

            # 4. Runbook Execution Log (Phase 2)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS runbook_execution_log (
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
            """)

            # 5. Daily Check-Sheet Manifest (Forward compatibility for Phase 3)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_checksheet_manifest (
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
            """)

            # Create indexing for rapid queries and reporting
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_run_id ON housekeeping_audit_log(run_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_platform ON housekeeping_audit_log(platform);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_sla ON housekeeping_audit_log(sla_status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_run_id ON file_action_ledger(run_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ledger_action ON file_action_ledger(action_taken);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runbook_order ON runbook_execution_log(execution_order);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runbook_change ON runbook_execution_log(change_ref);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_runbook_phase ON runbook_execution_log(phase);")

            conn.commit()

    def record_housekeeping_audit(self, audit_data: Dict[str, Any]) -> None:
        """Records a single node housekeeping audit row."""
        sql = """
        INSERT OR REPLACE INTO housekeeping_audit_log (
            run_id, timestamp_ist, hostname, platform, filesystem_path,
            before_used_pct, after_used_pct, inodes_used_pct,
            files_compressed, files_purged, files_skipped, space_reclaimed_mb,
            sha256_manifest_hash, sla_status, servicenow_inc_ref
        ) VALUES (
            :run_id, :timestamp_ist, :hostname, :platform, :filesystem_path,
            :before_used_pct, :after_used_pct, :inodes_used_pct,
            :files_compressed, :files_purged, :files_skipped, :space_reclaimed_mb,
            :sha256_manifest_hash, :sla_status, :servicenow_inc_ref
        );
        """
        with self.get_connection() as conn:
            conn.execute(sql, audit_data)
            conn.commit()

    def record_file_actions(self, actions: List[Dict[str, Any]]) -> None:
        """Batch inserts individual file actions into the ledger."""
        if not actions:
            return
        sql = """
        INSERT INTO file_action_ledger (
            run_id, file_path, file_age_days, action_taken, size_kb, timestamp_ist
        ) VALUES (
            :run_id, :file_path, :file_age_days, :action_taken, :size_kb, :timestamp_ist
        );
        """
        with self.get_connection() as conn:
            conn.executemany(sql, actions)
            conn.commit()

    def record_servicenow_incident(self, inc_data: Dict[str, Any]) -> None:
        """Records a ServiceNow P2 escalation ticket."""
        sql = """
        INSERT OR REPLACE INTO servicenow_incidents (
            incident_ref, run_id, hostname, filesystem_path,
            severity, category, short_description, assignment_group, status, created_at_ist
        ) VALUES (
            :incident_ref, :run_id, :hostname, :filesystem_path,
            :severity, :category, :short_description, :assignment_group, :status, :created_at_ist
        );
        """
        with self.get_connection() as conn:
            conn.execute(sql, inc_data)
            conn.commit()

    def get_audit_dataframe(self, run_id: Optional[str] = None) -> pd.DataFrame:
        """Fetches audit logs as a pandas DataFrame."""
        with self.get_connection() as conn:
            if run_id:
                query = "SELECT * FROM housekeeping_audit_log WHERE run_id = ? ORDER BY platform, hostname"
                return pd.read_sql_query(query, conn, params=(run_id,))
            query = "SELECT * FROM housekeeping_audit_log ORDER BY timestamp_ist DESC, platform, hostname"
            return pd.read_sql_query(query, conn)

    def get_action_ledger_dataframe(self, run_id: Optional[str] = None) -> pd.DataFrame:
        """Fetches action ledger entries as a pandas DataFrame."""
        with self.get_connection() as conn:
            if run_id:
                query = "SELECT * FROM file_action_ledger WHERE run_id = ? ORDER BY id"
                return pd.read_sql_query(query, conn, params=(run_id,))
            query = "SELECT * FROM file_action_ledger ORDER BY id"
            return pd.read_sql_query(query, conn)

    def get_incidents_dataframe(self, run_id: Optional[str] = None) -> pd.DataFrame:
        """Fetches generated ServiceNow incidents."""
        with self.get_connection() as conn:
            if run_id:
                query = "SELECT * FROM servicenow_incidents WHERE run_id = ? ORDER BY incident_ref"
                return pd.read_sql_query(query, conn, params=(run_id,))
            query = "SELECT * FROM servicenow_incidents ORDER BY incident_ref"
            return pd.read_sql_query(query, conn)

    def record_runbook_step(self, step_data: Dict[str, Any]) -> None:
        """Records a single runbook execution step."""
        sql = """
        INSERT OR REPLACE INTO runbook_execution_log (
            step_id, change_ref, runbook_id, phase, execution_order,
            tier, hostname, platform, service_name, sop_command,
            precheck_status, target_state, actual_state, pid_or_port_check,
            elapsed_sec, sla_limit_sec, sla_status, servicenow_inc_ref, timestamp_ist
        ) VALUES (
            :step_id, :change_ref, :runbook_id, :phase, :execution_order,
            :tier, :hostname, :platform, :service_name, :sop_command,
            :precheck_status, :target_state, :actual_state, :pid_or_port_check,
            :elapsed_sec, :sla_limit_sec, :sla_status, :servicenow_inc_ref, :timestamp_ist
        );
        """
        with self.get_connection() as conn:
            conn.execute(sql, step_data)
            conn.commit()

    def record_runbook_steps_batch(self, steps: List[Dict[str, Any]]) -> None:
        """Batch inserts runbook execution steps into the database."""
        if not steps:
            return
        sql = """
        INSERT OR REPLACE INTO runbook_execution_log (
            step_id, change_ref, runbook_id, phase, execution_order,
            tier, hostname, platform, service_name, sop_command,
            precheck_status, target_state, actual_state, pid_or_port_check,
            elapsed_sec, sla_limit_sec, sla_status, servicenow_inc_ref, timestamp_ist
        ) VALUES (
            :step_id, :change_ref, :runbook_id, :phase, :execution_order,
            :tier, :hostname, :platform, :service_name, :sop_command,
            :precheck_status, :target_state, :actual_state, :pid_or_port_check,
            :elapsed_sec, :sla_limit_sec, :sla_status, :servicenow_inc_ref, :timestamp_ist
        );
        """
        with self.get_connection() as conn:
            conn.executemany(sql, steps)
            conn.commit()

    def get_runbook_execution_dataframe(self, runbook_id: Optional[str] = None) -> pd.DataFrame:
        """Fetches runbook execution steps as a pandas DataFrame."""
        with self.get_connection() as conn:
            if runbook_id:
                query = "SELECT * FROM runbook_execution_log WHERE runbook_id = ? ORDER BY execution_order"
                return pd.read_sql_query(query, conn, params=(runbook_id,))
            query = "SELECT * FROM runbook_execution_log ORDER BY execution_order"
            return pd.read_sql_query(query, conn)

    def record_checksheet_manifest(self, manifest_data: Dict[str, Any]) -> None:
        """Records daily checksheet manifest metadata."""
        sql = """
        INSERT OR REPLACE INTO daily_checksheet_manifest (
            sheet_id, report_date, shift, total_systems_checked,
            healthy_count, warning_count, critical_count,
            excel_file_path, pdf_file_path, generated_at_ist, approved_by
        ) VALUES (
            :sheet_id, :report_date, :shift, :total_systems_checked,
            :healthy_count, :warning_count, :critical_count,
            :excel_file_path, :pdf_file_path, :generated_at_ist, :approved_by
        );
        """
        with self.get_connection() as conn:
            conn.execute(sql, manifest_data)
            conn.commit()

    def get_checksheet_manifest_dataframe(self) -> pd.DataFrame:
        """Fetches checksheet manifests as a pandas DataFrame."""
        with self.get_connection() as conn:
            return pd.read_sql_query("SELECT * FROM daily_checksheet_manifest ORDER BY id DESC", conn)


if __name__ == "__main__":
    db = SentinelDBManager()
    print(f"[INFO] Database initialized successfully at: {db.db_path}")
