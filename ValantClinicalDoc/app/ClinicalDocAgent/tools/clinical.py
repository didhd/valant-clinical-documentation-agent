"""Specialist sub-agents wrapped as Strands tools (agents-as-tools pattern).

Each tool below constructs a focused Agent with its own narrow system prompt
and model tier. The orchestrator (in main.py) routes work to them by name:

    get_patient_context     -> deterministic EHR lookup (no LLM)
    clinical_note_writer    -> Sonnet 4.6, drafts the structured note
    medical_coder           -> Sonnet 4.6, suggests ICD-10 + CPT
    qa_reviewer             -> Haiku 4.5, validates the final artifacts

The deterministic context tool keeps grounding facts (patient ID, diagnoses,
template hint) outside the LLM so downstream agents never have to invent them.

Reference: https://strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/
"""

from __future__ import annotations

import json
from typing import Any

from strands import Agent, tool

from fixtures import get_patient, get_transcript
from model.load import load_model

# -- Static template registry -------------------------------------------------

TEMPLATE_REGISTRY: dict[str, dict[str, Any]] = {
    "CBT": {
        "sections": [
            "Agenda",
            "Mood Check",
            "Homework Review",
            "Interventions",
            "Risk Assessment",
            "Homework Assigned",
            "Plan",
        ],
        "primary_cpt_hint": "90837",
    },
    "DAP": {
        "sections": ["Data", "Assessment", "Plan"],
        "primary_cpt_hint": "90834",
    },
    "SOAP": {
        "sections": ["Subjective", "Objective", "Assessment", "Plan"],
        "primary_cpt_hint": "90834",
    },
    "Med Management": {
        "sections": [
            "Current Medications",
            "Side Effects",
            "Efficacy",
            "Mental Status Exam",
            "Risk Assessment",
            "Assessment",
            "Plan",
        ],
        "primary_cpt_hint": "99213",
    },
}


def _select_template(session_type: str, modality: str) -> str:
    if session_type == "med_management":
        return "Med Management"
    if modality == "CBT":
        return "CBT"
    return "DAP"


# -- Specialist system prompts ------------------------------------------------

NOTE_WRITER_PROMPT = """You are a specialized behavioral-health clinical
documentation scribe. Produce a structured clinical note grounded only in the
provided transcript and patient context. Never invent clinical findings. If a
required section has no supporting evidence, write 'Not addressed this
session.' Use professional clinical language and include risk-assessment
content for any therapy or crisis encounter.

Your output is always a single JSON object whose keys are exactly the
required sections plus a 'metadata' key (template, duration_minutes,
encounter_date)."""

MEDICAL_CODER_PROMPT = """You are a specialized behavioral-health medical
coder. Suggest ICD-10 (F-codes preferred) and CPT codes from the provided
clinical note and session metadata.

Time-based psychotherapy CPT:
  90832 = 16-37 min, 90834 = 38-52 min, 90837 = >=53 min.
Add 90785 (interactive complexity) only when supported by the note.

Never invent diagnoses absent from the note. Output is JSON only:

{
  "icd10": [{"code": "...", "description": "...", "confidence": 0.0-1.0}],
  "cpt":   [{"code": "...", "description": "...", "confidence": 0.0-1.0}],
  "modifiers": [],
  "rationale": "one sentence"
}"""

QA_REVIEWER_PROMPT = """You are a specialized clinical QA reviewer for
behavioral-health documentation. Be strict.

Cross-reference every clinical claim in the note against the transcript.
Flag any content that is not directly supported. Verify the time-based CPT
matches the session duration. Verify a risk-assessment section is present.

Output JSON only:

{
  "checks": {
    "all_sections_present": true|false,
    "risk_assessment_documented": true|false,
    "time_matches_cpt": true|false,
    "no_hallucinations": true|false,
    "treatment_goals_referenced": true|false
  },
  "warnings": ["..."],
  "hallucinated_phrases": ["..."],
  "verdict": "pass" | "pass_with_warnings" | "fail"
}"""


# -- Tools --------------------------------------------------------------------


@tool
def get_patient_context(query: str) -> str:
    """Pull deterministic patient context for a documentation session.

    The orchestrator passes a JSON string with patient_id and session_type.
    This tool does not call an LLM — it returns ground-truth EHR data so
    downstream specialist agents have grounding facts they cannot invent.

    Args:
        query: JSON string like
               '{"patient_id": "P-1001", "session_type": "therapy"}'.
               session_type is optional and defaults to "therapy".

    Returns:
        JSON string with treatment_goals, previous_session_summary,
        measurements, sessions_remaining, and recommended_template.
    """
    try:
        if isinstance(query, str):
            try:
                args = json.loads(query)
            except json.JSONDecodeError:
                args = {"patient_id": query.strip()}
        else:
            args = dict(query)

        patient_id = args.get("patient_id", "").strip()
        session_type = args.get("session_type", "therapy")

        patient = get_patient(patient_id)
        if not patient:
            return json.dumps({"error": f"Patient {patient_id} not found in EHR"})

        modality = patient["treatment_plan"]["modality"]
        return json.dumps(
            {
                "patient_id": patient["patient_id"],
                "name": patient["name"],
                "diagnoses": patient["diagnoses"],
                "active_medications": patient["active_medications"],
                "treatment_goals": patient["treatment_plan"]["goals"],
                "homework_last_session": patient["treatment_plan"][
                    "homework_last_session"
                ],
                "previous_session_summary": patient["previous_session_summary"],
                "measurements": patient["measurements"],
                "sessions_remaining": patient["auth_status"]["sessions_remaining"],
                "payer": patient["auth_status"]["payer"],
                "recommended_template": _select_template(session_type, modality),
            },
            indent=2,
        )
    except Exception as exc:
        return f"Error in get_patient_context: {exc}"


