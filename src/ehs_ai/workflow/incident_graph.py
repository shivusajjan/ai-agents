from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph

from ehs_ai.agents.incident import (
    CorrectiveActionAgent,
    IntakeAgent,
    NotificationAgent,
    RootCauseAgent,
    TriageAgent,
)
from ehs_ai.schemas import (
    CorrectiveActionPlan,
    IncidentReport,
    IncidentWorkflowReport,
    IntakeSummary,
    NotificationResult,
    RootCauseAnalysis,
    TriageAssessment,
)
from ehs_ai.services.notifications import NotificationService
from ehs_ai.vector.memory import VectorMemory


class IncidentState(TypedDict, total=False):
    """Runtime state shared across LangGraph nodes."""

    report: IncidentReport
    intake: IntakeSummary
    triage: TriageAssessment
    root_cause: RootCauseAnalysis
    corrective_actions: CorrectiveActionPlan
    notifications: NotificationResult


class IncidentWorkflowGraph:
    """LangGraph implementation of the incident workflow."""

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
        self._intake_agent = intake_agent
        self._triage_agent = triage_agent
        self._root_cause_agent = root_cause_agent
        self._corrective_agent = corrective_agent
        self._notification_agent = notification_agent
        self._notification_service = notification_service
        self._graph = self._build_graph()

    async def run(self, report: IncidentReport) -> IncidentWorkflowReport:
        initial_state: IncidentState = {"report": report}
        final_state = await self._graph.ainvoke(initial_state)
        return IncidentWorkflowReport(
            incident=report,
            intake=final_state["intake"],
            triage=final_state["triage"],
            root_cause=final_state["root_cause"],
            corrective_actions=final_state["corrective_actions"],
            notifications=final_state["notifications"],
        )

    def _build_graph(self):
        graph = StateGraph(IncidentState)
        graph.add_node("intake", self._intake_node)
        graph.add_node("triage", self._triage_node)
        graph.add_node("root_cause", self._root_cause_node)
        graph.add_node("corrective", self._corrective_node)
        graph.add_node("notify", self._notify_node)

        graph.add_edge("intake", "triage")
        graph.add_edge("triage", "root_cause")
        graph.add_edge("root_cause", "corrective")
        graph.add_edge("corrective", "notify")
        graph.add_edge("notify", END)

        graph.set_entry_point("intake")
        return graph.compile()

    async def _intake_node(self, state: IncidentState) -> IncidentState:
        report = state["report"]
        intake = await self._intake_agent.process(report)
        return {"intake": intake}

    async def _triage_node(self, state: IncidentState) -> IncidentState:
        report = state["report"]
        intake = state["intake"]
        triage = await self._triage_agent.assess(report, intake)
        return {"triage": triage}

    async def _root_cause_node(self, state: IncidentState) -> IncidentState:
        report = state["report"]
        intake = state["intake"]
        triage = state["triage"]
        root_cause = await self._root_cause_agent.analyse(report, intake, triage)
        return {"root_cause": root_cause}

    async def _corrective_node(self, state: IncidentState) -> IncidentState:
        report = state["report"]
        intake = state["intake"]
        triage = state["triage"]
        root_cause = state["root_cause"]
        corrective_actions = await self._corrective_agent.plan(report, intake, triage, root_cause)
        return {"corrective_actions": corrective_actions}

    async def _notify_node(self, state: IncidentState) -> IncidentState:
        report = state["report"]
        intake = state["intake"]
        triage = state["triage"]
        corrective_actions = state["corrective_actions"]
        notification_plan = await self._notification_agent.plan(
            report, intake, triage, corrective_actions
        )
        notifications = await self._notification_service.execute(notification_plan)
        return {"notifications": notifications}


def compile_graph() -> StateGraph:
    graph_instance = IncidentWorkflowGraph(
        intake_agent=IntakeAgent(),
        triage_agent=TriageAgent(),
        root_cause_agent=RootCauseAgent(),
        corrective_agent=CorrectiveActionAgent(vector_memory=VectorMemory()),
        notification_agent=NotificationAgent(),
        notification_service=NotificationService(),
    )
    return graph_instance._graph


