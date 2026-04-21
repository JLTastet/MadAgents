from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI

from madagents.config import REASONING_EFFORT_LEVELS
from madagents.llm import vllm_patches  # noqa: F401  -- installs reasoning_content patch on import
from madagents.llm import vllm_tokens
from madagents.llm.runtime import LLMRuntime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model-family lookup tables
# ---------------------------------------------------------------------------

# Sampling presets by model-family prefix. First match wins; "default" is fallback.
_SAMPLING_PRESETS: dict[str, dict[str, float]] = {
    "qwen": {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0},
    "default": {"temperature": 0.7, "top_p": 0.9, "top_k": 0, "min_p": 0.0},
}

# Per-family mapping from MadAgents reasoning_effort to the ``extra_body``
# kwargs that realize it on vLLM. Each family must cover every effort level
# in REASONING_EFFORT_LEVELS — enforced by the assert below so a new level
# added in MadAgents fails loud here until every family is updated.
_THINKING_CONTROL: dict[str, dict[str, dict]] = {
    "qwen": {
        "minimal": {"chat_template_kwargs": {"enable_thinking": False}},
        "low":     {"chat_template_kwargs": {"enable_thinking": False}},
        "medium":  {"chat_template_kwargs": {"enable_thinking": True}},
        "high":    {"chat_template_kwargs": {"enable_thinking": True}},
    },
    # "gpt-oss": {...},  # when we add it
}

for _family, _mapping in _THINKING_CONTROL.items():
    assert set(_mapping) == set(REASONING_EFFORT_LEVELS), (
        f"_THINKING_CONTROL[{_family!r}] must map exactly "
        f"{set(REASONING_EFFORT_LEVELS)}; got {set(_mapping)}"
    )

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_vllm_url() -> str:
    """Read vLLM base URL from env, falling back to localhost:8200."""
    return os.environ.get("VLLM_API_BASE", "http://localhost:8200/v1")


def _resolve_vllm_model() -> str:
    """Read the HuggingFace model ID that vLLM was started with."""
    model = os.environ.get("VLLM_MODEL", "").strip()
    if not model:
        raise RuntimeError(
            "VLLM_MODEL environment variable is not set. "
            "It must match the model ID passed to vLLM (e.g. Qwen/Qwen3.5-27B-FP8)."
        )
    return model


def _get_sampling_defaults(model_name: str) -> dict[str, float]:
    """Look up sampling preset by model-family prefix."""
    lower = model_name.lower()
    for prefix, preset in _SAMPLING_PRESETS.items():
        if prefix != "default" and lower.startswith(prefix):
            return preset
    return _SAMPLING_PRESETS["default"]


def _thinking_family(model_name: str) -> str | None:
    """Return the ``_THINKING_CONTROL`` key matching ``model_name``'s prefix, or None."""
    lower = model_name.lower()
    for prefix in _THINKING_CONTROL:
        if lower.startswith(prefix):
            return prefix
    return None


def _get_existing_bound_max_tokens(llm: Any) -> int | None:
    """Return any ``max_tokens`` already bound on ``llm`` via ``.bind()``.

    LangChain's ``RunnableBinding.bind()`` flattens chained bind calls into
    a single binding layer (``kwargs = {**old, **new}``), so checking the
    top-level ``kwargs`` is sufficient. Returns ``None`` if no caller has
    bound a value.
    """
    kwargs = getattr(llm, "kwargs", None)
    if isinstance(kwargs, dict):
        val = kwargs.get("max_tokens")
        if isinstance(val, int) and val > 0:
            return val
    return None


def _reject_unsupported_caller_max_tokens(max_tokens: Any) -> None:
    """Fail loud on obvious misuses of ``create_chat_model``'s ``max_tokens``.

    ``VLLMRuntime`` ignores the construction-time ``max_tokens`` entirely;
    the real cap is computed per call in ``invoke()``. Behaviour by value:

    * ``0 < max_tokens < VLLM_DEFAULT_MAX_OUTPUT`` → **raise**. A value this
      small almost certainly means the caller *meant* it as a cap; silently
      dropping it would be surprising.
    * otherwise (including the ``1_000_000`` sentinel every current call
      site passes) → silently ignored. Signal-to-noise is too low to reject
      (test fixtures, docs, "no opinion" defaults all land here).

    To actually cap output, wrap the returned llm with
    ``llm.bind(max_tokens=N)``. ``invoke()`` honours caller binds in either
    direction — tighter wins silently, looser wins with a WARNING and may
    trigger a vLLM rejection if it overflows the context window.
    """
    if isinstance(max_tokens, int) and 0 < max_tokens < vllm_tokens.VLLM_DEFAULT_MAX_OUTPUT:
        raise RuntimeError(
            f"VLLMRuntime ignores caller-configured max_tokens ({max_tokens}); "
            f"value is below the runtime default ceiling "
            f"({vllm_tokens.VLLM_DEFAULT_MAX_OUTPUT}) and would silently be "
            f"discarded. If you actually want a per-call cap, use "
            f"``llm.bind(max_tokens=N)`` on the returned instance; ``invoke()`` "
            f"honours it (tighter wins silently, looser wins with a WARNING)."
        )