@tool
def clinical_note_writer(query: str) -> str:
    """Specialist sub-agent that drafts a structured clinical note.

    Wraps a focused Strands Agent with the note-writer system prompt. The
    orchestrator passes a JSON string containing transcript_id, patient_id,
    and an optional template. This tool reads the transcript + patient
    fixtures, builds a prompt for the specialist, and returns the structured
    note as text.

    Args:
        query: JSON string like
               '{"transcript_id": "T-CBT-001", "patient_id": "P-1001",
                 "template": "CBT"}'.

    Returns:
        Structured clinical note (JSON object as a string).
    """
    try:
        args = json.loads(query) if isinstance(query, str) else dict(query)
        transcript_id = args.get("transcript_id", "").strip()
        patient_id = args.get("patient_id", "").strip()
        template_override = args.get("template")

        transcript = get_transcript(transcript_id)
        patient = get_patient(patient_id)
        if not transcript:
            return json.dumps({"error": f"Transcript {transcript_id} not found"})
        if not patient:
            return json.dumps({"error": f"Patient {patient_id} not found"})

        chosen_template = template_override or _select_template(
            transcript["session_type"], transcript["modality"]
        )
        spec = TEMPLATE_REGISTRY.get(chosen_template, TEMPLATE_REGISTRY["DAP"])

        transcript_text = "\n".join(
            f"[{u['ts']}] {u['speaker']}: {u['text']}" for u in transcript["utterances"]
        )

        note_agent = Agent(
            model=load_model("note"),
            system_prompt=NOTE_WRITER_PROMPT,
            callback_handler=None,
        )

        prompt = f"""Generate a {chosen_template} note for the session below.

PATIENT CONTEXT:
- Name: {patient['name']} (DOB {patient['dob']})
- Diagnoses: {', '.join(patient['diagnoses'])}
- Active medications: {patient['active_medications']}
- Treatment goals: {patient['treatment_plan']['goals']}
- Homework from last session: {patient['treatment_plan']['homework_last_session']}
- Latest measurements: {patient['measurements']}

SESSION METADATA:
- Date: {transcript['encounter_date']}
- Type: {transcript['session_type']} / {transcript['modality']}
- Duration: {transcript['duration_minutes']} minutes

REQUIRED SECTIONS: {spec['sections']}

TRANSCRIPT:
{transcript_text}
"""
        response = note_agent(prompt)
        return str(response)
    except Exception as exc:
        return f"Error in clinical_note_writer: {exc}"


@tool
def medical_coder(query: str) -> str:
    """Specialist sub-agent that suggests ICD-10 + CPT codes.

    Args:
        query: JSON string like
               '{"note": "<clinical note text>", "session_duration_min": 53}'.

    Returns:
        JSON string with icd10[], cpt[], modifiers[], and rationale.
    """
    try:
        args = json.loads(query) if isinstance(query, str) else dict(query)
        note_text = args.get("note", "")
        duration = int(args.get("session_duration_min", 0))

        coding_agent = Agent(
            model=load_model("coding"),
            system_prompt=MEDICAL_CODER_PROMPT,
            callback_handler=None,
        )

        prompt = f"""Session duration: {duration} minutes.

CLINICAL NOTE:
{note_text}
"""
        response = coding_agent(prompt)
        return str(response)
    except Exception as exc:
        return f"Error in medical_coder: {exc}"


@tool
def qa_reviewer(query: str) -> str:
    """Specialist sub-agent that QA-validates the note + codes.

    Args:
        query: JSON string like
               '{"note": "...", "codes": "...", "transcript_id": "T-CBT-001"}'.

    Returns:
        JSON string with check results, warnings, and verdict.
    """
    try:
        args = json.loads(query) if isinstance(query, str) else dict(query)
        note_text = args.get("note", "")
        codes_text = args.get("codes", "")
        transcript_id = args.get("transcript_id", "").strip()

        transcript = get_transcript(transcript_id)
        if not transcript:
            return json.dumps({"error": f"Transcript {transcript_id} not found"})

        transcript_text = "\n".join(
            f"{u['speaker']}: {u['text']}" for u in transcript["utterances"]
        )

        qa_agent = Agent(
            model=load_model("qa"),
            system_prompt=QA_REVIEWER_PROMPT,
            callback_handler=None,
        )

        prompt = f"""Review the note and codes for compliance.

TRANSCRIPT (source of truth):
{transcript_text}

NOTE:
{note_text}

CODES:
{codes_text}
"""
        response = qa_agent(prompt)
        return str(response)
    except Exception as exc:
        return f"Error in qa_reviewer: {exc}"
