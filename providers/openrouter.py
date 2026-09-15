"""OpenRouter API client with automatic model fallback."""

import json
import logging
import uuid
from typing import Any, Callable

import httpx

from core.fallback_parser import parse_prompted_tool_calls
from core.types import ProviderResponse, ToolCall
from providers.base import LLMProvider

logger = logging.getLogger(__name__)

# Primary free models with tool-calling capabilities, ending with meta-router fallback
DEFAULT_CANDIDATE_MODELS: list[str] = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "google/gemma-4-31b-it:free",
    "openrouter/free",
]


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider implementing multi-model fallback and tool calling."""

    def __init__(
        self,
        api_key: str,
        candidate_models: list[str] | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 60.0,
        on_fallback: Callable[[str, Exception | str], None] | None = None,
        model_native_tools: dict[str, bool] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouterProvider.")
        self.api_key = api_key
        self.candidate_models = candidate_models or list(DEFAULT_CANDIDATE_MODELS)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.on_fallback = on_fallback
        self.model_native_tools = model_native_tools or {}

    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ProviderResponse:
        """Attempt completion across candidate models until one succeeds."""
        errors: list[str] = []

        for model in self.candidate_models:
            try:
                return self._call_model(model, messages, tools)
            except Exception as exc:
                err_msg = f"Model '{model}' failed: {exc}"
                logger.warning(err_msg)
                errors.append(err_msg)
                if self.on_fallback:
                    self.on_fallback(model, exc)

        combined_errors = "\n".join(errors)
        raise RuntimeError(
            f"All candidate models exhausted without success:\n{combined_errors}"
        )

    def _call_model(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ProviderResponse:
        """Call OpenRouter completions API for a specific model."""
        allow_native = self.model_native_tools.get(model, True)
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
        }
        if tools and allow_native:
            payload["tools"] = tools

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/coding-agent",
            "X-Title": "Coding Agent CLI",
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

        # If model rejected native tools, retry without tools parameter (prompted mode)
        if response.status_code in (400, 404) and "tool" in response.text.lower() and "tools" in payload:
            logger.info(f"Model '{model}' does not support native tools. Retrying in prompted mode.")
            self.model_native_tools[model] = False
            del payload["tools"]
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )

        if response.status_code != 200:
            raise RuntimeError(
                f"HTTP {response.status_code}: {response.text}"
            )

        data = response.json()
        return self._parse_response(data, requested_model=model)

    def _parse_response(
        self, data: dict[str, Any], requested_model: str
    ) -> ProviderResponse:
        """Parse OpenRouter completion response into standardized ProviderResponse."""
        choices = data.get("choices", [])
        if not choices:
            raise ValueError(f"Empty choices returned in response: {data}")

        first_choice = choices[0]
        message = first_choice.get("message", {})
        content = message.get("content")
        raw_tool_calls = message.get("tool_calls") or []

        parsed_tool_calls: list[ToolCall] = []
        for raw_call in raw_tool_calls:
            call_id = raw_call.get("id") or f"call_{uuid.uuid4().hex[:8]}"
            fn_data = raw_call.get("function", {})
            name = fn_data.get("name", "")
            raw_args = fn_data.get("arguments", "{}")

            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args) if raw_args.strip() else {}
                except json.JSONDecodeError:
                    args = {"raw_arguments": raw_args}
            elif isinstance(raw_args, dict):
                args = raw_args
            else:
                args = {}

            parsed_tool_calls.append(ToolCall(id=call_id, name=name, arguments=args))

        # If no native tool calls were returned, check for ReAct fenced JSON blocks in content
        if not parsed_tool_calls and content:
            thought, prompted_calls, parse_error = parse_prompted_tool_calls(content)
            if prompted_calls:
                parsed_tool_calls = prompted_calls
                content = thought or None

        model_used = data.get("model") or requested_model
        return ProviderResponse(
            content=content,
            tool_calls=parsed_tool_calls,
            model_used=model_used,
            raw_response=data,
        )
