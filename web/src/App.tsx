import { useEffect, useMemo, useRef, useState } from "react";
import AppLayout from "@cloudscape-design/components/app-layout";
import Box from "@cloudscape-design/components/box";
import Button from "@cloudscape-design/components/button";
import Container from "@cloudscape-design/components/container";
import ContentLayout from "@cloudscape-design/components/content-layout";
import ExpandableSection from "@cloudscape-design/components/expandable-section";
import Grid from "@cloudscape-design/components/grid";
import Header from "@cloudscape-design/components/header";
import KeyValuePairs from "@cloudscape-design/components/key-value-pairs";
import Select from "@cloudscape-design/components/select";
import type { SelectProps } from "@cloudscape-design/components/select";
import SpaceBetween from "@cloudscape-design/components/space-between";
import StatusIndicator from "@cloudscape-design/components/status-indicator";
import TopNavigation from "@cloudscape-design/components/top-navigation";
import Badge from "@cloudscape-design/components/badge";
import Alert from "@cloudscape-design/components/alert";
import LiveRegion from "@cloudscape-design/components/live-region";
import PromptInput from "@cloudscape-design/components/prompt-input";
import Avatar from "@cloudscape-design/chat-components/avatar";
import ChatBubble from "@cloudscape-design/chat-components/chat-bubble";
import LoadingBar from "@cloudscape-design/chat-components/loading-bar";
import SupportPromptGroup from "@cloudscape-design/chat-components/support-prompt-group";
import {
  getTranscript,
  listTranscripts,
  streamInvocation,
} from "./api";
import type { TranscriptDetail, TranscriptSummary } from "./types";
import Markdown from "./components/Markdown";

type Author = "user" | "assistant";

interface ChatMessage {
  id: string;
  author: Author;
  text: string;
  tools: string[];
  state: "streaming" | "done" | "error";
}

const SELECTED_ID_KEY = "valant.selectedTranscriptId";

const FULL_PIPELINE_PROMPT = (transcriptId: string, patientId: string) =>
  `Document session ${transcriptId} for patient ${patientId}. ` +
  `Run the full pipeline: pull patient context, generate the clinical note, ` +
  `suggest ICD-10 + CPT codes, then run QA validation. Present the final ` +
  `note, codes, and QA verdict.`;

const SUPPORT_PROMPTS = [
  { id: "full", text: "Run the full pipeline" },
  { id: "si", text: "Active SI discussed?" },
  { id: "cpt", text: "Best CPT code?" },
  { id: "summary", text: "3-sentence chart summary" },
];

