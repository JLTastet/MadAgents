from __future__ import annotations

from typing import Any, Protocol

from langchain_core.messages import BaseMessage


class LLMRuntime(Protocol):
    """Provider runtime abstraction used by agent orchestration code."""

    def create_chat_model(
        self,
        *,
        model: str,
        reasoning_effort: str,
        verbosity: str | None,
        max_tokens: int,
    ) -> Any:
        """Create a chat model instance for the provider."""

    def build_preamble(
        self,
        *,
        prompt: str,
    ) -> list[BaseMessage]:
        """Build provider-specific instruction preamble messages."""

    def prepare_tools(self, tools: list) -> tuple[list, list]:
        """Return (llm_tools, node_tools) after provider-specific mapping."""

    def bind_reasoning(self, llm: Any, *, reasoning_effort: str, adaptive: bool = True) -> Any:
        """Bind request-scoped reasoning controls."""

    def bind_reasoning_trace(self, llm: Any) -> Any:
        """Bind request options needed for encrypted reasoning traces."""

    def count_tokens(
        self,
        messages: list[BaseMessage],
        *,
        tools: list | None = None,
        chat_template_kwargs: dict | None = None,
    ) -> int | None:
        """Exact prompt-token count for ``messages``, or ``None`` if unsupported.

        Providers with a server-side tokenizer (e.g. vLLM's ``/tokenize``)
        override this; the concrete default returns ``None`` so callers fall back
        to a heuristic. ``tools`` and ``chat_template_kwargs`` mirror what the
        provider would send so the count matches the rendered prompt.
        """
        return None

    def invoke(
        self,
        llm: Any,
        messages: list[BaseMessage],
        *,
        reasoning_effort: str | None = None,
        agent_name: str | None = None,
    ) -> Any:
        """Invoke a model with provider-specific call arguments.

        ``agent_name`` is an advisory hint identifying the caller — runtimes
        may use it to apply per-agent policies (e.g. sampling overrides,
        output-budget ceilings). Runtimes that don't need it ignore it.
        """

    def with_structured_output(
        self,
        llm: Any,
        schema: Any,
        *,
        include_raw: bool,
        strict: bool | None = None,
        tools: list | None = None,
        include_reasoning_trace: bool = False,
        reasoning_effort: str | None = None,
        agent_name: str | None = None,
    ) -> Any:
        """Create a structured-output bound model with provider-specific args."""
