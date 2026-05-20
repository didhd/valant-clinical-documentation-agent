export interface TranscriptSummary {
  transcript_id: string;
  patient_id: string;
  patient_name: string;
  session_type: string;
  modality: string;
  duration_minutes: number;
  encounter_date: string;
  utterance_count: number;
}

export interface Utterance {
  speaker: "CLINICIAN" | "PATIENT";
  ts: string;
  text: string;
}

export interface Transcript extends TranscriptSummary {
  utterances: Utterance[];
}

export interface Patient {
  patient_id: string;
  name: string;
  dob: string;
  diagnoses: string[];
  active_medications: { name: string; dose: string; frequency: string }[];
  treatment_plan: {
    modality: string;
    goals: string[];
    homework_last_session: string;
  };
  measurements: Record<
    string,
    { trend: number[]; latest: number; instrument: string }
  >;
  previous_session_summary: string;
  auth_status: { sessions_remaining: number; payer: string; auth_id: string };
  provider_id: string;
}

export interface TranscriptDetail {
  transcript: Transcript;
  patient: Patient;
}