export default function App() {
  const [transcripts, setTranscripts] = useState<TranscriptSummary[]>([]);
  const [selectedId, setSelectedIdState] = useState<string | null>(() => {
    try {
      return localStorage.getItem(SELECTED_ID_KEY);
    } catch {
      return null;
    }
  });
  const setSelectedId = (id: string | null) => {
    setSelectedIdState(id);
    try {
      if (id) localStorage.setItem(SELECTED_ID_KEY, id);
      else localStorage.removeItem(SELECTED_ID_KEY);
    } catch {
      // ignore
    }
  };

  const [detail, setDetail] = useState<TranscriptDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listTranscripts()
      .then((items) => {
        setTranscripts(items);
        // Use stored selection only if it still exists in the list.
        const stillThere = items.some((t) => t.transcript_id === selectedId);
        if (!stillThere && items.length) {
          setSelectedId(items[0].transcript_id);
        }
      })
      .catch((err) => setError(String(err)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setDetail(null);
    setMessages([]);
    getTranscript(selectedId)
      .then(setDetail)
      .catch((err) => setError(String(err)));
  }, [selectedId]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

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

  async function sendPrompt(prompt: string) {
    if (!detail || !prompt.trim() || busy) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setBusy(true);
    setError(null);

    // Inject session context so the orchestrator always knows which
    // transcript/patient is active. The user sees only their own text.
    const contextPrefix =
      `[Active session: transcript_id=${detail.transcript.transcript_id}, ` +
      `patient_id=${detail.patient.patient_id}, ` +
      `patient_name=${detail.patient.name}, ` +
      `modality=${detail.transcript.modality}, ` +
      `duration=${detail.transcript.duration_minutes}min]\n\n`;
    const fullPrompt = contextPrefix + prompt;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      author: "user",
      text: prompt, // Show only user's text in the bubble
      tools: [],
      state: "done",
    };
    const assistantId = `a-${Date.now()}`;
    const assistantMsg: ChatMessage = {
      id: assistantId,
      author: "assistant",
      text: "",
      tools: [],
      state: "streaming",
    };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    try {
      let lastTool: string | null = null;
      for await (const chunk of streamInvocation(fullPrompt, ctrl.signal)) {
        if (chunk.includes("[tool]")) {
          const toolName = chunk.replace(/\n?\[tool\]/g, "").trim();
          if (toolName && toolName !== lastTool) {
            lastTool = toolName;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, tools: [...m.tools, toolName] }
                  : m,
              ),
            );
          }
          continue;
        }
        lastTool = null;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, text: m.text + chunk } : m,
          ),
        );
      }
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, state: "done" } : m,
        ),
      );
    } catch (err) {
      if ((err as Error).name === "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, state: "done" } : m,
          ),
        );
        return;
      }
      setError(String(err));
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, state: "error", text: m.text || String(err) }
            : m,
        ),
      );
    } finally {
      setBusy(false);
    }
  }

  function onSubmit() {
    const text = draft.trim();
    if (!text || !detail) return;
    setDraft("");
    sendPrompt(text);
  }

  function onSupportPrompt(id: string) {
    const sp = SUPPORT_PROMPTS.find((s) => s.id === id);
    if (!sp || !detail) return;
    if (id === "full") {
      sendPrompt(
        "Run the full pipeline: pull patient context, generate the clinical note, " +
          "suggest ICD-10 + CPT codes, then run QA validation. Present the final " +
          "note, codes, and QA verdict.",
      );
    } else {
      sendPrompt(sp.text);
    }
  }

  function stop() {
    abortRef.current?.abort();
  }

  function clearChat() {
    abortRef.current?.abort();
    setMessages([]);
  }

  const lastAssistantText = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].author === "assistant") return messages[i].text;
    }
    return "";
  }, [messages]);

  return (
    <>
      <TopNavigation
        identity={{
          href: "#",
          title: "ScribeForce",
        }}
        utilities={[
          {
            type: "button",
            text: "Bedrock AgentCore + Strands",
            disableUtilityCollapse: true,
          },
        ]}
      />
      <AppLayout
        toolsHide
        navigationHide
        maxContentWidth={Number.MAX_VALUE}
        content={
          <ContentLayout
            disableOverlap
            header={
              <Header
                variant="h1"
                description="Bedrock AgentCore + Strands orchestrator running a multi-specialist clinical-note pipeline (context → note → codes → QA). Voice input via Nova Sonic — text-only output."
              >
                Clinician Review
              </Header>
            }
          >
            <SpaceBetween size="m">
              {error && (
                <Alert
                  type="error"
                  header="Error"
                  dismissible
                  onDismiss={() => setError(null)}
                >
                  {error}
                </Alert>
              )}

              <Grid
                gridDefinition={[
                  { colspan: { default: 12, m: 5, l: 4, xl: 3 } },
                  { colspan: { default: 12, m: 7, l: 8, xl: 9 } },
                ]}
              >
                {/* LEFT RAIL ------------------------------------------------ */}
                <SpaceBetween size="s">
                  <Container
                    header={
                      <Header
                        variant="h3"
                        description={
                          detail
                            ? `${detail.transcript.modality} · ${detail.transcript.duration_minutes} min`
                            : `${transcripts.length} sessions`
                        }
                      >
                        Session
                      </Header>
                    }
                  >
                    <Select
                      selectedOption={selectedOption}
                      onChange={(e) =>
                        setSelectedId(e.detail.selectedOption.value ?? null)
                      }
                      options={selectOptions}
                      placeholder="Choose a transcript"
                      empty="No transcripts available"
                      filteringType="auto"
                      expandToViewport
                    />
                  </Container>

                  {detail && (
                    <Container
                      header={<Header variant="h3">Patient</Header>}
                    >
                      <KeyValuePairs
                        columns={1}
                        items={[
                          { label: "Name", value: detail.patient.name },
                          {
                            label: "ID",
                            value: detail.patient.patient_id,
                          },
                          ...(detail.patient.dob
                            ? [{ label: "DOB", value: detail.patient.dob }]
                            : []),
                          {
                            label: "Diagnoses",
                            value:
                              detail.patient.diagnoses
                                .map((d) => d.split(" ")[0])
                                .join(", ") || "—",
                          },
                          {
                            label: "Sessions left",
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
                          ...(Object.keys(detail.patient.measurements).length >
                          0
                            ? [
                                {
                                  label: "Scores",
                                  value: Object.entries(
                                    detail.patient.measurements,
                                  )
                                    .map(([k, v]) => `${k}=${v.latest}`)
                                    .join(" · "),
                                },
                              ]
                            : []),
                        ]}
                      />
                      <Box margin={{ top: "s" }}>
                        <ExpandableSection
                          variant="footer"
                          headerText="More details"
                        >
                          <KeyValuePairs
                            columns={1}
                            items={[
                              {
                                label: "Full diagnoses",
                                value:
                                  detail.patient.diagnoses.join("; ") || "—",
                              },
                              {
                                label: "Active meds",
                                value:
                                  detail.patient.active_medications
                                    .map(
                                      (m) =>
                                        `${m.name} ${m.dose} ${m.frequency}`,
                                    )
                                    .join(", ") || "—",
                              },
                              ...(detail.patient.previous_session_summary
                                ? [
                                    {
                                      label: "Last session",
                                      value:
                                        detail.patient.previous_session_summary,
                                    },
                                  ]
                                : []),
                            ]}
                          />
                        </ExpandableSection>
                      </Box>
                    </Container>
                  )}

                  {detail && (
                    <Container
                      header={
                        <Header
                          variant="h3"
                          description={`${detail.transcript.utterances.length} utterances`}
                        >
                          Transcript
                        </Header>
                      }
                    >
                      <ExpandableSection
                        variant="footer"
                        headerText="Show full transcript"
                      >
                        <pre
                          style={{
                            whiteSpace: "pre-wrap",
                            margin: 0,
                            maxHeight: 320,
                            overflow: "auto",
                            fontSize: 11,
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
                    </Container>
                  )}
                </SpaceBetween>

                {/* RIGHT COLUMN — CHAT ------------------------------------- */}
                <Container
                  disableContentPaddings
                  header={
                    <Header
                      variant="h2"
                      description="Routes to the right specialist (context, note, coder, QA) automatically."
                      actions={
                        <SpaceBetween size="xs" direction="horizontal">
                          {busy && (
                            <Button onClick={stop} iconName="status-stopped">
                              Stop
                            </Button>
                          )}
                          {messages.length > 0 && !busy && (
                            <Button onClick={clearChat} iconName="refresh">
                              New chat
                            </Button>
                          )}
                        </SpaceBetween>
                      }
                    >
                      Generative AI chat
                    </Header>
                  }
                >
                  <div
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      height: "calc(100vh - 200px)",
                      minHeight: 480,
                    }}
                  >
                    <div
                      role="region"
                      aria-label="Chat"
                      ref={scrollRef}
                      style={{
                        flex: 1,
                        overflowY: "auto",
                        padding: "16px 20px",
                      }}
                    >
                      {messages.length === 0 ? (
                        <Box
                          color="text-body-secondary"
                          textAlign="center"
                          padding="xxl"
                        >
                          <SpaceBetween size="s">
                            <div style={{ fontSize: 32 }}>💬</div>
                            <Box variant="h3" color="text-body-secondary">
                              Ready when you are
                            </Box>
                            <div>
                              Pick a quick prompt below or ask anything about{" "}
                              {detail
                                ? `${detail.transcript.transcript_id} — ${detail.patient.name}`
                                : "the selected session"}
                              .
                            </div>
                          </SpaceBetween>
                        </Box>
                      ) : (
                        <SpaceBetween size="m">
                          {messages.map((m) => (
                            <ChatMessageView key={m.id} message={m} />
                          ))}
                        </SpaceBetween>
                      )}
                      <LiveRegion hidden assertive>
                        {lastAssistantText.slice(-280)}
                      </LiveRegion>
                    </div>

                    <div
                      style={{
                        borderTop: "1px solid #e9ebed",
                        padding: 12,
                        background: "#fafbfc",
                      }}
                    >
                      <SpaceBetween size="xs">
                        {detail && messages.length === 0 && (
                          <SupportPromptGroup
                            ariaLabel="Suggested prompts"
                            onItemClick={(e) => onSupportPrompt(e.detail.id)}
                            items={SUPPORT_PROMPTS.map((p) => ({
                              text: p.text,
                              id: p.id,
                            }))}
                          />
                        )}

                        <PromptInput
                          value={draft}
                          onChange={(e) => setDraft(e.detail.value)}
                          onAction={onSubmit}
                          actionButtonAriaLabel={
                            busy ? "Sending — disabled" : "Send message"
                          }
                          actionButtonIconName="send"
                          placeholder={
                            detail
                              ? `Ask about ${detail.transcript.transcript_id} — ${detail.patient.name}`
                              : "Pick a session first"
                          }
                          ariaLabel="Clinician question"
                          minRows={1}
                          maxRows={4}
                          disableActionButton={
                            busy || !detail || !draft.trim()
                          }
                          disabled={!detail}
                        />

                        {busy ? (
                          <LoadingBar variant="gen-ai-masked" />
                        ) : (
                          <Box variant="small" color="text-body-secondary">
                            <StatusIndicator type="success">
                              Ready
                            </StatusIndicator>
                          </Box>
                        )}
                      </SpaceBetween>
                    </div>
                  </div>
                </Container>
              </Grid>
            </SpaceBetween>
          </ContentLayout>
        }
      />
    </>
  );
}

function ChatMessageView({ message }: { message: ChatMessage }) {
  const isUser = message.author === "user";
  return (
    <ChatBubble
      ariaLabel={`${isUser ? "You" : "Assistant"} message`}
      type={isUser ? "outgoing" : "incoming"}
      avatar={
        isUser ? (
          <Avatar ariaLabel="Clinician" tooltipText="Clinician" initials="DR" />
        ) : (
          <Avatar
            color="gen-ai"
            iconName="gen-ai"
            ariaLabel="Documentation agent"
            tooltipText="Documentation agent"
            loading={message.state === "streaming"}
          />
        )
      }
    >
      {isUser ? (
        <Box>{message.text}</Box>
      ) : (
        <SpaceBetween size="xs">
          {message.tools.length > 0 && (
            <SpaceBetween size="xxs" direction="horizontal">
              {message.tools.map((t, i) => (
                <Badge color="blue" key={`${t}-${i}`}>
                  {t}
                </Badge>
              ))}
            </SpaceBetween>
          )}
          {message.text ? (
            <Markdown source={message.text} />
          ) : message.state === "streaming" ? (
            <Box color="text-body-secondary">Thinking…</Box>
          ) : null}
        </SpaceBetween>
      )}
    </ChatBubble>
  );
}
