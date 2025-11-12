# EHS Safety Assistant

Environmental Health & Safety decision-support service powered entirely by [pydantic-ai](https://docs.pydantic.dev/latest/ai/).  
The platform orchestrates a multi-agent incident workflow that automates intake, triage, root cause analysis, corrective actions, and stakeholder notifications.

## Features

- **Incident workflow orchestration**: LangGraph coordinates intake, triage, root cause, corrective actions, and notifications executed by specialised pydantic-ai agents.
- **Vector-backed policy retrieval**: ChromaDB + SentenceTransformers seed policies used to ground corrective action plans.
- **Automated ticket & email stubs**: Workflow produces ticket/email plans and simulates execution (ready to swap for real integrations).
- **Structured results**: Every step returns strongly typed Pydantic models, ensuring reliable downstream automation.

## Quick Start

1. **Install dependencies**

   ```bash
   python3 -m venv .venv
   source venv/bin/activate
   pip install -e .
   ```

2. **Configure environment**

   ```bash
   cp env.example .env
   # Edit .env and set OPENAI_API_KEY=<your key>
   ```

3. **Run the API**

   ```bash
   uvicorn ehs_ai.main:app --reload
   ```

4. **Execute the incident workflow**

   ```bash
   curl -X POST http://127.0.0.1:8000/incident-workflow \
        -F 'incident={
              "title": "Forklift struck a pallet in aisle 7",
              "description": "Operator reported limited visibility due to stacked crates. One contractor sustained a minor ankle strain.",
              "reported_by": "Maria Gomez",
              "severity_hint": "medium",
              "location": "Warehouse Aisle 7",
              "time_of_incident": "2025-11-11T09:35:00",
              "individuals_involved": ["Operator 2145", "Contractor 8821"]
            }' \
        -F message='Operator noted blocked sightlines near loading bay.' \
        -F evidence=@/Users/shivakumar/Downloads/my_photo.jpeg \
        -o incident_report.pdf
   
   
     curl -X POST http://127.0.0.1:8000/incident-workflow \
        -F evidence=@/path/test-incident.jpg \
        -o incident_report.pdf
   ```

   You can omit `incident` and send only `message`+evidence (or evidence alone); the service will synthesize a report narrative from the uploaded files and vision analysis. Every uploaded file appears in the PDF with object/hazard insights.

5. **Retrieve stored evidence (optional)**

   ```bash
   curl -O http://127.0.0.1:8000/evidence/<incident_id>/<filename>
   ```

## Project Layout

- `ehs_ai/agents/incident.py` – specialised pydantic-ai agents for incident intake, triage, root cause, corrective action, and notifications.
- `ehs_ai/workflow/incident_graph.py` – LangGraph definition of the incident workflow.
- `ehs_ai/services/incident_workflow.py` – thin service wrapper around the LangGraph runtime.
- `ehs_ai/services/notifications.py` – ticket/email execution stubs.
- `ehs_ai/vector/memory.py` – ChromaDB-backed policy memory with seed documents.
- `ehs_ai/schemas.py` – Pydantic request/response models.
- `ehs_ai/main.py` – FastAPI wiring and endpoints.

## Development Notes
- Requires Python 3.11+.

## Draw langgraph workflow:  langgraph UI is not working to render workflow diagram, need to troubleshoot
```
langgraph dev --config langgraph.json --port 20202
```