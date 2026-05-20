import { useEffect, useMemo, useRef, useState } from "react";
import AppLayout from "@cloudscape-design/components/app-layout";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import ColumnLayout from "@cloudscape-design/components/column-layout";
import ExpandableSection from "@cloudscape-design/components/expandable-section";
import FormField from "@cloudscape-design/components/form-field";
import Header from "@cloudscape-design/components/header";
import KeyValuePairs from "@cloudscape-design/components/key-value-pairs";
import Select from "@cloudscape-design/components/select";
import type { SelectProps } from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import Spinner from "@cloudscape-design/components/spinner";
import Textarea from "@cloudscape-design/components/textarea";
import TopNavigation from "@cloudscape-design/components/top-navigation";
import Badge from "@cloudscape-design/components/badge";
import Alert from "@cloudscape-design/components/alert";
import {
  getTranscript,
  listTranscripts,
  streamInvocation,
} from "./api";
import type { TranscriptDetail, TranscriptSummary } from "./types";

type RunState = "idle" | "running" | "done" | "error";

const FULL_PIPELINE_PROMPT = (transcriptId: string, patientId: string) =>
  `Document session ${transcriptId} for patient ${patientId}. ` +
  `Run the full pipeline: pull patient context, generate the clinical note, ` +
  `suggest ICD-10 + CPT codes, then run QA validation. Present the final ` +
  `note, codes, and QA verdict.`;

const ASK_PROMPT = (
  transcriptId: string,
  patientId: string,
  question: string,
) =>
  `Active session: transcript_id=${transcriptId}, patient_id=${patientId}. ` +
  `Use the relevant specialist tool(s) only as needed to answer this ` +
  `clinician question. Cite which tool(s) you used. Question: ${question.trim()}`;

