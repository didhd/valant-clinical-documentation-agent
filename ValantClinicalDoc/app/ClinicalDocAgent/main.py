"""Valant Clinical Documentation Agent — orchestrator.

Option B from the solution architecture (Custom Agentic Pipeline on AgentCore +
Strands), with the transcription stage skipped. We feed dummy transcripts from
the fixtures module and let the orchestrator coordinate context retrieval,
note generation, coding, and QA validation.
"""

import os
from typing import Any

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from strands import Agent

from fixtures import PATIENTS, TRANSCRIPTS
from model.load import load_model
from tools import (
    clinical_note_writer,
    get_patient_context,
    medical_coder,
    qa_reviewer,
)

app = BedrockAgentCoreApp()
log = app.logger

# CORS so the Vite dev server (5173) can call us during the hackathon.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


SYSTEM_PROMPT = """You are the Valant Clinical Documentation Orchestrator.
You route work to specialist sub-agents (each exposed as a tool) and assemble
their outputs into a final, sign-off-ready clinical artifact bundle.

Routing rules:
  - For pulling patient EHR context (treatment plan, PHQ-9/GAD-7 trends,
    sessions remaining, recommended template) -> use get_patient_context.
  - For drafting the structured clinical note from a transcript ->
    use clinical_note_writer.
  - For suggesting ICD-10 + CPT codes from the drafted note ->
    use medical_coder.
  - For QA validation of the note + codes against the transcript ->
    use qa_reviewer.
  - For trivial questions about the workflow -> answer directly.

Always select the most appropriate tool based on the user's request. Each
specialist tool accepts a single JSON-string argument named `query`. Pass
arguments as a JSON object string, for example:
  get_patient_context(query='{"patient_id": "P-1001", "session_type": "therapy"}')
  clinical_note_writer(query='{"transcript_id": "T-CBT-001", "patient_id": "P-1001"}')
  medical_coder(query='{"note": "...", "session_duration_min": 53}')
  qa_reviewer(query='{"note": "...", "codes": "...", "transcript_id": "T-CBT-001"}')

When the user asks for the full pipeline, run the tools in this order:
  1. get_patient_context  (resolve template + grounding facts)
  2. clinical_note_writer (draft the note in the recommended template)
  3. medical_coder        (codes from the drafted note + duration)
  4. qa_reviewer          (validate note + codes against transcript)

Hard rules:
  - Never fabricate clinical content. If the transcript does not support a
    statement, omit it or say "Not addressed this session."
  - Always require a risk-assessment section for therapy and crisis sessions.
  - Confirm with the clinician before any EHR write-back step.
  - Be concise. No filler text. Go straight to action.
  - Never use emojis in your output.
  - If you recall any user preferences from memory (injected in your context
    by the memory session manager), acknowledge them visibly at the start of
    your response with a line like:
      > Recalled preference: <what you remembered>
    This helps the clinician see that memory is working.
  - If the user asks you to remember something, confirm with:
      > Stored: <what will be remembered next session>
  - After calling each tool, IMMEDIATELY present its result in markdown
    with a clear header. Do not wait until all tools finish. Stream as you go:
      ## Clinical Note
      <paste note result here>
      ## Suggested Codes
      <paste codes here>
      ## QA Verdict
      <paste QA result here>
      ## Recommendation
      <one-line: "ready for sign-off" or "needs clinician edit: <reason>">
  - Do NOT add commentary between sections. Just the headers and content.

Available demo data:
  - Transcript T-CBT-001 (CBT therapy, patient P-1001, 53 min)
  - Transcript T-MED-002 (med management, patient P-1002, 22 min)
"""


# -- Memory ------------------------------------------------------------------
# AgentCore Memory is wired in only if MEMORY_ID is set in the environment so
# `agentcore dev` works locally without provisioning a memory resource. To
# enable: `agentcore add` -> Memory -> User preference, then redeploy.

