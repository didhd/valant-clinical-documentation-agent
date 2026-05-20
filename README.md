# Valant Clinical Documentation Agent

Hackathon project for **Valant Medical Solutions** — a multi-specialist
agentic pipeline that turns a behavioral-health session **transcript** into a
sign-off-ready clinical artifact bundle (structured note + ICD-10/CPT codes +
QA verdict).

Built on **Amazon Bedrock AgentCore Runtime + Strands** following Option B
("Custom Agentic Pipeline") from the solution architecture, deliberately
**without the transcription stage** so we can iterate on the agentic layer
end-to-end. Audio → transcript is mocked with two dummy session fixtures.

The clinician-facing UI is a **Cloudscape Design System** React app that
streams the orchestrator's output via SSE.

> Deeper context for AI coding assistants lives in [`CLAUDE.md`](./CLAUDE.md).

## Architecture

```
                 ┌──────────────────────────────────────┐
                 │ Clinician Browser  (Cloudscape UI)   │
                 │   - Transcript picker                │
                 │   - Patient panel + transcript view  │
                 │   - Streaming agent output panel     │
                 └──────────────────┬───────────────────┘
                                    │  GET  /transcripts
                                    │  POST /invocations  (SSE stream)
                                    ▼
            ┌────────────────────────────────────────────────────┐
            │  Bedrock AgentCore Runtime (BedrockAgentCoreApp)   │
            │  app/ClinicalDocAgent/main.py                       │
            │                                                    │
            │   ┌──────────────────────────────────────────┐     │
            │   │   ORCHESTRATOR  (Strands Agent)          │     │
            │   │   model: us.anthropic.claude-sonnet-4-6  │     │
            │   │   system_prompt: routing rules           │     │
            │   └─────┬─────┬──────────┬───────────┬───────┘     │
            │         │     │          │           │             │
            │   tool: │  tool:        tool:       tool:          │
            │  get_   │  clinical_   medical_    qa_             │
            │  patient│  note_       coder       reviewer        │
            │  _ctx   │  writer                                  │
            │         │     │          │           │             │
            │      (dummy)  │ Sonnet 4.6  Sonnet 4.6  Haiku 4.5  │
            │      EHR pull │ Strands     Strands     Strands    │
            │               │ specialist  specialist  specialist │
            │   ┌───────────┴──────────────────────────────┐     │
            │   │   AgentCore Memory (optional, env-gated) │     │
            │   │   MEMORY_ID + ACTOR_ID -> session mgr    │     │
            │   └──────────────────────────────────────────┘     │
            └────────────────────────┬───────────────────────────┘
                                     │
                                     ▼
                  ┌──────────────────────────────────┐
                  │ Bedrock (us-west-2)              │
                  │   us.anthropic.claude-opus-4-6-v1│
                  │   us.anthropic.claude-sonnet-4-6 │
                  │   us.anthropic.claude-haiku-4-5  │
                  └──────────────────────────────────┘

                  ┌──────────────────────────────────┐
                  │ Dummy data (no Nova Sonic yet)   │
                  │  fixtures/transcripts.py:        │
                  │   - T-CBT-001  (CBT, 53 min)     │
                  │   - T-MED-002  (med mgmt, 22 min)│
                  └──────────────────────────────────┘
```

### Pipeline order

1. **`get_patient_context`** — deterministic EHR lookup. Returns treatment
   plan, PHQ-9 / GAD-7 trends, sessions remaining, and the recommended
   template (CBT / DAP / SOAP / Med Management). No LLM call.
2. **`clinical_note_writer`** *(Sonnet 4.6 specialist)* — drafts the
   structured note, grounded in the transcript + patient context. Refuses
   to invent content; missing sections become "Not addressed this session."
3. **`medical_coder`** *(Sonnet 4.6 specialist)* — suggests ICD-10 (F-codes
   first) + time-based CPT (90832/90834/90837) with confidence scores.
4. **`qa_reviewer`** *(Haiku 4.5 specialist)* — strict QA pass that checks
   for hallucinations against the transcript, risk-assessment language,
   time-vs-CPT consistency, and treatment-goal alignment.

### Why agents-as-tools