export default function App() {
  const [transcripts, setTranscripts] = useState<TranscriptSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TranscriptDetail | null>(null);
  const [output, setOutput] = useState<string>("");
  const [toolEvents, setToolEvents] = useState<string[]>([]);
  const [state, setState] = useState<RunState>("idle");
  const [error, setError] = useState<string | null>(null);
  const [question, setQuestion] = useState<string>("");
  const abortRef = useRef<AbortController | null>(null);
  const outputRef = useRef<HTMLPreElement>(null);

  useEffect(() => {
    listTranscripts()
      .then((items) => {
        setTranscripts(items);
        if (items.length && !selectedId) setSelectedId(items[0].transcript_id);
      })
      .catch((err) => setError(String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setDetail(null);
    getTranscript(selectedId)
      .then(setDetail)
      .catch((err) => setError(String(err)));
  }, [selectedId]);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [output]);

  const selectOptions: SelectProps.Option[] = useMemo(
    () =>
      transcripts.map((t) => ({
        label: `${t.transcript_id} — ${t.patient_name}`,
        value: t.transcript_id,
        description: `${t.modality} · ${t.duration_minutes} min · ${t.encounter_date}`,
      })),
    [transcripts],
  );

  const selectedOption =
    selectOptions.find((o) => o.value === selectedId) ?? null;

  async function runPrompt(prompt: string) {
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setOutput("");
    setToolEvents([]);
    setError(null);
    setState("running");

    try {
      let lastTool: string | null = null;
      for await (const chunk of streamInvocation(prompt, ctrl.signal)) {
        if (chunk.includes("[tool]")) {
          const toolName = chunk.replace(/\n?\[tool\]/g, "").trim();
          if (toolName && toolName !== lastTool) {
            setToolEvents((evs) => [...evs, toolName]);
            lastTool = toolName;
          }
          continue;
        }
        lastTool = null;
        setOutput((prev) => prev + chunk);
      }
      setState("done");
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      setError(String(err));
      setState("error");
    }
  }

  function runFullPipeline() {
    if (!detail) return;
    runPrompt(
      FULL_PIPELINE_PROMPT(
        detail.transcript.transcript_id,
        detail.patient.patient_id,
      ),
    );
  }

  function askQuestion() {
    if (!detail || !question.trim()) return;
    runPrompt(
      ASK_PROMPT(
        detail.transcript.transcript_id,
        detail.patient.patient_id,
        question,
      ),
    );
  }

  function stopPipeline() {
    abortRef.current?.abort();
    setState("idle");
  }

  return (
    <>
      <TopNavigation
        identity={{
          href: "#",
          title: "Valant Clinical Documentation Agent",
        }}
        utilities={[
          {
            type: "button",
            text: "Hackathon · Bedrock AgentCore + Strands",
            disableUtilityCollapse: true,
          },
        ]}
      />
      <AppLayout
        toolsHide
        navigationHide
        content={
          <ContentLayout
            header={
              <Header
                variant="h1"
                description="Skips Nova Sonic — feeds dummy session transcripts to a Bedrock AgentCore + Strands orchestrator that runs the full clinical-note pipeline (context → note → codes → QA)."
              >
                Clinician Review
              </Header>
            }
          >
            <SpaceBetween size="l">
              {error && (
                <Alert type="error" header="Error">
                  {error}
                </Alert>
              )}

              <Container
                header={<Header variant="h2">Session selector</Header>}
              >
                <SpaceBetween size="m">
                  <Select
                    selectedOption={selectedOption}
                    onChange={(e) =>
                      setSelectedId(e.detail.selectedOption.value ?? null)
                    }
                    options={selectOptions}
                    placeholder="Choose a transcript"
                    empty="No transcripts available"
                  />
                  <SpaceBetween size="s" direction="horizontal">
                    <Button
                      variant="primary"
                      onClick={runFullPipeline}
                      loading={state === "running"}
                      disabled={!detail || state === "running"}
                    >
                      Run documentation pipeline
                    </Button>
                    {state === "running" && (
                      <Button onClick={stopPipeline}>Stop</Button>
                    )}
                  </SpaceBetween>
                </SpaceBetween>
              </Container>

              {detail && (
                <ColumnLayout columns={2} variant="default">
                  <Container header={<Header variant="h2">Patient</Header>}>
                    <KeyValuePairs
                      columns={1}
                      items={[
                        { label: "Name", value: detail.patient.name },
                        {
                          label: "Patient ID",
                          value: detail.patient.patient_id,
                        },
                        { label: "DOB", value: detail.patient.dob },
                        {
                          label: "Diagnoses",
                          value: detail.patient.diagnoses.join(", "),
                        },
                        {
                          label: "Active medications",
                          value: detail.patient.active_medications
                            .map(
                              (m) =>
                                `${m.name} ${m.dose} ${m.frequency}`,
                            )
                            .join(", "),
                        },
                        {
                          label: "Sessions remaining",
                          value: (
                            <Badge
                              color={
                                detail.patient.auth_status
                                  .sessions_remaining < 4
                                  ? "red"
                                  : "green"
                              }
                            >
                              {String(
                                detail.patient.auth_status
                                  .sessions_remaining,
                              )}
                            </Badge>
                          ),
                        },
                        {
                          label: "Payer",
                          value: detail.patient.auth_status.payer,
                        },
                        {
                          label: "Latest measurements",
                          value: Object.entries(
                            detail.patient.measurements,
                          )
                            .map(
                              ([k, v]) =>
                                `${k}=${v.latest} (trend ${v.trend.join(",")})`,
                            )
                            .join(" · "),
                        },
                      ]}
                    />
                  </Container>

                  <Container
                    header={
                      <Header
                        variant="h2"
                        description={`${detail.transcript.modality} · ${detail.transcript.duration_minutes} min · ${detail.transcript.utterances.length} utterances`}
                      >
                        Transcript
                      </Header>
                    }
                  >
                    <Box>
                      <ExpandableSection
                        defaultExpanded
                        headerText="Show full transcript"
                      >
                        <pre
                          style={{
                            whiteSpace: "pre-wrap",
                            margin: 0,
                            maxHeight: 320,
                            overflow: "auto",
                            fontSize: 12,
                            lineHeight: 1.5,
                          }}
                        >
                          {detail.transcript.utterances
                            .map(
                              (u) =>
                                `[${u.ts}] ${u.speaker}: ${u.text}`,
                            )
                            .join("\n")}
                        </pre>
                      </ExpandableSection>
                    </Box>
                  </Container>
                </ColumnLayout>
              )}

              <Container
                header={
                  <Header
                    variant="h2"
                    actions={
                      state === "running" ? (
                        <Spinner />
                      ) : state === "done" ? (
                        <StatusIndicator type="success">
                          Stream complete
                        </StatusIndicator>
                      ) : state === "error" ? (
                        <StatusIndicator type="error">
                          Failed
                        </StatusIndicator>
                      ) : (
                        <StatusIndicator type="pending">
                          Idle
                        </StatusIndicator>
                      )
                    }
                  >
                    Agent output (streaming)
                  </Header>
                }
              >
                <SpaceBetween size="s">
                  {toolEvents.length > 0 && (
                    <Box>
                      <SpaceBetween size="xxs" direction="horizontal">
                        {toolEvents.map((t, i) => (
                          <Badge color="blue" key={`${t}-${i}`}>
                            {t}
                          </Badge>
                        ))}
                      </SpaceBetween>
                    </Box>
                  )}
                  <pre
                    ref={outputRef}
                    style={{
                      whiteSpace: "pre-wrap",
                      margin: 0,
                      minHeight: 240,
                      maxHeight: 540,
                      overflow: "auto",
                      background: "#f4f4f4",
                      padding: 12,
                      borderRadius: 4,
                      fontSize: 13,
                      lineHeight: 1.55,
                    }}
                  >
                    {output ||
                      (state === "idle"
                        ? "Press “Run documentation pipeline” to start, or ask a question below."
                        : "Waiting for first chunk…")}
                  </pre>
                </SpaceBetween>
              </Container>

              <Container
                header={
                  <Header
                    variant="h2"
                    description="Ask the orchestrator anything about this session — it routes to the relevant specialist (context, note, coder, QA) automatically."
                  >
                    Ask the agent
                  </Header>
                }
              >
                <SpaceBetween size="s">
                  <FormField
                    label="Clinician question"
                    description={
                      detail
                        ? `Context: ${detail.transcript.transcript_id} · ${detail.patient.name} (${detail.patient.patient_id})`
                        : "Pick a transcript first."
                    }
                  >
                    <Textarea
                      value={question}
                      onChange={(e) => setQuestion(e.detail.value)}
                      placeholder="e.g., What CPT code best fits this 53-minute CBT session and why? Or: Did the patient mention any active SI?"
                      rows={3}
                      onKeyDown={(e) => {
                        if (
                          e.detail.key === "Enter" &&
                          (e.detail.metaKey || e.detail.ctrlKey)
                        ) {
                          askQuestion();
                        }
                      }}
                    />
                  </FormField>
                  <SpaceBetween size="s" direction="horizontal">
                    <Button
                      variant="primary"
                      onClick={askQuestion}
                      disabled={
                        !detail || !question.trim() || state === "running"
                      }
                    >
                      Ask agent
                    </Button>
                    <Button
                      onClick={() => setQuestion("")}
                      disabled={!question}
                    >
                      Clear
                    </Button>
                    <Box variant="small" color="text-body-secondary">
                      Tip: ⌘/Ctrl+Enter to send
                    </Box>
                  </SpaceBetween>
                </SpaceBetween>
              </Container>
            </SpaceBetween>
          </ContentLayout>
        }
      />
    </>
  );
}
