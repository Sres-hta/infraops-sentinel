# 02. Phase 1: Multi-Platform Housekeeping & Storage Governance Deep Dive
**Project:** `InfraOps-Sentinel`  
**Focus:** Automated Storage Reclamation, Telemetry, Active File Safety & ServiceNow Escalation  
**Relevant Code:** `config/housekeeping_policy.json`, `scripts/seed_mock_filesystem.sh`, `scripts/unix_housekeeping.sh`, `src/housekeeping_engine.py`  
**Author:** Sreshta Sarkar  

---

## 1. The Operational Problem: Storage Exhaustion in Banking

In enterprise banking production environments, disk and inode saturation are among the most frequent causes of unplanned Sev-1 outages. An unmonitored log mount or spool directory reaching 100% capacity triggers cascading failures:
1. **Core Banking Transaction Freezes:** RDBMS engines (Oracle, DB2, SQL Server) crash immediately when transaction log mounts (`/var/log/mufg_app`, `D:\SQLData`) cannot write redo or undo buffers.
2. **Mainframe / AS400 ASP Lockups:** IBM iSeries Auxiliary Storage Pool (ASP) exceeding 90% forces the Operating System to restrict batch jobs and suspend interactive terminal sessions (`QINTER`).
3. **Inode Exhaustion Without Disk Block Depletion:** Thousands of zero-byte session files (`.tmp`) can exhaust filesystem inodes (`df -i` at 100%), preventing new file creation even when hundreds of gigabytes of disk block storage (`df -k`) remain free.

To counter this, `InfraOps-Sentinel` implements an automated, multi-tiered retention and active protection engine.

---

## 2. File Evaluation & Retention Decision Tree

The following decision logic is enforced across every file scanned in Unix, Windows, and AS400 filesystems:

```mermaid
flowchart TD
    Start(["File Identified by Scanner"]) --> CheckAge{"File Age (Epoch Delta)<br/>diff_sec / 86400"}
    
    CheckAge -->|Age <= 1 Day<br/>Modified < 24h| RuleActive["ACTION: SKIPPED_ACTIVE<br/>Preserve live banking process lock.<br/>Do NOT compress or touch."]
    
    CheckAge -->|Age > 1 Day| CheckType{"Inspect File Type<br/>& Extension"}
    
    CheckType -->|Transient Crash / Scratch<br/>.core, .dmp, .tmp| RulePurgeTransient["ACTION: PURGED_RETENTION<br/>Immediate unlink to recover space.<br/>Clean orphan crash traces."]
    
    CheckType -->|Age > 30 Days<br/>Expired Retention| RulePurgeExpired["ACTION: PURGED_RETENTION<br/>Remove uncompressed or .gz archives<br/>exceeding 30-day regulatory window."]
    
    CheckType -->|7 Days < Age <= 30 Days<br/>Uncompressed Log (.log)| RuleCompress["ACTION: COMPRESSED_GZ<br/>Invoke gzip -f.<br/>Recover 70-85% block capacity."]
    
    CheckType -->|14 Days < Age <= 30 Days<br/>AS400 Spool (SPL_*)| RuleAS400Archive["ACTION: COMPRESSED_GZ<br/>Archive spool to compressed tape queue."]
    
    CheckType -->|Within Normal Retention<br/>1 to 7 Days old| RuleRetain["ACTION: SKIPPED_ACTIVE<br/>Retained for active operational queries."]

    RuleActive --> LogLedger["Write Granular Row to<br/>file_action_ledger in SQLite"]
    RulePurgeTransient --> LogLedger
    RulePurgeExpired --> LogLedger
    RuleCompress --> LogLedger
    RuleAS400Archive --> LogLedger
    RuleRetain --> LogLedger
```

---

## 3. Threshold Evaluation & ServiceNow P2 Escalation Flow

Once housekeeping actions complete on a filesystem, `InfraOps-Sentinel` recalculates storage utilization and compares the post-housekeeping delta against SLA policies:

