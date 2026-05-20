# Valant Clinical Documentation Agent — local dev shortcuts
# Run `make help` for the list.

AGENT_DIR := ValantClinicalDoc/app/ClinicalDocAgent
WEB_DIR   := web
AGENT_PORT := 8080
WEB_PORT   := 5173

.PHONY: help install agent web dev clean check

help:
	@echo "Valant Clinical Documentation Agent — make targets"
	@echo ""
	@echo "  make install   Install Python (uv) + Node deps for the first time"
	@echo "  make agent     Run the AgentCore orchestrator on :$(AGENT_PORT)"
	@echo "  make web       Run the Cloudscape UI on :$(WEB_PORT)"
	@echo "  make dev       Run both agent + UI concurrently (needs npx concurrently)"
	@echo "  make check     Validate agentcore.json + Python syntax"
	@echo "  make clean     Stop processes on :$(AGENT_PORT) and :$(WEB_PORT)"

install:
	@echo "→ Installing Python deps via uv"
	cd $(AGENT_DIR) && uv sync
	@echo "→ Installing web deps via npm"
	cd $(WEB_DIR) && npm install
	@echo "→ Creating env stubs if missing"
	@test -f ValantClinicalDoc/agentcore/.env.local || \
	  (touch ValantClinicalDoc/agentcore/.env.local && \
	   echo "# Set MEMORY_ID + ACTOR_ID after `agentcore add memory`" \
	     > ValantClinicalDoc/agentcore/.env.local)
	@echo ""
	@echo "✓ Install complete. Run 'make dev' to launch both processes."

agent:
	cd $(AGENT_DIR) && AWS_REGION=$${AWS_REGION:-us-west-2} uv run python main.py

web:
	cd $(WEB_DIR) && npm run dev

dev:
	@echo "→ Launching agent (:$(AGENT_PORT)) + UI (:$(WEB_PORT)) — Ctrl-C stops both"
	@npx --yes concurrently -k -n agent,web -c blue,green \
	  "$(MAKE) agent" "$(MAKE) web"

check:
	cd ValantClinicalDoc && agentcore validate
	cd $(AGENT_DIR) && uv run python -m py_compile main.py tools/clinical.py \
	  fixtures/transcripts.py model/load.py
	@echo "✓ checks passed"

clean:
	-@lsof -nP -iTCP:$(AGENT_PORT) -sTCP:LISTEN 2>/dev/null | \
	  awk 'NR>1{print $$2}' | xargs -r kill 2>/dev/null || true
	-@lsof -nP -iTCP:$(WEB_PORT) -sTCP:LISTEN 2>/dev/null | \
	  awk 'NR>1{print $$2}' | xargs -r kill 2>/dev/null || true
	@echo "✓ ports $(AGENT_PORT) and $(WEB_PORT) cleared"
