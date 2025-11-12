from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """Metadata about uploaded evidence associated with an incident."""

    filename: str
    url: str
    size_bytes: int
    analysis: Optional[str] = None


class IncidentReport(BaseModel):
    """Input payload representing an incident submission."""

    title: str
    description: str
    reported_by: Optional[str] = None
    severity_hint: Optional[str] = Field(
        default=None, description="Initial severity impression from the reporter."
    )
    location: Optional[str] = None
    time_of_incident: Optional[str] = None
    individuals_involved: List[str] = Field(default_factory=list)
    attachments: List[str] = Field(
        default_factory=list,
        description="Optional references to evidence (file paths, URLs, etc.).",
    )


class IntakeSummary(BaseModel):
    """Summarizes the incident report and key immediate concerns."""

    narrative: str
    key_findings: List[str]
    injuries_or_illnesses: List[str]
    severity: Literal["low", "medium", "high", "critical"]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class TriageAssessment(BaseModel):
    """Determines urgency and immediate containment actions."""

    risk_level: Literal["low", "medium", "high", "critical"]
    priority_actions: List[str]
    escalation_required: bool
    escalation_channels: List[str]
    monitoring_plan: str
    rationale: str


class RootCauseAnalysis(BaseModel):
    """Identifies plausible root causes and contributing factors."""

    primary_causes: List[str]
    contributing_factors: List[str]
    uncertainty_gaps: List[str]


class PolicyReference(BaseModel):
    """Relevant policies or procedures pulled from vector memory."""

    title: str
    excerpt: str
    source: str


class CorrectiveActionPlan(BaseModel):
    """Action plan aligned with relevant policies and root cause findings."""

    actions: List[str]
    responsible_parties: List[str]
    due_dates: List[str]
    policy_references: List[PolicyReference]


class TicketRequest(BaseModel):
    """Defines a ticket to be opened in downstream systems."""

    title: str
    description: str
    priority: Literal["low", "medium", "high", "urgent"]


class EmailRequest(BaseModel):
    """Represents an outbound notification email."""

    recipient: str
    subject: str
    body: str


class NotificationPlan(BaseModel):
    """Planned notifications (tickets + emails) derived from incident context."""

    tickets: List[TicketRequest]
    emails: List[EmailRequest]


class TicketReceipt(BaseModel):
    """Receipt for a ticket created by the notification service."""

    ticket_id: str
    status: Literal["created", "failed"]
    request: TicketRequest


class EmailReceipt(BaseModel):
    """Receipt for an email dispatch."""

    recipient: str
    status: Literal["sent", "failed"]
    request: EmailRequest
    message_id: Optional[str] = None


class NotificationResult(BaseModel):
    """Outcome of executing the notification plan."""

    plan: NotificationPlan
    tickets: List[TicketReceipt]
    emails: List[EmailReceipt]
    notes: Optional[str] = None


class IncidentWorkflowReport(BaseModel):
    """Complete end-to-end output of the incident workflow."""

    incident: IncidentReport
    intake: IntakeSummary
    triage: TriageAssessment
    root_cause: RootCauseAnalysis
    corrective_actions: CorrectiveActionPlan
    notifications: NotificationResult
    evidence: List[EvidenceItem] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

