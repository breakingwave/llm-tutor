import time
import logging
from collections.abc import AsyncGenerator

import litellm

from app.config import ModelsConfig, PromptsConfig, ModelConfig
from app.models.api_log import APICallLog
from app.services.api_logger import APILogger

logger = logging.getLogger("llm_tutor.llm")


class LLMService:
    def __init__(
        self,
        models_config: ModelsConfig,
        prompts_config: PromptsConfig,
        api_logger: APILogger,
        llm_base_url: str = "",
        llm_api_key: str = "",
    ):
        self.models_config = models_config
        self.prompts_config = prompts_config
        self.api_logger = api_logger
        self.llm_base_url = llm_base_url
        self.llm_api_key = llm_api_key

    def get_model_config(self, module: str, operation: str) -> ModelConfig:
        return self.models_config.get_model_config(module, operation)

    def get_prompt_template(self, module: str, operation: str):
        return self.prompts_config.get_prompt(module, operation)

    def build_messages(
        self,
        module: str,
        operation: str,
        user_vars: dict,
        system_override: str | None = None,
        extra_messages: list[dict] | None = None,
    ) -> list[dict]:
        """Build messages list from prompt templates + variables."""
        template = self.get_prompt_template(module, operation)

        if system_override:
            system_content = system_override
        elif isinstance(template, str):
            system_content = template.format(**user_vars)
        else:
            system_content = template.system.format(**user_vars) if template.system else ""

        messages = []
        if system_content:
            messages.append({"role": "system", "content": system_content})

        if extra_messages:
            messages.extend(extra_messages)

        if not isinstance(template, str) and template.user:
            user_content = template.user.format(**user_vars)
            messages.append({"role": "user", "content": user_content})

        return messages

    async def completion(
        self,
        module: str,
        operation: str,
        messages: list[dict],
        session_id: str | None = None,
        **kwargs,
    ) -> str:
        """Make a non-streaming LLM call. Returns the response content string."""
        cfg = self.get_model_config(module, operation)
        model = kwargs.pop("model", None) or cfg.model
        kwargs.pop("temperature", None)
        max_tokens = kwargs.pop("max_tokens", None) or cfg.max_tokens
        reasoning_effort = kwargs.pop("reasoning_effort", None) or cfg.reasoning_effort
        response_format = kwargs.pop("response_format", None) or getattr(
            cfg, "response_format", None
        )

        start = time.perf_counter()
        error_str = None
        response_content = ""
        input_tokens = None
        output_tokens = None
        cost = None

        completion_kwargs: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "reasoning_effort": reasoning_effort,
            **kwargs,
        }
        if response_format:
            completion_kwargs["response_format"] = response_format
        if self.llm_base_url:
            completion_kwargs["api_base"] = self.llm_base_url
        if self.llm_api_key:
            completion_kwargs["api_key"] = self.llm_api_key

        try:
            response = await litellm.acompletion(**completion_kwargs)
            response_content = response.choices[0].message.content or ""
            if hasattr(response, "usage") and response.usage:
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
            try:
                cost = litellm.completion_cost(completion_response=response)
            except Exception:
                cost = None
        except Exception as e:
            error_str = str(e)
            raise
        finally:
            latency = (time.perf_counter() - start) * 1000
            self.api_logger.log_call(APICallLog(
                module=module,
                operation=operation,
                service="litellm",
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency,
                cost_estimate_usd=float(cost) if cost is not None else 0.0,
                request_payload={"messages": _summarize_messages(messages)},
                response_payload={"content": response_content[:500]} if response_content else {},
                error=error_str,
                session_id=session_id,
            ))

        return response_content

    async def completion_stream(
        self,
        module: str,
        operation: str,
        messages: list[dict],
        session_id: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[str, None]:
        """Make a streaming LLM call. Yields token strings."""
        cfg = self.get_model_config(module, operation)
        model = kwargs.pop("model", None) or cfg.model
        kwargs.pop("temperature", None)
        max_tokens = kwargs.pop("max_tokens", None) or cfg.max_tokens
        reasoning_effort = kwargs.pop("reasoning_effort", None) or cfg.reasoning_effort
        response_format = kwargs.pop("response_format", None) or getattr(
            cfg, "response_format", None
        )

        start = time.perf_counter()
        error_str = None
        full_content = ""
        input_tokens = None
        output_tokens = None

        completion_kwargs: dict = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "reasoning_effort": reasoning_effort,
            "stream": True,
            **kwargs,
        }
        if response_format:
            completion_kwargs["response_format"] = response_format
        if self.llm_base_url:
            completion_kwargs["api_base"] = self.llm_base_url
        if self.llm_api_key:
            completion_kwargs["api_key"] = self.llm_api_key

        try:
            response = await litellm.acompletion(**completion_kwargs)
            async for chunk in response:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    full_content += delta.content
                    yield delta.content
                if hasattr(chunk, "usage") and chunk.usage:
                    input_tokens = getattr(chunk.usage, "prompt_tokens", None)
                    output_tokens = getattr(chunk.usage, "completion_tokens", None)
        except Exception as e:
            error_str = str(e)
            raise
        finally:
            latency = (time.perf_counter() - start) * 1000
            try:
                cost = litellm.completion_cost(
                    model=model,
                    prompt=str(messages),
                    completion=full_content,
                )
            except Exception:
                cost = None
            self.api_logger.log_call(APICallLog(
                module=module,
                operation=operation,
                service="litellm",
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency,
                cost_estimate_usd=float(cost) if cost is not None else 0.0,
                request_payload={"messages": _summarize_messages(messages)},
                response_payload={"content": full_content[:500]} if full_content else {},
                error=error_str,
                session_id=session_id,
            ))


def _summarize_messages(messages: list[dict], max_content_len: int = 300) -> list[dict]:
    """Summarize messages for logging — truncate long content."""
    summarized = []
    for msg in messages:
        content = msg.get("content", "")
        if len(content) > max_content_len:
            content = content[:max_content_len] + "...[truncated]"
        summarized.append({"role": msg.get("role", ""), "content": content})
    return summarized
