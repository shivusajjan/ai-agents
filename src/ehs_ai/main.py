from __future__ import annotations

from io import BytesIO
import uuid
import asyncio

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse

from pydantic import ValidationError

from ehs_ai.agents.incident import (
    CorrectiveActionAgent,
    IntakeAgent,
    NotificationAgent,
    RootCauseAgent,
    TriageAgent,
)
from ehs_ai.config import get_settings
from ehs_ai.reporting.pdf import generate_incident_pdf
from ehs_ai.schemas import IncidentReport, IncidentWorkflowReport
from ehs_ai.services.evidence import EvidenceStorage
from ehs_ai.services.evidence_analyzer import EvidenceAnalyzer
from ehs_ai.services.incident_workflow import IncidentWorkflowService
from ehs_ai.services.notifications import NotificationService
from ehs_ai.utils.logger import get_logger
from ehs_ai.vector.memory import VectorMemory

logger = get_logger(__name__)

settings = get_settings()
vector_memory = VectorMemory()
vector_memory.ensure_seed_documents()

evidence_storage = EvidenceStorage()
evidence_analyzer = EvidenceAnalyzer()

app = FastAPI(title="EHS Incident Assistant", version="0.3.2")
incident_workflow_service = IncidentWorkflowService(
    intake_agent=IntakeAgent(),
    triage_agent=TriageAgent(),
    root_cause_agent=RootCauseAgent(),
    corrective_agent=CorrectiveActionAgent(vector_memory=vector_memory),
    notification_agent=NotificationAgent(),
    notification_service=NotificationService(),
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "environment": settings.environment}


@app.post("/incident-workflow", response_class=StreamingResponse)
async def incident_workflow(
    incident: str | None = Form(
        default=None, description="Optional JSON-encoded IncidentReport payload"
    ),
    message: str | None = Form(default=None, description="Optional free-form incident message"),
    evidence: list[UploadFile] = File(
        default_factory=list, description="Optional incident evidence files"
    ),
) -> StreamingResponse:
    if incident is None and message is None and not evidence:
        raise HTTPException(status_code=400, detail="Provide an incident payload, message, or evidence.")

    report = await _prepare_incident_report(incident_json=incident, message=message)

    incident_id = uuid.uuid4().hex
    saved_records = await evidence_storage.save(incident_id=incident_id, files=evidence)

    evidence_items = []
    analyses = []
    if saved_records:
        analysis_tasks = []
        for item, rel_name in saved_records:
            path = evidence_storage.resolve(incident_id, rel_name)
            evidence_items.append((item, path))
            analysis_tasks.append(asyncio.create_task(evidence_analyzer.analyse(path)))
        analyses = await asyncio.gather(*analysis_tasks, return_exceptions=True)
        for (item, _), analysis in zip(evidence_items, analyses, strict=False):
            item.analysis = analysis if isinstance(analysis, str) else "Analysis failed."

    evidence_models = [item for item, _ in evidence_items]
    if evidence_models:
        report.attachments = [evidence.url for evidence in evidence_models]
        summary_lines = [item.analysis for item in evidence_models if item.analysis]
        if summary_lines:
            summary = "\n".join(summary_lines)
            report.description = f"{report.description}\n\nEvidence Insights:\n{summary}".strip()

    try:
        result: IncidentWorkflowReport = await incident_workflow_service.run(report)
    except Exception as exc:  # pylint: disable=broad-except
        logger.exception("Incident workflow execution failed: %s", exc)
        raise HTTPException(status_code=500, detail="Incident workflow failed.") from exc

    result.evidence = evidence_models

    pdf_bytes = generate_incident_pdf(result)
    headers = {
        "Content-Disposition": f'attachment; filename="incident_{result.incident.title[:20].replace(" ", "_")}.pdf"',
        "X-Triage-Risk": result.triage.risk_level,
        "X-Incident-Title": result.incident.title,
    }
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


async def _prepare_incident_report(
    *, incident_json: str | None, message: str | None
) -> IncidentReport:
    if incident_json:
        try:
            return IncidentReport.model_validate_json(incident_json)
        except ValidationError as exc:  # pylint: disable=broad-except
            logger.exception("Invalid incident payload: %s", exc)
            raise HTTPException(status_code=400, detail="Invalid incident payload.") from exc

    message_text = (message or "").strip()
    if not message_text:
        message_text = "Evidence submitted without accompanying narrative."
    title = message_text.splitlines()[0][:80] if message_text else "Evidence Submission"
    return IncidentReport(title=title or "Evidence Submission", description=message_text)


@app.get("/evidence/{incident_id}/{filename}")
async def get_evidence(incident_id: str, filename: str) -> FileResponse:
    path = evidence_storage.resolve(incident_id, filename)
    try:
        path.relative_to(evidence_storage.root)
    except ValueError as exc:  # pragma: no cover
        logger.warning("Attempt to access evidence outside root: %s", path)
        raise HTTPException(status_code=404, detail="Evidence not found") from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Evidence not found")
    return FileResponse(path)


