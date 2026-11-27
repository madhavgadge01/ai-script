import time
import json
from typing import Type, TypeVar, Optional, Any
from pydantic import BaseModel
from google import genai
from google.genai import types

from config.settings import settings
from app.ai.tracker import CostTracker

T = TypeVar("T", bound=BaseModel)

class GeminiQuotaExhaustedError(RuntimeError):
    """Raised when the Gemini API returns a 429 Quota Exhausted or Resource Exhausted error."""
    pass

class GeminiClient:
    """
    Client for Google Gemini API using the modern google-genai SDK.
    Supports structured outputs, exponential backoff retries, and token tracking.
    """

    def __init__(self, api_key: str = None, model: str = None, tracker: CostTracker = None):
        self.api_key = api_key or settings.gemini_api_key
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set. Please add it to your .env file.")
        
        self.model = model or settings.gemini_model
        self.tracker = tracker or CostTracker(
            max_tokens=settings.max_tokens_per_doc,
            max_cost_usd=settings.max_cost_usd_per_doc
        )
        # Initialize Google GenAI client with 120s timeout for structured generation
        self.client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(timeout=120000)
        )

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        max_retries: int = 3,
        temperature: float = 0.2,
    ) -> T:
        """
        Calls Gemini API with structured Pydantic schema validation and automatic retries.
        """
        retries = 0
        backoff = 2.0

        while retries <= max_retries:
            start_time = time.time()
            try:
                # Configure generation with schema
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    system_instruction=system_instruction,
                    temperature=temperature,
                )

                response = self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=config,
                )

                duration = time.time() - start_time

                # Track tokens
                usage = getattr(response, "usage_metadata", None)
                in_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
                out_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0

                self.tracker.record_usage(
                    model=self.model,
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                    duration=duration,
                    retries=retries,
                )

                # Parse validated Pydantic model
                raw_text = response.text
                parsed_data = response_schema.model_validate_json(raw_text)
                return parsed_data

            except Exception as e:
                err_str = str(e).lower()
                # Fast fail on definitive quota or billing exhaustion
                if "resource_exhausted" in err_str or ("quota" in err_str and "exceeded" in err_str):
                    raise GeminiQuotaExhaustedError(
                        f"Gemini Free Tier Quota Exhausted on model '{self.model}': {e}"
                    ) from e

                retries += 1
                if retries > max_retries:
                    if "429" in err_str:
                        raise GeminiQuotaExhaustedError(
                            f"Gemini API rate limit (429) exceeded after {max_retries} retries: {e}"
                        ) from e
                    raise RuntimeError(f"Gemini API failed after {max_retries} retries. Error: {e}") from e

                # Back off on rate-limit (429) or transient 5xx errors
                if "429" in err_str or "503" in err_str:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    time.sleep(1.0)

class Tuple_Result:
    pass
