from __future__ import annotations

from ehs_ai.agents.incident import (
    CorrectiveActionAgent,
    IntakeAgent,
    NotificationAgent,
    RootCauseAgent,
    TriageAgent,
)
from ehs_ai.schemas import IncidentReport, IncidentWorkflowReport
from ehs_ai.services.notifications import NotificationService
from ehs_ai.utils.logger import get_logger
from ehs_ai.workflow.incident_graph import IncidentWorkflowGraph

logger = get_logger(__name__)


class IncidentWorkflowService:
    """Coordinates the multi-step incident workflow across specialized agents."""

    def __init__(
        self,
        *,
        intake_agent: IntakeAgent,
        triage_agent: TriageAgent,
        root_cause_agent: RootCauseAgent,
        corrective_agent: CorrectiveActionAgent,
        notification_agent: NotificationAgent,
        notification_service: NotificationService,
    ) -> None:
        self._graph = IncidentWorkflowGraph(
            intake_agent=intake_agent,
            triage_agent=triage_agent,
            root_cause_agent=root_cause_agent,
            corrective_agent=corrective_agent,
            notification_agent=notification_agent,
            notification_service=notification_service,
        )

    async def run(self, report: IncidentReport) -> IncidentWorkflowReport:
        logger.info("Starting incident workflow for '%s'", report.title)

        report_result = await self._graph.run(report)
        if hasattr(report, "attachments") and report.attachments:
            report_result.evidence = [
                item for item in report_result.evidence
            ]  # ensure list exists

        logger.info("Completed incident workflow for '%s'", report.title)
        return report_result

