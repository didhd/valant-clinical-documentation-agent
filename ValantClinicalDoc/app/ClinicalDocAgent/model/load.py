"""Bedrock model loader with frontier-tier routing.

Three tiers backed by us.anthropic.* inference profiles in us-west-2:
  - opus    : Claude Opus 4.6   (deep reasoning, expensive)
  - sonnet  : Claude Sonnet 4.6 (default — best speed/intelligence)
  - haiku   : Claude Haiku 4.5  (fast, cheap — good for QA validation)

Tier mapping per role can be overridden with env vars without code changes:
  ORCHESTRATOR_MODEL_TIER, NOTE_MODEL_TIER, CODING_MODEL_TIER, QA_MODEL_TIER.
"""

from __future__ import annotations

import os
from typing import Literal

from strands.models.bedrock import BedrockModel

Tier = Literal["opus", "sonnet", "haiku"]

TIER_TO_MODEL_ID: dict[Tier, str] = {
    "opus": "us.anthropic.claude-opus-4-6-v1",
    "sonnet": "us.anthropic.claude-sonnet-4-6",
    "haiku": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
}

ROLE_DEFAULT_TIER: dict[str, Tier] = {
    "orchestrator": "sonnet",
    "note": "sonnet",
    "coding": "sonnet",
    "qa": "haiku",
}


def _resolve_tier(role: str) -> Tier:
    env_key = f"{role.upper()}_MODEL_TIER"
    requested = os.environ.get(env_key, "").lower().strip()
    if requested in TIER_TO_MODEL_ID:
        return requested  # type: ignore[return-value]
    return ROLE_DEFAULT_TIER.get(role, "sonnet")


def load_model(role: str = "orchestrator") -> BedrockModel:
    """Return a BedrockModel for the given role.

    Args:
        role: One of "orchestrator", "note", "coding", "qa". Unknown roles
              default to the sonnet tier.
    """
    tier = _resolve_tier(role)
    return BedrockModel(model_id=TIER_TO_MODEL_ID[tier])