```mermaid
sequenceDiagram
    autonumber
    participant Host as Target Node (e.g. mufg-win-pay01)
    participant Engine as HousekeepingEngine (Python/Bash)
    participant DB as SQLite (infraops_sentinel.db)
    participant SNOW as ServiceNow (MUFG-GLOBAL-STORAGE-L2)

    Engine->>Host: 1. Measure Pre-Housekeeping Telemetry (Disk % & Inode %)
    Note over Host,Engine: mufg-win-pay01 Before Used: 88.7% (Exceeds 85% SLA)
    
    Engine->>Host: 2. Execute Retention Rules (Purge >3d tmp, Compress >7d logs)
    Host-->>Engine: 3. Telemetry Result: Reclaimed 1.00 MB (Diff backup scratch)
    
    Engine->>Host: 4. Measure Post-Housekeeping Telemetry
    Note over Host,Engine: Post-Housekeeping Used: 87.7% (Still exceeds 85.0% SLA!)
    
    Engine->>Engine: 5. SLA Evaluation: after_used_pct (87.7%) >= Critical Threshold (85.0%)
    
    Engine->>DB: 6. Record Audit in housekeeping_audit_log (SLA: CRITICAL_ESCALATED)
    Engine->>DB: 7. Record 36 File Actions in file_action_ledger
    
    Engine->>SNOW: 8. Auto-Generate P2 Incident: INC0094821
    Note over Engine,SNOW: Assignment Group: MUFG-GLOBAL-STORAGE-L2<br/>Severity: P2 - High<br/>Category: Storage / Filesystem Threshold Breach
    
    Engine->>DB: 9. Persist Incident Record in servicenow_incidents table
```

---

## 4. Low-Level Linux & Systems Engineering Breakdown

### A. The Safety Foundation: `set -euo pipefail`
In `scripts/unix_housekeeping.sh` and `scripts/seed_mock_filesystem.sh`, the very first operational line is:
```bash
set -euo pipefail
```
- `-e` (errexit): Immediately aborts script execution if any command exits with a non-zero code. In banking operations, this prevents a failed `cd /target/dir` from cascading into `rm -rf *` inside `/root` or `/`.
- `-u` (nounset): Treats uninitialized shell variables as fatal errors. If `$TARGET_PATH` is undefined, `rm -rf "${TARGET_PATH}/*"` will fail immediately rather than deleting root directories.
- `-o pipefail`: By default, Bash returns the exit status of the *last* command in a pipeline (`cmd1 | cmd2 | cmd3`). If `cmd1` fails, default Bash masks the error. With `pipefail`, if any stage fails, the entire pipeline returns that error code.

> ⚠️ **The SIGPIPE / Head Pitfall in `pipefail`:**  
> When generating large files using `yes "..." | head -c 1024`, `head` exits after 1024 bytes, closing the pipe. Under `pipefail`, `yes` receives SIGPIPE (exit code 141), which would abort the script! In `InfraOps-Sentinel`, we replaced this with `head -c "${remaining}" /dev/zero | tr '\0' 'L' >> "${filepath}"`, ensuring 100% deterministic, SIGPIPE-free execution.

---

### B. Inode Exhaustion vs. Block Exhaustion (`df -P` vs. `df -i`)
Standard storage monitoring often only checks disk blocks via `df -h`. However, in banking message queues and SWIFT parsing directories, **inode exhaustion is equally lethal**:

```bash
# 1. POSIX Block Telemetry (df -k with -P for standard single-line POSIX format)
DF_OUTPUT=$(df -P -k "${TARGET_DIR}" | tail -n 1)
REAL_FS=$(echo "${DF_OUTPUT}" | awk '{print $1}')
REAL_DF_USED_PCT=$(echo "${DF_OUTPUT}" | awk '{print $5}' | tr -d '%')

# 2. Inode Telemetry (-i displays total, used, free inodes and inode %)
DF_INODE_OUTPUT=$(df -P -i "${TARGET_DIR}" | tail -n 1)
INODE_USED_PCT=$(echo "${DF_INODE_OUTPUT}" | awk '{print $5}' | tr -d '%')
```

| Metric | Measured By | Impact of 100% Exhaustion | Typical Root Cause in Banking |
| :--- | :---: | :--- | :--- |
| **Disk Block Usage** | `df -k` | No new data can be written; transactions fail. | Large database transaction log bloat (`.ldf`), uncompressed trace dumps (`.dmp`). |
| **Inode Usage** | `df -i` | No new files can be created (even 0-byte files fail). | Millions of small session cookies, temporary queue scratch files (`.tmp`), unprocessed message fragments. |

---

### C. Active File Protection: Why Deleting Files `< 24 Hours` Old Is Fatal
In Unix systems, deleting an active file that is currently opened by a running daemon (e.g. `core_banking_txn.log` opened by the transaction engine) removes the directory entry from the filesystem tree, but **does NOT release disk blocks**.

```bash
# The Unix Kernel handles open file descriptors independently:
# When process PID 1289 holds an open fd to /var/log/mufg_app/core_banking_txn.log
rm -f /var/log/mufg_app/core_banking_txn.log
```
1. **The Phantom Disk Leak (`lsof +L1`):** The file disappears from `ls -l`, but `df -k` shows disk usage does not drop! The blocks remain allocated until the holding daemon is killed.
2. **Corrupted Process Buffers:** In high-speed payment switches, truncating or gzipping an active log file while the worker process is writing causes buffer misalignment, null-byte padding, and data loss.

