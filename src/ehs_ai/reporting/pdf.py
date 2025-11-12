from __future__ import annotations

from datetime import datetime
from typing import Iterable, List
import unicodedata

from fpdf import FPDF

from ehs_ai.schemas import (
    CorrectiveActionPlan,
    IncidentWorkflowReport,
    NotificationResult,
    PolicyReference,
    EvidenceItem,
)


class IncidentPDF(FPDF):
    """Customised FPDF wrapper for incident workflow reports."""

    def header(self) -> None:  # type: ignore[override]
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "Incident Workflow Report", ln=True, align="L")
        self.ln(4)

    def add_section_title(self, title: str) -> None:
        self.set_font("Helvetica", "B", 13)
        self.cell(0, 8, title, ln=True)
        self.set_font("Helvetica", size=11)

    def add_key_value(self, key: str, value: str | None) -> None:
        value_str = _sanitize(value if value else "N/A")
        text = f"{key}: {value_str}"
        self.set_font("Helvetica", size=11)
        self.multi_cell(0, 6, text)
        self.ln(1)

    def add_bullet_list(self, items: Iterable[str]) -> None:
        items = list(items)
        if not items:
            self.cell(0, 6, "- None", ln=1)
            return
        for item in items:
            lines = _wrap_lines(item)
            for idx, line in enumerate(lines):
                prefix = "- " if idx == 0 else "  "
                self.cell(0, 6, f"{prefix}{line}", ln=1)
        self.ln(1)

    def add_wrapped_text(self, text: str | None) -> None:
        sanitized = _sanitize(text if text else "")
        self.set_font("Helvetica", size=11)
        for line in _wrap_lines(sanitized):
            self.cell(0, 6, line, ln=1)
        self.ln(1)


def _format_policy_reference(ref: PolicyReference) -> str:
    return f"{ref.title} ({ref.source}): {ref.excerpt}"


def _render_corrective_actions(pdf: IncidentPDF, corrective: CorrectiveActionPlan) -> None:
    pdf.add_section_title("Corrective Action Plan")
    pdf.add_bullet_list(corrective.actions)
    pdf.ln(2)
    pdf.add_section_title("Responsible Parties")
    pdf.add_bullet_list(corrective.responsible_parties)
    pdf.ln(2)
    pdf.add_section_title("Due Dates")
    pdf.add_bullet_list(corrective.due_dates or ["Not specified"])
    pdf.ln(2)
    if corrective.policy_references:
        pdf.add_section_title("Policy References")
        policy_items = [_format_policy_reference(ref) for ref in corrective.policy_references]
        pdf.add_bullet_list(policy_items)
        pdf.ln(2)


def _render_notifications(pdf: IncidentPDF, notifications: NotificationResult) -> None:
    pdf.add_section_title("Notification Plan - Tickets")
    ticket_lines = [
        f"{ticket.request.title} (Priority: {ticket.request.priority}) -> {ticket.ticket_id} [{ticket.status}]"
        for ticket in notifications.tickets
    ]
    pdf.add_bullet_list(ticket_lines or ["No tickets created"])
    pdf.ln(2)
    pdf.add_section_title("Notification Plan - Emails")
    email_lines = [
        f"{email.request.recipient} | {email.request.subject} -> {email.status}"
        for email in notifications.emails
    ]
    pdf.add_bullet_list(email_lines or ["No emails sent"])
    if notifications.notes:
        pdf.ln(2)
        pdf.add_wrapped_text(f"Notes: {notifications.notes}")


def _wrap_lines(text: str | None, width: int = 90) -> List[str]:
    """Break text into chunks so each line renders safely within the page width."""
    sanitized = _sanitize(text if text is not None else "")
    if not sanitized:
        return [""]
    lines: List[str] = []
    for raw_line in sanitized.splitlines() or [sanitized]:
        if not raw_line:
            lines.append("")
            continue
        start = 0
        while start < len(raw_line):
            lines.append(raw_line[start : start + width])
            start += width
    return lines or [""]