def _build_session_manager(session_id: str | None):
    memory_id = os.environ.get("MEMORY_ID")
    if not memory_id or not session_id:
        return None
    try:
        from bedrock_agentcore.memory.integrations.strands.config import (
            AgentCoreMemoryConfig,
            RetrievalConfig,
        )
        from bedrock_agentcore.memory.integrations.strands.session_manager import (
            AgentCoreMemorySessionManager,
        )
    except ImportError:
        log.warning("bedrock_agentcore memory integration unavailable; "
                    "skipping memory wiring. Install with: "
                    "pip install 'bedrock-agentcore[strands-agents]'")
        return None

    region = os.environ.get("AWS_REGION", "us-west-2")
    actor_id = os.environ.get("ACTOR_ID", "clinician")

    config = AgentCoreMemoryConfig(
        memory_id=memory_id,
        session_id=session_id,
        actor_id=actor_id,
        retrieval_config={
            f"/users/{actor_id}/preferences": RetrievalConfig(
                top_k=5,
                relevance_score=0.3,
            ),
        },
    )
    try:
        return AgentCoreMemorySessionManager(
            agentcore_memory_config=config,
            region_name=region,
        )
    except Exception as exc:  # pragma: no cover - resilient stub
        log.warning("Failed to build memory session manager: %s", exc)
        return None


TOOLS = [
    get_patient_context,
    clinical_note_writer,
    medical_coder,
    qa_reviewer,
]


def _build_agent(session_id: str | None) -> Agent:
    return Agent(
        model=load_model("orchestrator"),
        system_prompt=SYSTEM_PROMPT,
        tools=TOOLS,
        session_manager=_build_session_manager(session_id),
    )


# -- Read-only data routes for the UI ---------------------------------------
# These don't invoke Bedrock. They let the Cloudscape UI populate its
# transcript picker and patient panel without spending model tokens.

async def list_transcripts(request: Request) -> JSONResponse:
    items = []
    for tid, t in TRANSCRIPTS.items():
        patient = PATIENTS.get(t["patient_id"], {})
        items.append({
            "transcript_id": tid,
            "patient_id": t["patient_id"],
            "patient_name": patient.get("name", ""),
            "session_type": t["session_type"],
            "modality": t["modality"],
            "duration_minutes": t["duration_minutes"],
            "encounter_date": t["encounter_date"],
            "utterance_count": len(t["utterances"]),
        })
    return JSONResponse({"transcripts": items})


async def get_transcript_detail(request: Request) -> JSONResponse:
    tid = request.path_params["transcript_id"]
    transcript = TRANSCRIPTS.get(tid)
    if not transcript:
        return JSONResponse({"error": f"Transcript {tid} not found"}, status_code=404)
    patient = PATIENTS.get(transcript["patient_id"])
    return JSONResponse({"transcript": transcript, "patient": patient})


app.add_route("/transcripts", list_transcripts, methods=["GET"])
app.add_route("/transcripts/{transcript_id}", get_transcript_detail, methods=["GET"])


# -- Agent entrypoint --------------------------------------------------------

@app.entrypoint
async def invoke(payload: dict[str, Any], context):
    log.info("ClinicalDocAgent invoked")
    prompt = payload.get("prompt") or payload.get("input") or ""
    if not prompt:
        yield "No prompt provided. Try: 'Document session T-CBT-001 for patient P-1001.'"
        return

    # In deployed AgentCore Runtime, context provides session_id.
    # Locally (python main.py), fall back to a payload field or a stable default
    # so memory works across requests within the same dev server lifetime.
    session_id = (
        getattr(context, "session_id", None)
        or payload.get("session_id")
        or "local-dev-session"
    )
    agent = _build_agent(session_id)

    stream = agent.stream_async(prompt)
    last_tool: str | None = None
    async for event in stream:
        if not isinstance(event, dict):
            continue

        # Detect tool use start from the raw Bedrock event structure.
        raw = event.get("event")
        if isinstance(raw, dict):
            cbs = raw.get("contentBlockStart", {}).get("start", {})
            if "toolUse" in cbs:
                name = cbs["toolUse"].get("name") or "unknown"
                if name != last_tool:
                    yield f"\n[tool] {name}\n"
                    last_tool = name
                continue

        # Also detect via the higher-level key Strands adds in some versions.
        tool_use = event.get("current_tool_use")
        if tool_use:
            name = tool_use.get("name") or "unknown"
            if name != last_tool:
                yield f"\n[tool] {name}\n"
                last_tool = name
            continue

        # Stream text deltas — the "data" key is the text content.
        if "data" in event and isinstance(event["data"], str):
            last_tool = None
            yield event["data"]


if __name__ == "__main__":
    app.run()