def _get_model_name(llm: Any) -> str:
    """Extract model name from an LLM instance or RunnableBinding chain.

    ChatOpenAI uses ``model_name`` as the real Pydantic field (``model`` is
    only a constructor alias), while ChatAnthropic uses ``model`` directly.
    We check both, preferring ``model_name``.
    """
    for attr in ("model_name", "model"):
        val = getattr(llm, attr, None)
        if isinstance(val, str) and val:
            return val
    for wrapper_attr in ("first", "bound"):
        inner = getattr(llm, wrapper_attr, None)
        if inner:
            for attr in ("model_name", "model"):
                val = getattr(inner, attr, None)
                if isinstance(val, str) and val:
                    return val
    return ""


# ---------------------------------------------------------------------------
# Message preprocessing (ported from proxy/vllm_compat.py, adapted for
# LangChain BaseMessage objects instead of raw dicts)
# ---------------------------------------------------------------------------


def _extract_text(content: Any) -> str:
    """Extract plain text from a message's content field.

    Content may be a string or a list of content blocks (e.g.
    ``[{"type": "text", "text": "..."}]``).
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n\n".join(parts) if parts else ""
    return str(content) if content else ""


def _consolidate_system_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Merge all system/developer messages into a single SystemMessage at index 0.

    Open-source chat templates (Qwen, Llama, DeepSeek, etc.) require all
    system-role content at the very beginning.  MadAgents injects developer-role
    instructions mid-conversation (via ``build_preamble()`` with
    ``__openai_role__: "developer"``), and some agents add system messages
    between user/assistant turns.  vLLM rejects requests where a system message
    appears after user/assistant messages, producing a template error.

    ::

        BEFORE consolidation:            AFTER consolidation:
        +------------------------+       +------------------------+
        | SystemMessage("You are |       | SystemMessage(         |
        |   a physics assistant")|--+    |   "You are a physics   |
        +------------------------+  |    |    assistant\\n\\n     |
        | HumanMessage("Run DY") |  +--->|    Use tools always")  |
        +------------------------+  |    +------------------------+
        | AIMessage("Starting…") |  |    | HumanMessage("Run DY") |
        +------------------------+  |    +------------------------+
        | SystemMessage("Use     |--+    | AIMessage("Starting…") |
        |   tools always")       |       +------------------------+
        +------------------------+       | HumanMessage("Go on")  |
        | HumanMessage("Go on")  |       +------------------------+
        +------------------------+

    Returns a new list -- the original is not mutated.
    """
    if not messages:
        return []

    system_parts: list[str] = []
    other: list[BaseMessage] = []

    for msg in messages:
        is_system = isinstance(msg, SystemMessage)
        is_developer = (
            not is_system
            and getattr(msg, "additional_kwargs", {}).get("__openai_role__") == "developer"
        )
        if is_system or is_developer:
            text = _extract_text(msg.content)
            if text:
                system_parts.append(text)
        else:
            other.append(msg)

    if not system_parts:
        return list(messages)

    merged = SystemMessage(content="\n\n".join(system_parts))
    return [merged, *other]


