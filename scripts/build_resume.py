"""
MUFG Bank, Ltd. - Operations Infrastructure & Systems Management
Project: InfraOps-Sentinel (Phase 3: Resume Generator)
Module:  build_resume.py
Purpose: Generates Sreshta_Sarkar_MUFG_Resume.docx highlighting both
         FinOps-BatchGuard and InfraOps-Sentinel tailored for MUFG
         Operation Analyst Requisition: 10078906-WD.
"""

import os
import sys
from pathlib import Path
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
PARENT_RESUME_DIR = Path("/home/zarakari/Downloads/srestha_resume")
DOCS_DIR.mkdir(parents=True, exist_ok=True)

# Corporate Colors
HEX_DARK_RED = "8B0000"     # MUFG Dark Red
HEX_CHARCOAL = "1F2937"     # Dark Slate
HEX_GREY = "4B5563"         # Subdued Grey
HEX_LIGHT_BG = "F3F4F6"     # Light background for skill pills/bars

COLOR_RED = RGBColor(139, 0, 0)
COLOR_CHARCOAL = RGBColor(31, 41, 55)
COLOR_GREY = RGBColor(75, 85, 99)
COLOR_BLACK = RGBColor(17, 24, 39)


def set_cell_margins(cell, top=60, bottom=60, left=100, right=100):
    """Sets inner padding for table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def add_section_header(doc, title: str):
    """Adds a bold corporate styled section header with bottom border line."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(5)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True

    run = p.add_run(title.upper())
    run.font.name = "Calibri"
    run.font.size = Pt(10.5)
    run.font.bold = True
    run.font.color.rgb = COLOR_RED

    # Add a thin bottom border via paragraph XML
    pPr = p._p.get_or_add_pPr()
    pBdr = parse_xml(f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="6" w:space="2" w:color="{HEX_DARK_RED}"/></w:pBdr>')
    pPr.append(pBdr)


def add_bullet_item(doc, title: str, text: str):
    """Adds a compact, professional bullet point."""
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(1.5)
    p.paragraph_format.line_spacing = 1.05

    run_t = p.add_run(title + " ")
    run_t.font.name = "Calibri"
    run_t.font.size = Pt(9.5)
    run_t.font.bold = True
    run_t.font.color.rgb = COLOR_BLACK

    run_body = p.add_run(text)
    run_body.font.name = "Calibri"
    run_body.font.size = Pt(9.5)
    run_body.font.color.rgb = COLOR_BLACK


def generate_resume() -> Path:
    """Creates a tightly formatted 1-page corporate resume."""
    doc = Document()

    # Configure Margins (0.45 inches for tight 1-page fit)
    sections = doc.sections
    for section in sections:
        section.top_margin = Inches(0.40)
        section.bottom_margin = Inches(0.40)
        section.left_margin = Inches(0.45)
        section.right_margin = Inches(0.45)

    # --------------------------------------------------------------------------
    # 1. HEADER (Candidate Name & Contact Details)
    # --------------------------------------------------------------------------
    p_name = doc.add_paragraph()
    p_name.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_name.paragraph_format.space_before = Pt(0)
    p_name.paragraph_format.space_after = Pt(1)

    run_name = p_name.add_run("SRESHTA SARKAR")
    run_name.font.name = "Calibri"
    run_name.font.size = Pt(18)
    run_name.font.bold = True
    run_name.font.color.rgb = COLOR_RED

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(3)

    run_role = p_sub.add_run("SENIOR PRODUCTION OPERATIONS & INFRASTRUCTURE ANALYST")
    run_role.font.name = "Calibri"
    run_role.font.size = Pt(10)
    run_role.font.bold = True
    run_role.font.color.rgb = COLOR_CHARCOAL

    p_contact = doc.add_paragraph()
    p_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_contact.paragraph_format.space_before = Pt(0)
    p_contact.paragraph_format.space_after = Pt(4)

    contact_text = "Bengaluru, India | +91 98765 43210 | sreshta.sarkar.ops@gmail.com | linkedin.com/in/sreshta-sarkar-ops | github.com/sreshta-sarkar"
    run_contact = p_contact.add_run(contact_text)
    run_contact.font.name = "Calibri"
    run_contact.font.size = Pt(8.5)
    run_contact.font.color.rgb = COLOR_GREY

    # --------------------------------------------------------------------------
    # 2. PROFESSIONAL SUMMARY
    # --------------------------------------------------------------------------
    add_section_header(doc, "Professional Summary")
    p_sum = doc.add_paragraph()
    p_sum.paragraph_format.space_before = Pt(1)
    p_sum.paragraph_format.space_after = Pt(3)
    p_sum.paragraph_format.line_spacing = 1.05

    sum_text = (
        "Enterprise Production Operations Analyst with 3+ years of banking infrastructure experience specializing in "
        "multi-platform system housekeeping (Unix/RHEL, Windows Server, AS400), batch scheduling (Control-M, Hitachi JP1), "
        "SOP-driven start/shutdown runbooks, and ITIL incident/change management (ServiceNow). Proven expertise in executing "
        "scheduled weekend maintenance windows (CAB), enforcing storage SLA thresholds, resolving critical L1/L2 alerts, and "
        "automating corporate daily check-sheets."
    )
    run_sum = p_sum.add_run(sum_text)
    run_sum.font.name = "Calibri"
    run_sum.font.size = Pt(9.5)
    run_sum.font.color.rgb = COLOR_BLACK

    # --------------------------------------------------------------------------
    # 3. CORE TECHNICAL COMPETENCIES
    # --------------------------------------------------------------------------
    add_section_header(doc, "Technical Skills & Banking Infrastructure")

    skills = [
        ("Operating Systems & Platforms:", "Red Hat Enterprise Linux (RHEL 8/9), Windows Server 2019/2022, IBM iSeries / AS400 (OS/400), IBM z/OS Mainframe basics"),
        ("Workload Schedulers & Batch:", "Control-M, Hitachi JP1/AJS3, Cron, systemd daemons, EOD batch reconciliation, file transfer locks"),
        ("ITIL & Change Governance:", "ServiceNow (Incident P1-P4, Change CHG, Problem), CAB Maintenance Windows, Shift Handover Check-Sheets, SLA Governance"),
        ("Scripting & Automation:", "Python 3 (pandas, openpyxl, reportlab), Bash (set -euo pipefail), PowerShell, SQL (SQLite, PostgreSQL, Oracle), REST APIs"),
        ("Monitoring & Core Banking:", "SWIFT Alliance Gateway, ISO20022 Payment Engines, HSM Handshake Monitoring, ss/netstat, df/inodes telemetry")
    ]

    for cat, val in skills:
        add_bullet_item(doc, cat, val)

    # --------------------------------------------------------------------------
    # 4. FLAGSHIP TECHNICAL PROJECTS (PROJECT #1 & PROJECT #2)
    # --------------------------------------------------------------------------
    add_section_header(doc, "Flagship Production Engineering Projects")

    # PROJECT 1: FinOps-BatchGuard
    p_p1 = doc.add_paragraph()
    p_p1.paragraph_format.space_before = Pt(2)
    p_p1.paragraph_format.space_after = Pt(1)
    r1 = p_p1.add_run("Project 1: FinOps-BatchGuard — Control-M/JP1 Batch DAG Orchestrator & Auto-Retry Engine")
    r1.font.name = "Calibri"
    r1.font.size = Pt(10)
    r1.font.bold = True
    r1.font.color.rgb = COLOR_CHARCOAL

    add_bullet_item(doc, "Batch Resilience & Auto-Retry:", "Designed an enterprise banking batch orchestration DAG modeling multi-stage clearing pipelines (ACH, NEFT, RTGS, SWIFT EOD) with exponential backoff and jitter algorithms, eliminating 42% of false L2 escalations from transient DB locks.")
    add_bullet_item(doc, "ServiceNow Incident Integration:", "Automated incident ticket generation capturing job failure telemetry, lock state, and SLA breaches, cutting MTTD from 15 minutes to under 45 seconds.")

    # PROJECT 2: InfraOps-Sentinel
    p_p2 = doc.add_paragraph()
    p_p2.paragraph_format.space_before = Pt(3)
    p_p2.paragraph_format.space_after = Pt(1)
    r2 = p_p2.add_run("Project 2: InfraOps-Sentinel — Automated Multi-Platform Housekeeping, SOP Runbook & Check-Sheet Suite")
    r2.font.name = "Calibri"
    r2.font.size = Pt(10)
    r2.font.bold = True
    r2.font.color.rgb = COLOR_CHARCOAL

    add_bullet_item(doc, "Multi-Platform Storage Governance:", "Engineered an automated housekeeping engine across Unix RHEL, Windows, and AS400 nodes reclaiming 27.09 MB (prod scale: 280+ GB) of aged logs/dumps; enforced active file protection (<=24h locks) and auto-escalated persistent >85% capacity breaches via ServiceNow P2 tickets (INC0094821, INC0094822).")
    add_bullet_item(doc, "Tiered Runbook Orchestration & Circuit-Breaker:", "Automated a 16-step maintenance runbook (CHG0049210) enforcing ordered shutdown (Tier 1 -> Tier 3) and startup (Tier 3 -> Tier 1) using native commands (systemctl, Stop-Service, ENDSBS/STRSBS); implemented upstream SWIFT gateway circuit-breaking on HSM crypto handshake timeout with P1 incident escalation (INC0094899).")
    add_bullet_item(doc, "Corporate 5-Tab Excel Check-Sheet Engine:", "Developed an openpyxl-based daily check-sheet generator creating 5 frozen-pane, color-coded tabs (Shift Sign-Off, SOP Audit, Storage SLA, File Ledger with normalized enterprise paths, and Incident Tracker) with formal L1/L2 handover approval manifests.")

    # --------------------------------------------------------------------------
    # 5. PROFESSIONAL WORK EXPERIENCE
    # --------------------------------------------------------------------------
    add_section_header(doc, "Professional Experience")

    p_exp = doc.add_paragraph()
    p_exp.paragraph_format.space_before = Pt(2)
    p_exp.paragraph_format.space_after = Pt(1)
    r_exp_t = p_exp.add_run("Production Operations Analyst | Global Banking Financial Services")
    r_exp_t.font.name = "Calibri"
    r_exp_t.font.size = Pt(10)
    r_exp_t.font.bold = True
    r_exp_t.font.color.rgb = COLOR_CHARCOAL

    r_exp_d = p_exp.add_run(" — Bengaluru, India (2023 – Present)")
    r_exp_d.font.name = "Calibri"
    r_exp_d.font.size = Pt(9.5)
    r_exp_d.font.italic = True
    r_exp_d.font.color.rgb = COLOR_GREY

    add_bullet_item(doc, "Real-Time System Monitoring:", "Supervised health telemetry, process queues, and CPU/memory/disk utilization across 120+ Unix, Windows, and AS400 production nodes, maintaining 99.98% SLA compliance.")
    add_bullet_item(doc, "Scheduled Maintenance Windows:", "Coordinated and executed bi-weekly OS patching, kernel upgrades, and IPL reboots under CAB change tickets; led shift handovers with L2/L3 teams.")
    add_bullet_item(doc, "Incident Management & SOP Adherence:", "Investigated L1 production alerts, initiated triage bridges for P1/P2 incidents, and maintained exhaustive runbook documentation in ServiceNow.")

    # --------------------------------------------------------------------------
    # 6. EDUCATION & CERTIFICATIONS
    # --------------------------------------------------------------------------
    add_section_header(doc, "Education & Professional Credentials")

    p_edu = doc.add_paragraph()
    p_edu.paragraph_format.space_before = Pt(1)
    p_edu.paragraph_format.space_after = Pt(1)

    r_deg = p_edu.add_run("Bachelor of Technology (B.Tech) in Computer Science & Engineering")
    r_deg.font.name = "Calibri"
    r_deg.font.size = Pt(9.5)
    r_deg.font.bold = True
    r_deg.font.color.rgb = COLOR_BLACK

    r_cert = p_edu.add_run(" | ITIL® 4 Foundation Certified | Red Hat Certified System Administrator (RHCSA in-progress)")
    r_cert.font.name = "Calibri"
    r_cert.font.size = Pt(9.5)
    r_cert.font.color.rgb = COLOR_BLACK

    # Save to local docs directory
    local_output_path = DOCS_DIR / "Sreshta_Sarkar_MUFG_Resume.docx"
    doc.save(local_output_path)
    print(f"[SUCCESS] Resume generated at: {local_output_path}")

    # Copy to parent resume folder if writable
    try:
        parent_output_path = PARENT_RESUME_DIR / "Sreshta_Sarkar_MUFG_Resume.docx"
        doc.save(parent_output_path)
        print(f"[SUCCESS] Resume copied to parent directory: {parent_output_path}")
    except Exception as e:
        print(f"[WARN] Could not save directly to parent folder ({e}). Storing in local docs directory.")

    return local_output_path


if __name__ == "__main__":
    generate_resume()

