# CLAUDE.md — Valant Clinical Documentation Agent

This file gives an AI coding assistant the minimum context needed to work
productively in this repo. Keep it in sync when you change architecture,
tooling, or run instructions.

## What this project is

A hackathon-grade reference implementation of the Valant **AI Clinical
Documentation Agent** described in
`Valant Clinical Documentation Agent — Solution Architecture.md` (Option B —
"Custom Agentic Pipeline (Bedrock AgentCore + Strands)"), with one
intentional simplification: we **skip the transcription stage** (Nova Sonic /
Connect Health) and feed dummy session transcripts so we can iterate on the
agentic layer end-to-end without real audio.

The orchestrator is a Strands `Agent` deployed to **Amazon Bedrock AgentCore
Runtime**. It coordinates four specialist sub-agents wrapped as tools
(the [agents-as-tools pattern](https://strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/)):

| Tool | Role | Model tier |
|------|------|------------|
| `get_patient_context` | Deterministic EHR lookup (no LLM) | n/a |
| `clinical_note_writer` | Drafts a structured note from transcript + context | Sonnet 4.6 |
| `medical_coder` | Suggests ICD-10 + CPT with confidence scores | Sonnet 4.6 |
| `qa_reviewer` | Validates note + codes against the transcript | Haiku 4.5 |

The orchestrator itself runs on **Sonnet 4.6** by default. Tier per role is
overridable via env vars (see `app/ClinicalDocAgent/model/load.py`).

The clinician-facing web UI is a Cloudscape Design System React app under
`web/` that streams the orchestrator's output via SSE.

## Architecture

```
                 ┌──────────────────────────────────────┐
                 │ Clinician Browser  (Cloudscape UI)   │
                 │   - Transcript picker                │
                 │   - Patient panel + transcript view  │
                 │   - Streaming agent output panel     │
                 └──────────────────┬───────────────────┘
                                    │  fetch /transcripts
                                    │  POST   /invocations  (SSE stream)
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

Pipeline order driven by the orchestrator's system prompt:

```
1. get_patient_context  →  patient facts + recommended template
2. clinical_note_writer →  structured note in chosen template
3. medical_coder        →  ICD-10 + CPT + confidence
4. qa_reviewer          →  pass / pass_with_warnings / fail + warnings
```

## Repo layout

```
valant/
├── README.md                       # Hackathon walkthrough
├── CLAUDE.md                       # ← this file (AI assistant context)
├── Makefile                        # `make dev`, `make agent`, `make web`
├── ValantClinicalDoc/              # AgentCore CLI project
│   ├── agentcore/agentcore.json    # CLI config (validate with `agentcore validate`)
│   └── app/ClinicalDocAgent/
│       ├── main.py                 # Orchestrator entrypoint
│       ├── tools/clinical.py       # 4 specialist sub-agents (agents-as-tools)
│       ├── fixtures/transcripts.py # Dummy transcripts + patient context
│       ├── model/load.py           # Tiered Bedrock model loader
│       └── pyproject.toml          # uv-managed Python deps
└── web/                            # Cloudscape clinician UI
    ├── package.json
    ├── vite.config.ts              # Proxies /transcripts + /invocations -> :8080
    └── src/
        ├── App.tsx                 # AppLayout, Select, streaming panel
        ├── api.ts                  # SSE-aware fetch wrapper
        └── types.ts
```

## Running locally

Prerequisites:

- Node.js ≥ 20
- Python ≥ 3.10 + [uv](https://docs.astral.sh/uv/getting-started/installation/)
- AWS credentials in `~/.aws/credentials` with `bedrock:InvokeModel` for the
  three `us.anthropic.*` Claude inference profiles in **us-west-2**
- `npm install -g @aws/agentcore` (only required if you want to deploy)

First-time setup:

```bash
git clone <repo>
cd valant
make install           # uv sync (Python) + npm install (web) + create .env.local
```

Run both processes in two terminals:

```bash
make agent             # Terminal 1 — Bedrock AgentCore Runtime on :8080
make web               # Terminal 2 — Vite dev server on :5173
```

…or both at once:

```bash
make dev               # uses concurrently to run both
```

Then open http://localhost:5173 and pick a transcript.

## Adding AgentCore Memory (optional)

The orchestrator wires `AgentCoreMemorySessionManager` only when `MEMORY_ID`
is in env, so local dev runs fine without provisioning anything.

```bash
cd ValantClinicalDoc
agentcore add          # Memory → ClinicalDocMemory, 7-day expiry, User-pref
agentcore deploy
echo "MEMORY_ID=<id-from-agentcore-status>" >> agentcore/.env.local
echo "ACTOR_ID=clinician" >> agentcore/.env.local
```

## Conventions for AI assistants working on this repo

- **Don't bring back Nova Sonic** unless explicitly asked. The hackathon
  scope is "agentic pipeline only, dummy transcripts."
- **Sub-agents stay narrow.** Each one has a focused system prompt and a
  single `query: str -> str` signature per the agents-as-tools pattern.
  If you need to add a new specialist (e.g., risk-scoring agent), copy the
  shape in `tools/clinical.py`.
- **Frontier model IDs only.** Use `us.anthropic.claude-{opus-4-6-v1,
  sonnet-4-6, haiku-4-5-20251001-v1:0}` via the loader in `model/load.py`.
- **Stream by default.** The agent yields text deltas + `[tool] <name>`
  markers; the UI consumes them as SSE.
- **Validate config after editing `agentcore.json`.** Run `agentcore validate`.
- **Never write `${VAR}` placeholders into `agentcore.json`.** Resolve env
  vars yourself and write literal values, otherwise the runtime IAM policy
  breaks at invoke time.

## Troubleshooting

- `404 {"error":"Not found"}` on `/invocations` → you hit `agentcore dev` in
  a non-TTY shell. Use `python main.py` (or `make agent`) instead.
- Console error `does not provide an export named 'SelectProps'` → use a
  `import type { SelectProps }` separate from the runtime import (Cloudscape
  ships types under the same module path but esbuild/Vite needs the `type`
  marker).
- `AccessDeniedException` on Bedrock → confirm your AWS credentials see the
  `us.anthropic.*` inference profiles by running
  `aws bedrock list-inference-profiles --region us-west-2`.

## References

- AgentCore CLI cheatsheet: https://docs.aws.amazon.com/bedrock-agentcore/
- Strands agents-as-tools: https://strandsagents.com/docs/user-guide/concepts/multi-agent/agents-as-tools/
- Strands streaming: https://strandsagents.com/docs/user-guide/concepts/streaming/
- Cloudscape components: https://cloudscape.design/
