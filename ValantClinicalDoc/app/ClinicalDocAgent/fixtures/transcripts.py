"""Dummy session transcripts and patient context for the Valant clinical
documentation hackathon. Stands in for the Nova Sonic / Connect Health
transcription stage so we can iterate on the agentic pipeline end-to-end
without real audio.

Two data sources, in priority order:

  1. `valant_clinical_transcripts.json` at the repo root (or the path in
     env var VALANT_TRANSCRIPTS_JSON). Schema produced by the hackathon
     dataset:
        {"sessions": [{"session_id": "...", "filename": "...",
                       "content": "<markdown blob>"}]}
     Each markdown blob has a metadata block + a Transcript section with
     `**[ts] Speaker:**` lines.

  2. Embedded fallbacks below (T-CBT-001, T-MED-002).

Both sources populate the same `PATIENTS` and `TRANSCRIPTS` dicts that the
specialist tools query.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

# -- Embedded fallbacks ------------------------------------------------------

PATIENTS: dict[str, dict[str, Any]] = {
    "P-1001": {
        "patient_id": "P-1001",
        "name": "Jane Doe",
        "dob": "1989-03-12",
        "diagnoses": [
            "F33.1 Major depressive disorder, recurrent, moderate",
            "F41.1 Generalized anxiety disorder",
        ],
        "active_medications": [
            {"name": "Sertraline", "dose": "100 mg", "frequency": "daily"}
        ],
        "treatment_plan": {
            "modality": "CBT",
            "goals": [
                "Reduce PHQ-9 score from 16 to <10 within 12 weeks",
                "Identify and reframe at least 3 cognitive distortions per week",
                "Resume social activities at least 1x/week",
            ],
            "homework_last_session": "Daily thought record for negative automatic thoughts",
        },
        "measurements": {
            "PHQ-9": {"trend": [18, 17, 16, 16, 14], "latest": 14, "instrument": "PHQ-9"},
            "GAD-7": {"trend": [15, 14, 13, 12, 12], "latest": 12, "instrument": "GAD-7"},
        },
        "previous_session_summary": (
            "Patient reported moderate depressive symptoms, completed 5 of 7 thought "
            "records. Discussed cognitive distortion of catastrophizing related to work."
        ),
        "auth_status": {"sessions_remaining": 8, "payer": "BCBS", "auth_id": "AUTH-77231"},
        "provider_id": "DR-SMITH-12345",
    },
    "P-1002": {
        "patient_id": "P-1002",
        "name": "Marcus Lee",
        "dob": "1976-09-04",
        "diagnoses": [
            "F31.81 Bipolar II disorder, current depressed",
            "F90.0 ADHD, predominantly inattentive",
        ],
        "active_medications": [
            {"name": "Lamotrigine", "dose": "200 mg", "frequency": "daily"},
            {"name": "Bupropion XL", "dose": "300 mg", "frequency": "daily"},
        ],
        "treatment_plan": {
            "modality": "Med Management",
            "goals": [
                "Stabilize mood (no hypomanic episodes for 90 days)",
                "Improve sustained attention at work",
            ],
            "homework_last_session": "Mood + sleep log nightly",
        },
        "measurements": {
            "PHQ-9": {"trend": [12, 11, 9, 9, 8], "latest": 8, "instrument": "PHQ-9"},
        },
        "previous_session_summary": (
            "Tolerating lamotrigine well, no rash. Reported residual fatigue. "
            "Increased bupropion XL from 150mg to 300mg two weeks ago."
        ),
        "auth_status": {"sessions_remaining": 4, "payer": "Aetna", "auth_id": "AUTH-88112"},
        "provider_id": "DR-PATEL-67890",
    },
}


TRANSCRIPTS: dict[str, dict[str, Any]] = {
    "T-CBT-001": {
        "transcript_id": "T-CBT-001",
        "patient_id": "P-1001",
        "session_type": "therapy",
        "modality": "CBT",
        "duration_minutes": 53,
        "encounter_date": "2026-05-20",
        "utterances": [
            {"speaker": "CLINICIAN", "ts": "00:00:05", "text": "Hi Jane, good to see you again. How are you feeling since last week?"},
            {"speaker": "PATIENT",  "ts": "00:00:11", "text": "Honestly, kind of mixed. The mornings are still really heavy, but I noticed I had two days where I actually wanted to call my sister."},
            {"speaker": "CLINICIAN", "ts": "00:00:25", "text": "That's a meaningful shift. Did you call her?"},
            {"speaker": "PATIENT",  "ts": "00:00:29", "text": "I did, on Saturday. We talked for about an hour."},
            {"speaker": "CLINICIAN", "ts": "00:00:34", "text": "How was your mood after that conversation, on a scale of zero to ten?"},
            {"speaker": "PATIENT",  "ts": "00:00:40", "text": "Maybe a six? It dipped again Sunday morning though."},
            {"speaker": "CLINICIAN", "ts": "00:00:48", "text": "Let's look at the thought records. You filled out five of seven this week, is that right?"},
            {"speaker": "PATIENT",  "ts": "00:00:55", "text": "Yeah. The two I missed were the days I just couldn't get out of bed."},
            {"speaker": "CLINICIAN", "ts": "00:01:03", "text": "Any cognitive distortions you noticed coming up repeatedly?"},
            {"speaker": "PATIENT",  "ts": "00:01:08", "text": "Catastrophizing, mostly about work. And mind reading, like assuming my manager is annoyed with me."},
            {"speaker": "CLINICIAN", "ts": "00:01:18", "text": "Good catch. Let's pick the work catastrophizing one and walk through it. What's the situation that triggered it?"},
            {"speaker": "PATIENT",  "ts": "00:01:26", "text": "I missed a deadline by half a day and immediately thought I was going to be fired."},
            {"speaker": "CLINICIAN", "ts": "00:01:34", "text": "And the evidence for and against that thought?"},
            {"speaker": "PATIENT",  "ts": "00:01:38", "text": "Evidence for: my manager replied with just 'ok'. Evidence against: I've never been written up, I had a positive review last quarter, and other people miss deadlines too."},
            {"speaker": "CLINICIAN", "ts": "00:02:02", "text": "What's a more balanced thought?"},
            {"speaker": "PATIENT",  "ts": "00:02:08", "text": "Missing one deadline by half a day is unlikely to get me fired. My manager is probably just busy."},
            {"speaker": "CLINICIAN", "ts": "00:02:18", "text": "How do you feel saying that?"},
            {"speaker": "PATIENT",  "ts": "00:02:21", "text": "A little lighter. Maybe a seven instead of a two."},
            {"speaker": "CLINICIAN", "ts": "00:02:30", "text": "Any thoughts of self-harm or hopelessness this week?"},
            {"speaker": "PATIENT",  "ts": "00:02:36", "text": "No active thoughts. Some passive 'what's the point' moments but nothing more than that."},
            {"speaker": "CLINICIAN", "ts": "00:02:48", "text": "Okay. For homework this week, let's keep the daily thought record and add one behavioral activation: schedule one social activity, even something small."},
            {"speaker": "PATIENT",  "ts": "00:02:58", "text": "I can do coffee with my neighbor on Wednesday."},
            {"speaker": "CLINICIAN", "ts": "00:03:03", "text": "Perfect. We'll see each other next Tuesday at the same time."},
        ],
    },
    "T-MED-002": {
        "transcript_id": "T-MED-002",
        "patient_id": "P-1002",
        "session_type": "med_management",
        "modality": "Med Management",
        "duration_minutes": 22,
        "encounter_date": "2026-05-20",
        "utterances": [
            {"speaker": "CLINICIAN", "ts": "00:00:04", "text": "Marcus, how have you been doing on the higher dose of bupropion?"},
            {"speaker": "PATIENT",  "ts": "00:00:10", "text": "Energy is better. Mornings used to take me an hour to get going, now maybe fifteen minutes."},
            {"speaker": "CLINICIAN", "ts": "00:00:21", "text": "Any side effects? Sleep, appetite, headaches?"},
            {"speaker": "PATIENT",  "ts": "00:00:26", "text": "A little harder to fall asleep, but I'm taking it earlier in the day now. No headaches."},
            {"speaker": "CLINICIAN", "ts": "00:00:36", "text": "Any signs of elevated mood, racing thoughts, irritability?"},
            {"speaker": "PATIENT",  "ts": "00:00:42", "text": "No. Mood feels stable. PHQ-9 I filled out this morning was an eight."},
            {"speaker": "CLINICIAN", "ts": "00:00:53", "text": "Eight is a real improvement. Are you tolerating the lamotrigine 200mg?"},
            {"speaker": "PATIENT",  "ts": "00:00:59", "text": "Yes. No rash, no dizziness."},
            {"speaker": "CLINICIAN", "ts": "00:01:06", "text": "Okay. Plan: continue lamotrigine 200mg daily, continue bupropion XL 300mg daily. We'll check labs in three months. Any questions?"},
            {"speaker": "PATIENT",  "ts": "00:01:18", "text": "Just refills."},
            {"speaker": "CLINICIAN", "ts": "00:01:21", "text": "Sending 90-day supply for both to your pharmacy now. See you in six weeks."},
        ],
    },
}


# -- valant_clinical_transcripts.json adapter --------------------------------

# Maps the dataset's CamelCase template names to our internal modality + type.
_TEMPLATE_TYPE_MAP: dict[str, tuple[str, str]] = {
    # template_type            -> (session_type,   modality)
    "CBT_Individual":            ("therapy",        "CBT"),
    "CBT_Adolescent":            ("therapy",        "CBT"),
    "Trauma_Focused_CBT":        ("therapy",        "CBT"),
    "DBT_Individual":            ("therapy",        "DBT"),
    "DBT_Skills_Group":          ("group",          "DBT"),
    "Group_Therapy":             ("group",          "Group"),
    "EMDR":                      ("therapy",        "EMDR"),
    "Couples_Therapy":           ("therapy",        "Couples"),
    "Motivational_Interviewing": ("therapy",        "MI"),
    "Intake_Assessment":         ("intake",         "Intake"),
    "Crisis_Intervention":       ("crisis",         "Crisis"),
    "Medication_Management":     ("med_management", "Med Management"),
}


def _meta_value(content: str, label: str) -> str | None:
    m = re.search(rf"\*\*{re.escape(label)}\*\*:\s*(.+)", content)
    return m.group(1).strip() if m else None


def _parse_utterances(content: str) -> list[dict[str, str]]:
    body = content.split("## Transcript", 1)[-1]
    pat = re.compile(
        r"\*\*\[(?P<ts>\d{2}:\d{2}:\d{2})\]\s*(?P<speaker>[^:]+?):\*\*\s*(?P<text>.+?)(?=\n\n\*\*\[|\n\n\*\*\[END|\Z)",
        re.DOTALL,
    )
    out: list[dict[str, str]] = []
    for m in pat.finditer(body):
        speaker_raw = m.group("speaker").strip()
        # Heuristic: any "Dr." / "Therapist" / "Clinician" / "Doctor" → CLINICIAN.
        # Everything else (first names, "Patient", parents) → PATIENT.
        upper = speaker_raw.upper()
        is_clinician = (
            upper.startswith("DR")
            or "THERAPIST" in upper
            or "CLINICIAN" in upper
            or "DOCTOR" in upper
            or "COUNSELOR" in upper
            or "PSYCHIATRIST" in upper
        )
        out.append(
            {
                "speaker": "CLINICIAN" if is_clinician else "PATIENT",
                "ts": m.group("ts"),
                "text": " ".join(m.group("text").split()),
                "speaker_label": speaker_raw,  # keep original for display if needed
            }
        )
    return out


def _parse_diagnosis(diag: str | None) -> list[str]:
    if not diag:
        return []
    return [d.strip() for d in re.split(r";\s*|\s*,\s*(?=[A-Z]\d)", diag) if d.strip()]


def _to_minutes(duration_str: str | None) -> int:
    if not duration_str:
        return 0
    m = re.search(r"(\d+)", duration_str)
    return int(m.group(1)) if m else 0


def _build_overlay_from_dataset(data: dict[str, Any]) -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[str, Any]]
]:
    patients: dict[str, dict[str, Any]] = {}
    transcripts: dict[str, dict[str, Any]] = {}

    for s in data.get("sessions", []):
        content = s.get("content", "")
        sid = s.get("session_id") or _meta_value(content, "Session ID") or ""
        if not sid:
            continue

        template_type = _meta_value(content, "Template Type") or ""
        session_type, modality = _TEMPLATE_TYPE_MAP.get(
            template_type, ("therapy", template_type or "Unknown")
        )
        cpt_code = _meta_value(content, "CPT Code") or ""
        clinician = _meta_value(content, "Clinician") or ""
        patient_name = _meta_value(content, "Patient") or "Unknown Patient"
        patient_age = _meta_value(content, "Patient Age") or ""
        diagnosis_raw = _meta_value(content, "Diagnosis")
        date = _meta_value(content, "Date") or ""
        duration_min = _to_minutes(_meta_value(content, "Duration"))
        presenting_concern = _meta_value(content, "Presenting Concern") or ""
        session_number = _meta_value(content, "Session Number") or ""

        # Synthesise stable-ish patient_id from the name so the same patient
        # (e.g., "Marcus Williams") collapses into one record across sessions.
        slug = re.sub(r"[^a-z0-9]+", "-", patient_name.lower()).strip("-") or sid
        patient_id = f"P-{slug}"
        transcript_id = f"T-{sid.replace('session_', '').upper() or sid.upper()}"

        utterances = _parse_utterances(content)

        patient = patients.setdefault(
            patient_id,
            {
                "patient_id": patient_id,
                "name": patient_name,
                "dob": "",
                "age": patient_age,
                "diagnoses": _parse_diagnosis(diagnosis_raw),
                "active_medications": [],
                "treatment_plan": {
                    "modality": modality,
                    "goals": [presenting_concern] if presenting_concern else [],
                    "homework_last_session": "",
                },
                "measurements": {},
                "previous_session_summary": "",
                "auth_status": {
                    "sessions_remaining": 6,
                    "payer": "Unknown",
                    "auth_id": f"AUTH-{slug}",
                },
                "provider_id": clinician or "Unknown",
            },
        )
        # If multiple sessions share a patient, keep the latest session-derived
        # treatment_plan/notes but accumulate diagnoses.
        for d in _parse_diagnosis(diagnosis_raw):
            if d not in patient["diagnoses"]:
                patient["diagnoses"].append(d)
        patient["last_session_number"] = session_number

        transcripts[transcript_id] = {
            "transcript_id": transcript_id,
            "patient_id": patient_id,
            "session_type": session_type,
            "modality": modality,
            "duration_minutes": duration_min,
            "encounter_date": date,
            "template_type": template_type,
            "cpt_code_documented": cpt_code,
            "clinician": clinician,
            "presenting_concern": presenting_concern,
            "session_number": session_number,
            "utterances": utterances,
        }

    return patients, transcripts


def _candidate_json_paths() -> list[Path]:
    here = Path(__file__).resolve()
    # here = .../valant/ValantClinicalDoc/app/ClinicalDocAgent/fixtures/transcripts.py
    # parents[0]=fixtures, [1]=ClinicalDocAgent, [2]=app, [3]=ValantClinicalDoc, [4]=valant (repo root)
    return [
        here.parents[4] / "valant_clinical_transcripts.json",  # repo root
        here.parents[3] / "valant_clinical_transcripts.json",  # ValantClinicalDoc/
        Path.cwd() / "valant_clinical_transcripts.json",
    ]


def _load_overlay() -> None:
    """If the dataset JSON is found, parse and merge it on top of the embedded
    fixtures. Honours VALANT_TRANSCRIPTS_JSON env var as an override path.
    Logs to stdout (no failures) so dev keeps running with embedded data when
    the file is missing or malformed.
    """
    env_path = os.environ.get("VALANT_TRANSCRIPTS_JSON")
    paths = [Path(env_path)] if env_path else _candidate_json_paths()

    for path in paths:
        if not path or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text())
        except Exception as exc:  # pragma: no cover - resilient
            print(f"[fixtures] Skipping {path}: {exc}")
            continue

        # Two accepted shapes:
        # (a) {"patients": {...}, "transcripts": {...}}  — pre-parsed
        # (b) {"sessions": [{"session_id", "content"}]}  — markdown blobs
        if isinstance(data.get("patients"), dict) or isinstance(
            data.get("transcripts"), dict
        ):
            if isinstance(data.get("patients"), dict):
                PATIENTS.update(data["patients"])
            if isinstance(data.get("transcripts"), dict):
                TRANSCRIPTS.update(data["transcripts"])
        elif isinstance(data.get("sessions"), list):
            patients, transcripts = _build_overlay_from_dataset(data)
            PATIENTS.update(patients)
            TRANSCRIPTS.update(transcripts)
        else:
            print(f"[fixtures] {path} has no recognised shape; skipping")
            continue

        print(
            f"[fixtures] Loaded overlay from {path.name} "
            f"(patients={len(PATIENTS)}, transcripts={len(TRANSCRIPTS)})"
        )
        return


_load_overlay()


def get_transcript(transcript_id: str) -> dict[str, Any] | None:
    return TRANSCRIPTS.get(transcript_id)


def get_patient(patient_id: str) -> dict[str, Any] | None:
    return PATIENTS.get(patient_id)
