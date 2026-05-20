"""Dummy session transcripts and patient context for the Valant clinical
documentation hackathon. Stands in for the Nova Sonic / Connect Health
transcription stage so we can iterate on the agentic pipeline end-to-end
without real audio.

If `valant_clinical_transcripts.json` exists at the repo root, it is loaded
and merged on top of the embedded fixtures. Expected schema:

  {
    "patients":    {"<patient_id>": {...patient fields...}, ...},
    "transcripts": {"<transcript_id>": {...transcript fields...}, ...}
  }

Patient and transcript field shapes match the embedded examples below.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PATIENTS: dict[str, dict[str, Any]] = {
    "P-1001": {
        "patient_id": "P-1001",
        "name": "Jane Doe",
        "dob": "1989-03-12",
        "diagnoses": ["F33.1 Major depressive disorder, recurrent, moderate",
                      "F41.1 Generalized anxiety disorder"],
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
        "diagnoses": ["F31.81 Bipolar II disorder, current depressed",
                      "F90.0 ADHD, predominantly inattentive"],
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
            {"speaker": "PATIENT", "ts": "00:00:11", "text": "Honestly, kind of mixed. The mornings are still really heavy, but I noticed I had two days where I actually wanted to call my sister."},
            {"speaker": "CLINICIAN", "ts": "00:00:25", "text": "That's a meaningful shift. Did you call her?"},
            {"speaker": "PATIENT", "ts": "00:00:29", "text": "I did, on Saturday. We talked for about an hour."},
            {"speaker": "CLINICIAN", "ts": "00:00:34", "text": "How was your mood after that conversation, on a scale of zero to ten?"},
            {"speaker": "PATIENT", "ts": "00:00:40", "text": "Maybe a six? It dipped again Sunday morning though."},
            {"speaker": "CLINICIAN", "ts": "00:00:48", "text": "Let's look at the thought records. You filled out five of seven this week, is that right?"},
            {"speaker": "PATIENT", "ts": "00:00:55", "text": "Yeah. The two I missed were the days I just couldn't get out of bed."},
            {"speaker": "CLINICIAN", "ts": "00:01:03", "text": "Any cognitive distortions you noticed coming up repeatedly?"},
            {"speaker": "PATIENT", "ts": "00:01:08", "text": "Catastrophizing, mostly about work. And mind reading, like assuming my manager is annoyed with me."},
            {"speaker": "CLINICIAN", "ts": "00:01:18", "text": "Good catch. Let's pick the work catastrophizing one and walk through it. What's the situation that triggered it?"},
            {"speaker": "PATIENT", "ts": "00:01:26", "text": "I missed a deadline by half a day and immediately thought I was going to be fired."},
            {"speaker": "CLINICIAN", "ts": "00:01:34", "text": "And the evidence for and against that thought?"},
            {"speaker": "PATIENT", "ts": "00:01:38", "text": "Evidence for: my manager replied with just 'ok'. Evidence against: I've never been written up, I had a positive review last quarter, and other people miss deadlines too."},
            {"speaker": "CLINICIAN", "ts": "00:02:02", "text": "What's a more balanced thought?"},
            {"speaker": "PATIENT", "ts": "00:02:08", "text": "Missing one deadline by half a day is unlikely to get me fired. My manager is probably just busy."},
            {"speaker": "CLINICIAN", "ts": "00:02:18", "text": "How do you feel saying that?"},
            {"speaker": "PATIENT", "ts": "00:02:21", "text": "A little lighter. Maybe a seven instead of a two."},
            {"speaker": "CLINICIAN", "ts": "00:02:30", "text": "Any thoughts of self-harm or hopelessness this week?"},
            {"speaker": "PATIENT", "ts": "00:02:36", "text": "No active thoughts. Some passive 'what's the point' moments but nothing more than that."},
            {"speaker": "CLINICIAN", "ts": "00:02:48", "text": "Okay. For homework this week, let's keep the daily thought record and add one behavioral activation: schedule one social activity, even something small."},
            {"speaker": "PATIENT", "ts": "00:02:58", "text": "I can do coffee with my neighbor on Wednesday."},
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
            {"speaker": "PATIENT", "ts": "00:00:10", "text": "Energy is better. Mornings used to take me an hour to get going, now maybe fifteen minutes."},
            {"speaker": "CLINICIAN", "ts": "00:00:21", "text": "Any side effects? Sleep, appetite, headaches?"},
            {"speaker": "PATIENT", "ts": "00:00:26", "text": "A little harder to fall asleep, but I'm taking it earlier in the day now. No headaches."},
            {"speaker": "CLINICIAN", "ts": "00:00:36", "text": "Any signs of elevated mood, racing thoughts, irritability?"},
            {"speaker": "PATIENT", "ts": "00:00:42", "text": "No. Mood feels stable. PHQ-9 I filled out this morning was an eight."},
            {"speaker": "CLINICIAN", "ts": "00:00:53", "text": "Eight is a real improvement. Are you tolerating the lamotrigine 200mg?"},
            {"speaker": "PATIENT", "ts": "00:00:59", "text": "Yes. No rash, no dizziness."},
            {"speaker": "CLINICIAN", "ts": "00:01:06", "text": "Okay. Plan: continue lamotrigine 200mg daily, continue bupropion XL 300mg daily. We'll check labs in three months. Any questions?"},
            {"speaker": "PATIENT", "ts": "00:01:18", "text": "Just refills."},
            {"speaker": "CLINICIAN", "ts": "00:01:21", "text": "Sending 90-day supply for both to your pharmacy now. See you in six weeks."},
        ],
    },
}


def _candidate_json_paths() -> list[Path]:
    here = Path(__file__).resolve()
    # repo root candidates: valant/ (top-level) and ValantClinicalDoc/
    return [
        here.parents[3] / "valant_clinical_transcripts.json",
        here.parents[2] / "valant_clinical_transcripts.json",
        Path.cwd() / "valant_clinical_transcripts.json",
    ]


def _load_overlay() -> None:
    """If valant_clinical_transcripts.json is found at the repo root, merge
    its `patients` and `transcripts` maps on top of the embedded fixtures.

    Honours VALANT_TRANSCRIPTS_JSON env var as an explicit override path.
    Logs to stdout (no failures) so dev keeps running with embedded data
    when the file is missing or malformed.
    """
    env_path = os.environ.get("VALANT_TRANSCRIPTS_JSON")
    paths = [Path(env_path)] if env_path else _candidate_json_paths()

    for path in paths:
        if not path or not path.is_file():
            continue
        try:
            data = json.loads(path.read_text())
        except Exception as exc:  # pragma: no cover - resilient stub
            print(f"[fixtures] Skipping {path}: {exc}")
            continue

        if isinstance(data.get("patients"), dict):
            PATIENTS.update(data["patients"])
        if isinstance(data.get("transcripts"), dict):
            TRANSCRIPTS.update(data["transcripts"])
        print(
            f"[fixtures] Loaded overlay from {path} "
            f"(patients={len(PATIENTS)}, transcripts={len(TRANSCRIPTS)})"
        )
        return


_load_overlay()


def get_transcript(transcript_id: str) -> dict[str, Any] | None:
    return TRANSCRIPTS.get(transcript_id)


def get_patient(patient_id: str) -> dict[str, Any] | None:
    return PATIENTS.get(patient_id)