def _sanitize(value: str | None) -> str:
    """Convert text to a latin-1-friendly representation, replacing problem characters."""
    if value is None:
        return ""
    replacements = {
        "→": "->",
        "←": "<-",
        "↔": "<->",
        "–": "-",
        "—": "-",
        "−": "-",
        "•": "-",
        "·": "-",
        "“": '"',
        "”": '"',
        "„": '"',
        "‟": '"',
        "’": "'",
        "‘": "'",
        "‛": "'",
        "…": "...",
        " ": " ",
        " ": " ",
    }
    normalized = unicodedata.normalize("NFKC", str(value))
    translated_chars: List[str] = []
    for ch in normalized:
        if ch in replacements:
            translated_chars.append(replacements[ch])
        elif ord(ch) < 32 and ch not in "\n\r\t":
            translated_chars.append(" ")
        else:
            translated_chars.append(ch)
    joined = "".join(translated_chars)
    ascii_bytes = joined.encode("latin-1", "replace")
    ascii_str = ascii_bytes.decode("latin-1")
    cleaned = "".join(ch if (32 <= ord(ch) < 127) or ch in "\n\r\t" else "?" for ch in ascii_str)
    return cleaned.strip()


def _render_evidence(pdf: IncidentPDF, evidence: Iterable[EvidenceItem]) -> None:
    pdf.add_section_title("Evidence")
    evidence = list(evidence)
    if not evidence:
        pdf.add_bullet_list(["No evidence uploaded."])
        return
    lines = []
    for item in evidence:
        base = f"{item.filename} ({_format_size(item.size_bytes)}) -> {item.url}"
        if item.analysis:
            base += f" | Analysis: {item.analysis}"
        lines.append(base)
    pdf.add_bullet_list(lines)


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    kb = size_bytes / 1024
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024
    return f"{mb:.1f} MB"


def generate_incident_pdf(report: IncidentWorkflowReport) -> bytes:
    """Render the workflow report as a PDF document."""

    pdf = IncidentPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    generated_at = report.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    pdf.set_font("Helvetica", size=11)
    pdf.add_key_value("Generated", generated_at)
    pdf.add_key_value("Incident Title", report.incident.title)
    pdf.add_key_value("Reported By", report.incident.reported_by or "Unknown")
    pdf.add_key_value("Location", report.incident.location or "Not specified")
    pdf.add_key_value("Time of Incident", report.incident.time_of_incident or "Not provided")
    pdf.ln(4)

    pdf.add_section_title("Reporter Description")
    pdf.add_wrapped_text(report.incident.description)
    pdf.ln(2)

    pdf.add_section_title("Intake Summary")
    pdf.add_wrapped_text(report.intake.narrative)
    pdf.ln(2)
    pdf.add_key_value("Severity Assessment", report.intake.severity)
    pdf.add_section_title("Key Findings")
    pdf.add_bullet_list(report.intake.key_findings)
    pdf.ln(2)
    pdf.add_section_title("Injuries / Illnesses")
    pdf.add_bullet_list(report.intake.injuries_or_illnesses)
    pdf.ln(4)

    pdf.add_section_title("Triage Assessment")
    pdf.add_key_value("Risk Level", report.triage.risk_level)
    pdf.add_section_title("Priority Actions")
    pdf.add_bullet_list(report.triage.priority_actions)
    pdf.ln(2)
    pdf.add_section_title("Escalation Channels")
    pdf.add_bullet_list(report.triage.escalation_channels)
    pdf.ln(2)
    pdf.add_section_title("Monitoring Plan")
    pdf.add_wrapped_text(report.triage.monitoring_plan)
    pdf.ln(4)

    pdf.add_section_title("Root Cause Analysis")
    pdf.add_section_title("Primary Causes")
    pdf.add_bullet_list(report.root_cause.primary_causes)
    pdf.ln(2)
    pdf.add_section_title("Contributing Factors")
    pdf.add_bullet_list(report.root_cause.contributing_factors)
    pdf.ln(2)
    pdf.add_section_title("Investigation Gaps")
    pdf.add_bullet_list(report.root_cause.uncertainty_gaps)
    pdf.ln(4)

    _render_corrective_actions(pdf, report.corrective_actions)
    pdf.ln(4)
    _render_notifications(pdf, report.notifications)
    pdf.ln(4)
    _render_evidence(pdf, report.evidence)

    raw_output = pdf.output(dest="S")
    if isinstance(raw_output, (bytes, bytearray)):
        return bytes(raw_output)
    return str(raw_output).encode("latin1", "replace")

