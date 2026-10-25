"""
MUFG Bank, Ltd. - Operations Infrastructure & Systems Management
Project: InfraOps-Sentinel (Phase 3: Mobile Revision PDF Suite)
Module:  generate_mobile_guide.py
Purpose: Generates a 4.5 x 8.0 inch mobile pocket interview & architecture
         study guide PDF with dark banking theme and high-impact cheat-sheets.
"""

import os
import sys
from pathlib import Path
from reportlab.lib.pagesizes import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
PDF_PATH = DOCS_DIR / "InfraOps_Sentinel_MUFG_Interview_Guide.pdf"

# Dimensions
PAGE_WIDTH = 4.5 * inch
PAGE_HEIGHT = 8.0 * inch

# Color Palette (Dark Banking Theme)
BG_COLOR = colors.HexColor("#0F172A")        # Deep Slate / Navy
CARD_BG = colors.HexColor("#1E293B")         # Card Slate
CARD_BORDER = colors.HexColor("#334155")     # Border Slate
ACCENT_RED = colors.HexColor("#E11D48")      # Crimson Red (MUFG)
ACCENT_AMBER = colors.HexColor("#F59E0B")    # Warning Amber
ACCENT_GREEN = colors.HexColor("#10B981")    # Success Emerald
ACCENT_CYAN = colors.HexColor("#06B6D4")     # Tech Cyan
TEXT_WHITE = colors.HexColor("#F8FAFC")      # Primary Text
TEXT_MUTED = colors.HexColor("#94A3B8")      # Subdued Text
TEXT_DARK = colors.HexColor("#0F172A")