def _fix_trailing_assistant(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Drop a trailing AIMessage so vLLM starts a fresh assistant turn.

    MadAgents conversations frequently end with an assistant message because
    the orchestrator dispatches work via tool calls and worker summaries
    return as ``AIMessage``.  A trailing assistant message is problematic
    because vLLM interprets it as an incomplete turn to continue (via
    ``continue_final_message``), producing empty output for already-complete
    responses.  This breaks tool calling and structured output.

    The obvious alternative — appending a synthetic user message like
    "Continue." — doesn't work either: Qwen reacts to it with
    meta-commentary ("The user is waiting for me to continue...") instead
    of doing useful work.  Every trailing-message variation we tried failed.

    Simply dropping the trailing assistant message is safe because its content
    is already captured in the orchestrator's ``orchestrator_messages`` stream
    (v1.1's dual message stream design).

    ::

        BEFORE fix:                  AFTER fix:
        +----------------------+     +----------------------+
        | SystemMessage(...)   |     | SystemMessage(...)   |
        +----------------------+     +----------------------+
        | HumanMessage("...")  |     | HumanMessage("...")  |
        +----------------------+     +----------------------+
        | AIMessage("Plan...") |     | ToolMessage(result)  |
        +----------------------+     +----------------------+
        | ToolMessage(result)  |
        +----------------------+
        | AIMessage("Done,     |---- dropped
        |   here is summary")  |
        +----------------------+

    Returns a new list -- the original is not mutated.
    """
    if messages and isinstance(messages[-1], AIMessage):
        return messages[:-1]
    return list(messages)


# ---------------------------------------------------------------------------
# VLLMRuntime
# ---------------------------------------------------------------------------


class VLLMRuntime(LLMRuntime):
    """Runtime for models served by vLLM via the OpenAI-compatible API."""

    def create_chat_model(
        self,
        *,
        model: str,
        reasoning_effort: str,
        verbosity: str | None,
        max_tokens: int,
    ) -> ChatOpenAI:
        vllm_model = _resolve_vllm_model()
        vllm_url = _resolve_vllm_url()
        sampling = _get_sampling_defaults(vllm_model)

        _reject_unsupported_caller_max_tokens(max_tokens)

        # No static max_tokens on ChatOpenAI: ``invoke()`` binds a dynamic
        # value from the exact prompt size per call.
        return ChatOpenAI(
            model=vllm_model,
            base_url=vllm_url,
            api_key=os.environ.get("VLLM_API_KEY", "dummy"),
            use_responses_api=False,
            temperature=sampling["temperature"],
            top_p=sampling["top_p"],
            extra_body={"top_k": sampling["top_k"], "min_p": sampling["min_p"]},
        )

    def build_preamble(self, *, prompt: str) -> list[BaseMessage]:
        return [SystemMessage(content=prompt)]

    def prepare_tools(self, tools: list) -> tuple[list, list]:
        llm_tools: list = []
        node_tools: list = []
        for tool in tools:
            if isinstance(tool, dict):
                continue  # Strip web_search and other provider-specific dict tools
            llm_tools.append(tool)
            node_tools.append(tool)
        return llm_tools, node_tools

    def bind_reasoning(
        self,
        llm: Any,
        *,
        reasoning_effort: str,
        adaptive: bool = True,  # Unused; Anthropic-only adaptive-thinking hint.
    ) -> Any:
        effort = (reasoning_effort or "").strip().lower() or None
        family = _thinking_family(_get_model_name(llm))
        if not effort or family is None:
            return llm  # No applicable thinking control — use model default.
        return llm.bind(extra_body=_THINKING_CONTROL[family][effort])

    def bind_reasoning_trace(self, llm: Any) -> Any:
        return llm  # No-op — encrypted reasoning traces are OpenAI-specific

    def invoke(
        self,
        llm: Any,
        messages: list[BaseMessage],
        *,
        reasoning_effort: str | None = None,
        agent_name: str | None = None,
    ) -> Any:
        messages = _consolidate_system_messages(list(messages))
        messages = _fix_trailing_assistant(messages)
        dynamic_max = vllm_tokens.prepare_invocation(
            llm, messages, agent_name=agent_name,
        )
        # Caller's ``.bind(max_tokens=N)`` takes precedence, in either
        # direction.  Tighter is safe and silent.  Looser is honoured with a
        # WARNING: it may exceed the remaining context budget, in which case
        # vLLM will reject the request.
        caller_max = _get_existing_bound_max_tokens(llm)
        if caller_max is not None and caller_max != dynamic_max:
            if caller_max > dynamic_max:
                logger.warning(
                    "vllm_runtime: caller-bound max_tokens=%d exceeds the "
                    "dynamic cap %d for agent=%s. Honouring it; vLLM will "
                    "reject the request if prompt_tokens + max_tokens > "
                    "MAX_MODEL_LEN.",
                    caller_max, dynamic_max, agent_name,
                )
            dynamic_max = caller_max
        bound = llm.bind(max_tokens=dynamic_max)
        return bound.invoke(messages)

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
        agent_name: str | None = None,  # Reserved for future per-agent policy in structured-output path.
    ) -> Any:
        # vLLM's structured-output path doesn't yet support tool-calling or
        # reasoning-trace passthrough the way OpenAI/Anthropic runtimes do.
        # Fail loud rather than silently drop the kwargs.
        if tools is not None:
            raise NotImplementedError(
                "VLLMRuntime.with_structured_output does not support `tools`. "
                "Tool-calling structured output would mirror OpenAI's "
                "_structured_output_with_tools path; not implemented yet."
            )
        if include_reasoning_trace:
            raise NotImplementedError(
                "VLLMRuntime.with_structured_output does not support "
                "`include_reasoning_trace`. Reasoning content is captured via "
                "the vllm_patches monkey-patch on regular invoke() calls."
            )
        if isinstance(reasoning_effort, str) and reasoning_effort:
            raise NotImplementedError(
                "VLLMRuntime.with_structured_output does not forward "
                "`reasoning_effort`. Call bind_reasoning on the llm before "
                "passing it in."
            )
        kwargs: dict[str, Any] = {"include_raw": include_raw}
        if strict is not None:
            kwargs["strict"] = strict
        return llm.with_structured_output(schema, **kwargs)
