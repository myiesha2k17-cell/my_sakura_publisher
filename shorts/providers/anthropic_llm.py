"""Claude via the Anthropic SDK: structured JSON output, server-side refusal fallbacks.

We call `beta.messages.create` (not `.parse`) so we can read `stop_reason` before validating:
`.parse` validates every text block first, which would turn a refusal into a validation error.
"""
from __future__ import annotations

import anthropic
from anthropic.lib._parse._transform import to_json_output_format

from shorts.providers.base import ProviderError, Refusal

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicLLM:
    def __init__(self, api_key: str, model: str, client=None):
        self.model = model
        self.client = client or anthropic.Anthropic(api_key=api_key)

    def parse(self, system, user, schema):
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": to_json_output_format(schema)},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as e:
            raise ProviderError("Anthropic rejected the API key (401). Check ANTHROPIC_API_KEY.") from e
        except anthropic.RateLimitError as e:
            raise ProviderError("Anthropic rate limit reached. Wait a minute and try again.") from e
        except anthropic.APIStatusError as e:
            raise ProviderError(f"Anthropic API error ({e.status_code}). Try again shortly.") from e
        except anthropic.APIConnectionError as e:
            raise ProviderError("Could not reach the Anthropic API. Check the network and try again.") from e
        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None) if response.stop_details else None
            raise Refusal(category or "refusal")
        if response.stop_reason == "max_tokens":
            raise ProviderError("Claude's reply was cut off before the script was finished. Try again.")
        text = "".join(block.text for block in response.content if getattr(block, "type", None) == "text")
        return schema.model_validate_json(text)  # a ValidationError here gets one retry in script._ask
