# ValantClinicalDoc — AgentCore project

This is the AgentCore CLI project that hosts the orchestrator + specialist
sub-agents. The clinician-facing Cloudscape UI lives one level up at
`../web/`. See the [top-level README](../README.md) and
[CLAUDE.md](../CLAUDE.md) for the big-picture architecture.

## Layout

```
ValantClinicalDoc/
├── agentcore/
│   ├── agentcore.json     # Project config — `agentcore validate`
│   ├── aws-targets.json   # Account + region (us-west-2)
│   ├── .env.local         # Secrets (gitignored) — set MEMORY_ID here
│   └── cdk/               # CDK infrastructure
└── app/
    └── ClinicalDocAgent/
        ├── main.py                   # Orchestrator entrypoint
        ├── tools/clinical.py         # 4 specialist sub-agents
        ├── fixtures/transcripts.py   # Dummy transcripts + patients
        ├── model/load.py             # Tiered Bedrock loader
        └── pyproject.toml
```

## Common commands

| Command | Description |
|---------|-------------|
| `uv run python app/ClinicalDocAgent/main.py` | Run the orchestrator on `:8080` |
| `agentcore validate` | Validate `agentcore.json` |
| `agentcore deploy` | Deploy to AgentCore Runtime via CDK |
| `agentcore invoke` | Interactive session with deployed agent |
| `agentcore add` | Add memory / gateway / target |
| `agentcore logs --since 30m` | Stream recent runtime logs |
| `agentcore traces list` | List execution traces |
| `agentcore destroy` | Tear down all deployed resources |

## Environment variables

| Var | Used for |
|-----|----------|
| `AWS_REGION` | Default: `us-west-2` |
| `MEMORY_ID` | Optional. AgentCore Memory resource id. When set, the orchestrator wires `AgentCoreMemorySessionManager`. |
| `ACTOR_ID` | Default: `clinician`. Identifies the memory actor namespace. |
| `ORCHESTRATOR_MODEL_TIER` | `opus` / `sonnet` / `haiku`. Default `sonnet`. |
| `NOTE_MODEL_TIER` | Default `sonnet`. |
| `CODING_MODEL_TIER` | Default `sonnet`. |
| `QA_MODEL_TIER` | Default `haiku` (fast, cheap). |

All three Claude tiers map to `us.anthropic.*` inference profiles in
`us-west-2`. See `app/ClinicalDocAgent/model/load.py`.

## Documentation

- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
- [Strands Agents SDK](https://strandsagents.com/)
- [Cloudscape Design System](https://cloudscape.design/)