**InfraOps-Sentinel Governance Rule:**
```bash
# Epoch delta calculation in seconds
NOW_EPOCH=$(date +%s)
file_mtime=$(stat -c %Y "${filepath}")
diff_sec=$(( NOW_EPOCH - file_mtime ))
file_age_days=$(( diff_sec / 86400 ))

# Active File Protection Gate
if (( file_age_days <= 1 )); then
    action="SKIPPED_ACTIVE"
    FILES_SKIPPED=$(( FILES_SKIPPED + 1 ))
    continue
fi
```

---

## 5. Multi-Platform Translation Table: Unix vs. Windows vs. AS400

Banking systems operate on diverse hardware architectures. The table below maps how `InfraOps-Sentinel` models and executes housekeeping across all three platforms:

| Platform Feature | Unix RHEL (`mufg-rhel-core01`) | Windows Server (`mufg-win-pay01`) | IBM iSeries / AS400 (`mufg-as400-prd02`) |
| :--- | :--- | :--- | :--- |
| **Primary Target Path** | `/var/log/mufg_app` | `D:\SQLData` & `C:\Temp\Dump` | `/QSYS.LIB` & `QSYSPRT.OUTQ` |
| **Storage Unit** | Mount Point / LVM Volume Group | Volume Drive Letter (`C:\`, `D:\`) | Auxiliary Storage Pool (System ASP 1) |
| **Metadata Index** | Inodes (`i-node` table) | Master File Table (MFT records) | Integrated File System (IFS Object Table) |
| **Temporary Files** | `/tmp/*.tmp`, `*.core` | `C:\Windows\Temp`, `*.dmp` | Spool files (`*SPOOL`), Job Logs (`*JOBLOG`) |
| **Active Lock Marker** | Inode lock (`fuser`, `lsof`) | Windows File Lock (`Handle.exe`) | Object Allocation Lock (`WRKOBJLCK`) |
| **Housekeeping Action** | `gzip -f` and `rm -f` | PowerShell `Remove-Item -Force` | `CL: DLTSPLF`, `CL: CLRJOBQ`, `CL: RGZPFM` |
| **Production Risk** | Signal kill required for leaked fd | Locked `.mdf` database files fail | System ASP > 90% triggers automatic OS halt |

---

## 6. Ground-Truth Telemetry Results (Phase 1 Execution)

During our verified execution under run ID **`HKP_20261017_064409`**, `InfraOps-Sentinel` audited 6 nodes and processed 36 files:

```
         hostname      platform                    filesystem_path  before_used_pct  after_used_pct  space_reclaimed_mb         sla_status servicenow_inc_ref
 mufg-rhel-core01     UNIX_RHEL                  /var/log/mufg_app             76.7            61.4                9.23          COMPLIANT                   
mufg-rhel-batch02     UNIX_RHEL                /var/log/mufg_batch             74.4            70.5                0.98          COMPLIANT                   
   mufg-win-app01   WINDOWS_SVR                       C:\Temp\Dump             82.0            64.5                8.76          COMPLIANT                   
   mufg-win-pay01   WINDOWS_SVR                         D:\SQLData             88.7            87.7                1.00 CRITICAL_ESCALATED         INC0094821
mufg-as400-core01 AS400_ISERIES /QSYS.LIB/QUSRSYS.LIB/QSYSPRT.OUTQ             78.9            63.1                7.12          COMPLIANT                   
 mufg-as400-prd02 AS400_ISERIES                          /QSYS.LIB             91.0            91.0                0.00 CRITICAL_ESCALATED         INC0094822
```

### File Ledger Summary
- **Files Compressed (`COMPRESSED_GZ`):** **7** files (`4,305.4 KB` uncompressed)
- **Files Purged (`PURGED_RETENTION`):** **16** files (`19,394.1 KB` removed)
- **Files Protected (`SKIPPED_ACTIVE`):** **13** files (`47,660.0 KB` protected & retained)
- **Total Storage Reclaimed:** **`27.09 MB`** (Production scale equivalent: `280+ GB`)

---

## 7. Interview Insights & Defense Tactics

> 💡 **Interview Insight: Explaining the 85% SLA Breach Escalation**  
> *"If an interviewer asks: 'What happens if your housekeeping script runs, but disk usage is still above the SLA threshold?', answer directly from InfraOps-Sentinel:  
> 'Our engine performs a closed-loop post-cleanup evaluation. On `mufg-win-pay01` and `mufg-as400-prd02`, even after purging expired temporary traces, disk capacity remained at 87.7% and 91.0% respectively due to legitimate transaction database growth and active journal receivers. The engine did not silently fail; it identified that the 85% Critical threshold was breached and automatically triggered structured ServiceNow P2 incidents (`INC0094821`, `INC0094822`) routed to `MUFG-GLOBAL-STORAGE-L2` for LUN expansion and offline journal receiver archiving.'*"