Each specialist is a `@tool`-decorated function that wraps a focused
`Agent(system_prompt=..., model=..., callback_handler=None)`. The
orchestrator picks them by name. This is the canonical Strands pattern:
[Agents as Tools](https://strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/).
Three benefits we rely on for hackathon iteration:

- **Per-tool model tier** — QA runs on cheaper Haiku 4.5; the note writer
  uses Sonnet 4.6. Override via `*_MODEL_TIER` env vars.
- **Independent prompts** — narrowing each specialist's scope reduces
  hallucinations vs. one mega-prompt.
- **Local testability** — each tool is a normal Python function we can
  unit-test or call from the orchestrator.

## Demo data

Two transcripts in `ValantClinicalDoc/app/ClinicalDocAgent/fixtures/transcripts.py`:

| ID | Session | Patient | Modality | Duration |
|----|---------|---------|----------|----------|
| `T-CBT-001` | CBT therapy | Jane Doe (P-1001) — MDD recurrent + GAD | CBT | 53 min |
| `T-MED-002` | Med management | Marcus Lee (P-1002) — Bipolar II + ADHD | Med Mgmt | 22 min |

## Run it locally (first time)

Prerequisites:

- **Node.js ≥ 20** and **Python ≥ 3.10**
- **`uv`** — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **AWS credentials** (`aws configure`) with `bedrock:InvokeModel` permission
  for the three `us.anthropic.*` Claude inference profiles in **us-west-2**

```bash
git clone <this-repo>
cd valant
make install        # uv sync + npm install + create .env.local stub
make dev            # runs agent (:8080) + UI (:5173) concurrently
```

Open http://localhost:5173, pick a transcript, hit **Run documentation
pipeline**, watch the orchestrator stream `[tool] <name>` markers and the
final note + codes + QA verdict.

If `make dev` doesn't suit you, run them in two terminals:

```bash
# Terminal 1
make agent          # cd ValantClinicalDoc/app/ClinicalDocAgent && uv run python main.py

# Terminal 2
make web            # cd web && npm run dev
```

## Deploy to AgentCore Runtime (optional)

```bash
cd ValantClinicalDoc
agentcore validate
agentcore deploy           # ~3-5 min, builds CDK stack + ECR repo
agentcore invoke           # interactive session
agentcore logs --since 30m
```

When you want memory:

```bash
agentcore add              # → Memory → ClinicalDocMemory, 7-day, User-pref
agentcore deploy
echo "MEMORY_ID=<id>"  >> agentcore/.env.local
echo "ACTOR_ID=clinician" >> agentcore/.env.local
```

## Repo layout

```
valant/
├── README.md                       # this file
├── CLAUDE.md                       # AI-assistant context
├── Makefile                        # `make install/agent/web/dev/check/clean`
├── ValantClinicalDoc/              # AgentCore CLI project
│   ├── agentcore/agentcore.json    # CLI config
│   └── app/ClinicalDocAgent/
│       ├── main.py                 # Orchestrator (BedrockAgentCoreApp + Strands)
│       ├── tools/clinical.py       # 4 specialist sub-agents (agents-as-tools)
│       ├── fixtures/transcripts.py # Dummy transcripts + patient context
│       ├── model/load.py           # Tiered Bedrock model loader
│       └── pyproject.toml
└── web/                            # Cloudscape clinician UI (Vite + React)
    ├── vite.config.ts              # /transcripts + /invocations proxy → :8080
    └── src/
        ├── App.tsx
        ├── api.ts                  # SSE-aware fetch wrapper
        └── types.ts
```

## Roadmap

| Stage | Adds | Status |
|-------|------|--------|
| 1. Skeleton | Orchestrator + 4 tool specialists + dummy data | ✅ done |
| 2. Cloudscape UI | Clinician review screen, streaming output | ✅ done |
| 3. AgentCore Memory | Per-clinician preferences across sessions | env-gated stub wired, needs `agentcore add` |
| 4. AgentCore Gateway | Replace dummy `get_patient_context` with Lambda → Valant EHR | TODO |
| 5. Real transcription | Plug in Connect Health / Nova Sonic in front | TODO |
| 6. Sign-off + writeback | Clinician approval flow → EHR API | TODO |

## References

- [Valant solution architecture](./Valant%20Clinical%20Documentation%20Agent%20—%20Solution%20Architecture.md) (private)
- [AgentCore CLI cheatsheet](https://docs.aws.amazon.com/bedrock-agentcore/)
- [Strands agents-as-tools](https://strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/)
- [Strands streaming](https://strandsagents.com/docs/user-guide/concepts/streaming/)
- [Cloudscape Design System](https://cloudscape.design/)
- Reference UI we borrowed shape from: https://github.com/didhd/nova-sonic-2-strands-pattern
