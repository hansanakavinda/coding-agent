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

# Default meta-router model that automatically routes to the best available free model
DEFAULT_MODEL: str = "openrouter/free"
DEFAULT_CANDIDATE_MODELS: list[str] = [DEFAULT_MODEL]


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider implementing automatic free model routing and tool calling."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        candidate_models: list[str] | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 60.0,
        on_fallback: Callable[[str, Exception | str], None] | None = None,
        model_native_tools: dict[str, bool] | None = None,
        on_rate_limit: Callable[[str], str | None] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY is required for OpenRouterProvider.")
        self.api_key = api_key
        if candidate_models:
            self.candidate_models = list(candidate_models)
        else:
            self.candidate_models = [model]
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.on_fallback = on_fallback
        self.model_native_tools = model_native_tools or {}
        self.on_rate_limit = on_rate_limit

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
                err_str = str(exc).lower()
                is_rate_limited = "429" in err_str or "limit" in err_str or "quota" in err_str or "credit" in err_str
                is_auth_error = (
                    "401" in err_str
                    or "unauthorized" in err_str
                    or ("http 400:" in err_str and not err_str.strip().endswith("}"))
                    or "invalid api key" in err_str
                    or "user has exceeded" in err_str
                    or "no endpoints found" in err_str
                )

                # If rate-limited or auth/key error and a prompt callback is provided, request new key
                if (is_rate_limited or is_auth_error) and self.on_rate_limit:
                    new_key = self.on_rate_limit(self.api_key)
                    if new_key and new_key != self.api_key:
                        self.api_key = new_key
                        try:
                            return self._call_model(model, messages, tools)
                        except Exception as retry_exc:
                            exc = retry_exc

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