class NumberedCanvas(canvas.Canvas):
    """Custom canvas providing dark background, top accent bar, and page numbers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages):
        self.saveState()
        # Draw dark canvas background
        self.setFillColor(BG_COLOR)
        self.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=True, stroke=False)

        # Draw top accent bar
        self.setFillColor(ACCENT_RED)
        self.rect(0, PAGE_HEIGHT - 4, PAGE_WIDTH, 4, fill=True, stroke=False)

        # Draw footer line
        self.setStrokeColor(CARD_BORDER)
        self.setLineWidth(0.5)
        self.line(18, 22, PAGE_WIDTH - 18, 22)

        # Header branding
        self.setFont("Helvetica-Bold", 6.5)
        self.setFillColor(TEXT_MUTED)
        self.drawString(18, PAGE_HEIGHT - 16, "MUFG BANK | INFRAOPS-SENTINEL POCKET STUDY GUIDE")

        # Footer page number
        self.setFont("Helvetica", 6.5)
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(PAGE_WIDTH - 18, 12, page_str)
        self.drawString(18, 12, "Requisition: 10078906-WD (Operation Analyst)")
        self.restoreState()


def build_mobile_pdf():
    """Compiles the mobile revision guide PDF."""
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        leftMargin=18,
        rightMargin=18,
        topMargin=26,
        bottomMargin=26
    )

    styles = getSampleStyleSheet()

    # Custom Typography Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=TEXT_WHITE,
        spaceAfter=3
    )

    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=ACCENT_RED,
        spaceBefore=4,
        spaceAfter=3
    )

    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=ACCENT_CYAN,
        spaceBefore=3,
        spaceAfter=2
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=TEXT_WHITE,
        spaceAfter=3
    )

    body_muted = ParagraphStyle(
        'BodyMuted',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9.5,
        textColor=TEXT_MUTED,
        spaceAfter=2
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=6.5,
        leading=8.5,
        textColor=ACCENT_AMBER
    )

    story = []

    # ==========================================================================
    # PAGE 1: TITLE & ELEVATOR PITCH
    # ==========================================================================
    story.append(Paragraph("INFRAOPS-SENTINEL", title_style))
    story.append(Paragraph("Automated Multi-Platform Housekeeping, Start/Shutdown Runbook & Excel Check-Sheet Engine", h2_style))
    story.append(Paragraph("<b>Target Candidate:</b> Sreshta Sarkar | <b>Target Role:</b> Operation Analyst", body_muted))
    story.append(Paragraph("<b>MUFG Requisition:</b> 10078906-WD | <b>CAB Ref:</b> CHG0049210", body_muted))
    story.append(HRFlowable(width="100%", thickness=1, color=CARD_BORDER, spaceBefore=4, spaceAfter=6))

    story.append(Paragraph("THE 30-SECOND INTERVIEW ELEVATOR PITCH", h1_style))
    story.append(Paragraph(
        "<i>\"InfraOps-Sentinel is a multi-platform production operations suite designed directly against MUFG's core operations mandate: automated system housekeeping, SLA-governed shutdown/startup runbooks, and corporate shift check-sheets across Unix RHEL, Windows Server, and IBM iSeries AS400.\"</i>",
        body_style
    ))

    # Architecture Pillar Box
    pillars_data = [
        [Paragraph("<b>PILLAR</b>", code_style), Paragraph("<b>ENTERPRISE FUNCTION</b>", code_style)],
        [Paragraph("<b>Phase 1: Housekeeping</b>", body_style), Paragraph("Active file protection (&le;24h locks), aged log compression (.gz), dump purge, P2 storage incident auto-escalation.", body_muted)],
        [Paragraph("<b>Phase 2: Runbooks</b>", body_style), Paragraph("Ordered 16-step maintenance SOP: Top-down shutdown, maintenance gate check, bottom-up startup, and SWIFT circuit-breaking.", body_muted)],
        [Paragraph("<b>Phase 3: Check-Sheet</b>", body_style), Paragraph("5-tab corporate Excel report with frozen panes, conditional status pills, normalized enterprise paths, and shift handover sign-offs.", body_muted)]
    ]
    t_pillars = Table(pillars_data, colWidths=[105, 183])
    t_pillars.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, CARD_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, CARD_BORDER),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_pillars)
    story.append(PageBreak())

    # ==========================================================================
    # PAGE 2: PHASE 1 - STORAGE HOUSEKEEPING & GOVERNANCE
    # ==========================================================================
    story.append(Paragraph("PHASE 1: HOUSEKEEPING & SLA GOVERNANCE", h1_style))
    story.append(Paragraph("Mandatory retention policies, active file safety, and storage SLA thresholds.", body_muted))
    story.append(HRFlowable(width="100%", thickness=1, color=CARD_BORDER, spaceBefore=2, spaceAfter=5))

    story.append(Paragraph("1. Active File Protection Rule (Critical)", h2_style))
    story.append(Paragraph(
        "Files modified within the last 24 hours (<b>&le; 1 day</b>) are strictly tagged <b>SKIPPED_ACTIVE</b>. This prevents race conditions and ensures live core banking transactions, active minidumps, and open journal receivers are never corrupted or removed.",
        body_style
    ))

    story.append(Paragraph("2. Tiered Platform Retention Policies", h2_style))
    retention_data = [
        [Paragraph("<b>Platform</b>", code_style), Paragraph("<b>Path</b>", code_style), Paragraph("<b>Policy Rules</b>", code_style)],
        [Paragraph("Unix RHEL", body_style), Paragraph("/var/log/mufg_app", code_style), Paragraph(">7d gzip compress; >30d purge; orphan .core/.tmp purge", body_muted)],
        [Paragraph("Windows", body_style), Paragraph("C:\\Temp\\Dump", code_style), Paragraph(">3d purge crash minidumps and scratch tmp", body_muted)],
        [Paragraph("AS400", body_style), Paragraph("QSYSPRT / QSYS", code_style), Paragraph(">14d archive spool; >30d purge joblogs", body_muted)]
    ]
    t_ret = Table(retention_data, colWidths=[55, 95, 138])
    t_ret.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, CARD_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, CARD_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_ret)
    story.append(Spacer(1, 4))

    story.append(Paragraph("3. SLA Thresholds & Auto-Escalation", h2_style))
    story.append(Paragraph(
        "&bull; <b>Warning (75.0%):</b> Logged as WARNING SLA in SQLite.<br/>"
        "&bull; <b>Critical (85.0%):</b> Automatically raises ServiceNow P2 ticket (e.g. <b>INC0094821</b> on mufg-win-pay01 and <b>INC0094822</b> on mufg-as400-prd02) assigned to <i>MUFG-GLOBAL-STORAGE-L2</i>.",
        body_style
    ))
    story.append(Paragraph(
        "&bull; <b>Audit Manifest:</b> Generates SHA-256 cryptographic hash of every node ledger for unalterable regulatory compliance.",
        body_muted
    ))
    story.append(PageBreak())

    # ==========================================================================
    # PAGE 3: PHASE 2 - ORDERED SHUTDOWN & GATE CHECK
    # ==========================================================================
    story.append(Paragraph("PHASE 2: ORDERED SHUTDOWN RUNBOOK", h1_style))
    story.append(Paragraph("Change Window CHG0049210: Top-Down Shutdown Sequence.", body_muted))
    story.append(HRFlowable(width="100%", thickness=1, color=CARD_BORDER, spaceBefore=2, spaceAfter=5))

    story.append(Paragraph("Why Top-Down Shutdown? (Tier 1 &rarr; 2 &rarr; 3)", h2_style))
    story.append(Paragraph(
        "In banking architectures, you <b>must close edge ingress gateways first</b> so no customer transactions enter while middleware or backend ledger databases are being taken offline. Shutting down the database first results in uncommitted transactions, message loss, and corrupt reconciliation balances.",
        body_style
    ))

    shutdown_steps_data = [
        [Paragraph("<b>Tier & Host</b>", code_style), Paragraph("<b>Service</b>", code_style), Paragraph("<b>Pre-check & Command</b>", code_style)],
        [Paragraph("<b>Tier 1</b><br/>mufg-rhel-core01", body_style), Paragraph("mufg-swift-gateway", code_style), Paragraph("Drain sockets (:8443 == 0)<br/>systemctl stop mufg-swift-gateway (SLA: 30s)", body_muted)],
        [Paragraph("<b>Tier 2</b><br/>mufg-win-pay01", body_style), Paragraph("ISO20022 PayEngine", code_style), Paragraph("MSMQ queue depth == 0<br/>Stop-Service -Force (SLA: 45s)", body_muted)],
        [Paragraph("<b>Tier 2</b><br/>mufg-rhel-batch02", body_style), Paragraph("Settlement Daemon", code_style), Paragraph("No active batch PID lock<br/>systemctl stop (SLA: 30s)", body_muted)],
        [Paragraph("<b>Tier 3</b><br/>mufg-as400-core01", body_style), Paragraph("QBATCH & QINTER", code_style), Paragraph("Drain teller sessions<br/>ENDSBS *CNTRLD (SLA: 90s)", body_muted)],
        [Paragraph("<b>Tier 3</b><br/>mufg-as400-prd02", body_style), Paragraph("MUFGCORE Ledger", code_style), Paragraph("Sync journal receivers<br/>ENDSBS *CNTRLD (SLA: 90s)", body_muted)]
    ]
    t_shut = Table(shutdown_steps_data, colWidths=[75, 85, 128])
    t_shut.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, CARD_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, CARD_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_shut)
    story.append(Spacer(1, 4))

    story.append(Paragraph("Maintenance Gate Check (Stage B)", h2_style))
    story.append(Paragraph(
        "Orchestrator verifies all 5 subsystems are in <b>STOPPED_VERIFIED</b> state. If any service fails to stop, startup is strictly blocked and the maintenance window is placed on hold.",
        body_style
    ))
    story.append(PageBreak())

    # ==========================================================================
    # PAGE 4: PHASE 2 - STARTUP & CIRCUIT-BREAKER
    # ==========================================================================
    story.append(Paragraph("PHASE 2: STARTUP & CIRCUIT-BREAKER", h1_style))
    story.append(Paragraph("Bottom-Up Startup (Tier 3 &rarr; 1) with Controlled Failure Escalation.", body_muted))
    story.append(HRFlowable(width="100%", thickness=1, color=CARD_BORDER, spaceBefore=2, spaceAfter=5))

    story.append(Paragraph("1. Bottom-Up Startup Hierarchy", h2_style))
    story.append(Paragraph(
        "&bull; <b>Step 11-12 (Tier 3):</b> Core banking AS400 subsystems (QBATCH/QINTER and MUFGCORE) started via <i>STRSBS</i> [STARTED_VERIFIED].<br/>"
        "&bull; <b>Step 13 (Tier 2):</b> Settlement daemon started via <i>systemctl</i> [STARTED_VERIFIED].",
        body_style
    ))

    story.append(Paragraph("2. Injected Middleware Failure & Retry", h2_style))
    story.append(Paragraph(
        "&bull; <b>Step 14 (Attempt #1):</b> <i>mufg-win-pay01</i> startup fails port 9443 validation (HSM crypto handshake timeout). Elapsed <b>48.4s</b> vs 45s SLA.<br/>"
        "&bull; <b>Step 15 (Attempt #2):</b> Automated SOP restart retry fails after <b>49.1s</b>. Marked <b>FAILED_SLA_BREACH</b>.<br/>"
        "&bull; <b>P1 Escalation:</b> Raises ServiceNow P1 Incident <b>INC0094899</b> assigned to <i>MUFG-WIN-MIDDLEWARE-L2</i>.",
        body_style
    ))

    story.append(Paragraph("3. Upstream Dependency Circuit-Breaker", h2_style))
    story.append(Paragraph(
        "&bull; <b>Step 16 (Tier 1 Protection):</b> Rather than blindly starting the SWIFT gateway, the orchestrator detects Tier 2 backend failure and activates the <b>HALTED_DEPENDENCY_BLOCK</b> circuit-breaker.<br/>"
        "&bull; <b>Operational Impact:</b> Prevents live SWIFT financial messages from entering an inoperable backend payment engine, avoiding widespread transaction drops and regulatory breach.",
        body_style
    ))
    story.append(PageBreak())

    # ==========================================================================
    # PAGE 5: PHASE 3 - CORPORATE EXCEL CHECK-SHEET
    # ==========================================================================
    story.append(Paragraph("PHASE 3: CORPORATE CHECK-SHEET ENGINE", h1_style))
    story.append(Paragraph("Automated 5-Tab Excel Report & Shift Handover Sign-Off.", body_muted))
    story.append(HRFlowable(width="100%", thickness=1, color=CARD_BORDER, spaceBefore=2, spaceAfter=5))

    story.append(Paragraph("Workbook Architecture (.xlsx)", h2_style))
    tabs_summary = [
        [Paragraph("<b>Tab Name</b>", code_style), Paragraph("<b>Key Contents & Formatting</b>", code_style)],
        [Paragraph("01_Shift_SignOff", body_style), Paragraph("Shift metadata, RAG status (AMBER/RED), KPI summary cards, and formal L1->L2 sign-off checklist.", body_muted)],
        [Paragraph("02_Start_Shutdown", body_style), Paragraph("16-step runbook audit log, elapsed seconds, SLA limits, and circuit-breaker status (Frozen A5).", body_muted)],
        [Paragraph("03_Storage_SLA", body_style), Paragraph("6-node storage audit, before/after disk & inode %, reclaimed MB, SHA-256 manifest hash.", body_muted)],
        [Paragraph("04_File_Ledger", body_style), Paragraph("All 36 file actions with <b>canonical enterprise path normalization</b> (/var/log, C:\\Temp, /QSYS.LIB).", body_muted)],
        [Paragraph("05_Escalations", body_style), Paragraph("Active ServiceNow tickets (INC0094821, INC0094822, INC0094899) with root cause & L1 action plan.", body_muted)]
    ]
    t_tabs = Table(tabs_summary, colWidths=[90, 198])
    t_tabs.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), CARD_BG),
        ('BOX', (0, 0), (-1, -1), 0.5, CARD_BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, CARD_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ]))
    story.append(t_tabs)
    story.append(Spacer(1, 4))

    story.append(Paragraph("Compliance & Visual Styling Rules", h2_style))
    story.append(Paragraph(
        "&bull; <b>Header Banner:</b> MUFG Corporate Dark Red (#8B0000) & Charcoal (#1F2937).<br/>"
        "&bull; <b>Frozen Panes:</b> A5 freeze across data tabs for seamless scrolling.<br/>"
        "&bull; <b>Conditional Pills:</b> Green (#D1FAE5) for Compliant, Amber (#FEF3C7) for Warning/Halted, Red (#FEE2E2) for Critical/Breached.",
        body_style
    ))
    story.append(PageBreak())

    # ==========================================================================
    # PAGE 6: INTERVIEW CHEATSHEET & Q&A
    # ==========================================================================
    story.append(Paragraph("MUFG INTERVIEW Q&A CHEATSHEET", h1_style))
    story.append(Paragraph("Targeting MUFG Requisition 10078906-WD (Operation Analyst)", body_muted))
    story.append(HRFlowable(width="100%", thickness=1, color=CARD_BORDER, spaceBefore=2, spaceAfter=5))

    qa_list = [
        ("Q1: Why is shutdown top-down but startup bottom-up?",
         "Top-down shutdown drains edge ingress first (Tier 1 SWIFT) so in-flight requests finish before middleware and databases stop. Bottom-up startup ensures data persistence and ledger subsystems (Tier 3 AS400) are fully healthy before middleware and edge gateways start accepting traffic."),
        ("Q2: How do you prevent corrupting active banking processes during housekeeping?",
         "We enforce the Active File Protection rule: files modified within 24h (&le;1d) are tagged SKIPPED_ACTIVE. Only files exceeding strict retention thresholds (>7d compress, >30d purge) and orphan crash dumps are touched."),
        ("Q3: What happened during the payment engine startup failure?",
         "mufg-win-pay01 exceeded its 45s startup SLA (48.4s/49.1s) due to an HSM handshake timeout. Our orchestrator prevented live financial losses by circuit-breaking upstream Tier 1 SWIFT Gateway and raising P1 Incident INC0094899 in ServiceNow."),
        ("Q4: How does this map to MUFG's daily reporting requirements?",
         "Our Phase 3 generator extracts telemetry into a 5-tab corporate Excel check-sheet with executive RAG cards, frozen panes, and formal shift handover approvals, providing instant auditability for CAB and regulators.")
    ]

    for q, a in qa_list:
        story.append(Paragraph(f"<b>{q}</b>", h2_style))
        story.append(Paragraph(a, body_style))
        story.append(Spacer(1, 2))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"[SUCCESS] Mobile pocket study guide PDF generated at: {PDF_PATH}")
    return PDF_PATH


if __name__ == "__main__":
    build_mobile_pdf()

