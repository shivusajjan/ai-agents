from __future__ import annotations

from typing import List

from pydantic_ai import Agent as PydanticAgent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from ehs_ai.config import get_settings
from ehs_ai.schemas import (
    CorrectiveActionPlan,
    IncidentReport,
    IntakeSummary,
    NotificationPlan,
    PolicyReference,
    RootCauseAnalysis,
    TriageAssessment,
)
from ehs_ai.utils.logger import get_logger
from ehs_ai.vector.memory import VectorMemory

logger = get_logger(__name__)


def _get_model() -> OpenAIChatModel:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY must be set for incident workflow agents.")
    provider = OpenAIProvider(api_key=settings.openai_api_key)
    return OpenAIChatModel(model_name=settings.openai_model, provider=provider)


class IntakeAgent:
    """Analyzes raw incident reports to produce structured intake summaries."""

    def __init__(self) -> None:
        self._agent = PydanticAgent(model=_get_model(), output_type=IntakeSummary)

        @self._agent.system_prompt
        def _system_prompt(_ctx: RunContext[IntakeSummary]) -> str:
            return (
                "You are an incident intake specialist for an Environmental Health & Safety team. "
                "Summarize the report clearly, highlight key findings, note any injuries, and assign "
                "a severity based on the description."
            )

    async def process(self, report: IncidentReport) -> IntakeSummary:
        prompt = (
            "Process the following incident report and produce an intake summary."
            f"\n\nTitle: {report.title}"
            f"\nReported By: {report.reported_by or 'Unknown'}"
            f"\nLocation: {report.location or 'Not specified'}"
            f"\nTime: {report.time_of_incident or 'Not specified'}"
            f"\nIndividuals Involved: {', '.join(report.individuals_involved) or 'Not listed'}"
            f"\nSeverity Hint: {report.severity_hint or 'None'}"
            f"\nDescription:\n{report.description}"
        )
        result = await self._agent.run(prompt)
        return result.output


class TriageAgent:
    """Determines urgency, escalation paths, and immediate containment steps."""

    def __init__(self) -> None:
        self._agent = PydanticAgent(model=_get_model(), output_type=TriageAssessment)

        @self._agent.system_prompt
        def _system_prompt(_ctx: RunContext[TriageAssessment]) -> str:
            return (
                "You are an EHS triage officer. Based on the incident summary, "
                "determine the risk level, immediate actions, escalation requirements, "
                "and monitoring plan. Justify your recommendations."
            )

    async def assess(self, report: IncidentReport, intake: IntakeSummary) -> TriageAssessment:
        prompt = (
            "Perform triage on the incident using the following context."
            f"\n\nIncident title: {report.title}"
            f"\nSeverity hint: {report.severity_hint or 'None'}"
            f"\nIntake summary: {intake.narrative}"
            f"\nKey findings: {', '.join(intake.key_findings)}"
            f"\nInjuries or illnesses: {', '.join(intake.injuries_or_illnesses) or 'None'}"
        )
        result = await self._agent.run(prompt)
        return result.output


class RootCauseAgent:
    """Explores potential root causes and contributing factors."""

    def __init__(self) -> None:
        self._agent = PydanticAgent(model=_get_model(), output_type=RootCauseAnalysis)

        @self._agent.system_prompt
        def _system_prompt(_ctx: RunContext[RootCauseAnalysis]) -> str:
            return (
                "You are a root cause analyst for EHS incidents. Provide plausible causes "
                "and contributing factors. Highlight any gaps requiring further investigation."
            )

    async def analyse(
        self, report: IncidentReport, intake: IntakeSummary, triage: TriageAssessment
    ) -> RootCauseAnalysis:
        prompt = (
            "Analyse root causes using the following inputs."
            f"\n\nDescription: {report.description}"
            f"\nIntake summary: {intake.narrative}"
            f"\nTriage rationale: {triage.rationale}"
            f"\nImmediate actions: {', '.join(triage.priority_actions)}"
        )
        result = await self._agent.run(prompt)
        return result.output


class CorrectiveActionAgent:
    """Produces policy-aligned corrective actions leveraging vector memory."""

    def __init__(self, *, vector_memory: VectorMemory) -> None:
        self._agent = PydanticAgent(model=_get_model(), output_type=CorrectiveActionPlan)
        self._memory = vector_memory

        @self._agent.system_prompt
        def _system_prompt(_ctx: RunContext[CorrectiveActionPlan]) -> str:
            return (
                "You are responsible for proposing corrective actions after an EHS incident. "
                "Outline actionable steps with responsible parties, target due dates, and cite "
                "relevant policies or procedures."
            )

    async def plan(
        self,
        report: IncidentReport,
        intake: IntakeSummary,
        triage: TriageAssessment,
        root_cause: RootCauseAnalysis,
    ) -> CorrectiveActionPlan:
        policy_matches = self._memory.query(
            text=f"{report.description}\n{intake.narrative}\n{','.join(root_cause.primary_causes)}",
            n_results=4,
        )
        policy_context = "\n".join(
            f"- {item['metadata'].get('tag', 'policy')}: {item['document']}"
            for item in policy_matches
        )
        prompt = (
            "Develop a corrective action plan."
            f"\n\nIncident summary: {intake.narrative}"
            f"\nRoot causes: {', '.join(root_cause.primary_causes)}"
            f"\nContributing factors: {', '.join(root_cause.contributing_factors) or 'None'}"
            f"\nTriage actions already underway: {', '.join(triage.priority_actions)}"
            f"\nRelevant policies:\n{policy_context or 'No policies found. Base recommendations on best practice.'}"
        )
        result = await self._agent.run(prompt)
        plan = result.output
        # Enrich policy references to include explicit metadata.
        enriched_refs: List[PolicyReference] = []
        for ref in plan.policy_references:
            enriched_refs.append(ref)
        plan.policy_references = enriched_refs
        return plan


class NotificationAgent:
    """Determines which stakeholders to notify and which artifacts to create."""

    def __init__(self) -> None:
        self._agent = PydanticAgent(model=_get_model(), output_type=NotificationPlan)

        @self._agent.system_prompt
        def _system_prompt(_ctx: RunContext[NotificationPlan]) -> str:
            return (
                "You coordinate incident communications. Decide which tickets to create and "
                "who to email, ensuring compliance with escalation protocol and data privacy guidelines."
            )

    async def plan(
        self,
        report: IncidentReport,
        intake: IntakeSummary,
        triage: TriageAssessment,
        corrective_actions: CorrectiveActionPlan,
    ) -> NotificationPlan:
        prompt = (
            "Create a notification plan for the incident."
            f"\n\nIncident title: {report.title}"
            f"\nLocation: {report.location or 'Not specified'}"
            f"\nSeverity: {intake.severity}"
            f"\nTriage risk level: {triage.risk_level}"
            f"\nKey actions: {', '.join(corrective_actions.actions)}"
            f"\nResponsible parties: {', '.join(corrective_actions.responsible_parties)}"
        )
        result = await self._agent.run(prompt)
        return result.output

