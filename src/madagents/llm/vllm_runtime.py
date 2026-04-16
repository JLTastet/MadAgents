from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_openai import ChatOpenAI

from madagents.llm.runtime import LLMRuntime

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_max_model_len = int(os.environ.get("MAX_MODEL_LEN", "65536"))
VLLM_MAX_OUTPUT = _max_model_len // 2

# ---------------------------------------------------------------------------
# Model-family lookup tables
# ---------------------------------------------------------------------------

# Sampling presets by model-family prefix. First match wins; "default" is fallback.
_SAMPLING_PRESETS: dict[str, dict[str, float]] = {
    "qwen": {"temperature": 0.6, "top_p": 0.95, "top_k": 20, "min_p": 0.0},
    "default": {"temperature": 0.7, "top_p": 0.9, "top_k": 0, "min_p": 0.0},
}

# Thinking control per model family (extra_body kwargs to enable/disable).
# Both directions supported: some models think by default (larger Qwen3.5),
# others don't (smaller variants may default to no-think).
_THINKING_CONTROL: dict[str, dict | None] = {
    "qwen": {
        "enable": {"chat_template_kwargs": {"enable_thinking": True}},
        "disable": {"chat_template_kwargs": {"enable_thinking": False}},
    },
    # "gpt-oss": None,  # No thinking support
}

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


def _get_thinking_control(model_name: str) -> dict | None:
    """Look up thinking control dict by model-family prefix."""
    lower = model_name.lower()
    for prefix, control in _THINKING_CONTROL.items():
        if lower.startswith(prefix):
            return control
    return None


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
    of doing useful work.  This was tested exhaustively during the Anthropic
    compat shim development; every trailing-message variation failed.

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
        capped = min(max_tokens, VLLM_MAX_OUTPUT) if isinstance(max_tokens, int) else VLLM_MAX_OUTPUT
        sampling = _get_sampling_defaults(vllm_model)

        return ChatOpenAI(
            model=vllm_model,
            base_url=vllm_url,
            api_key=os.environ.get("VLLM_API_KEY", "dummy"),
            use_responses_api=False,
            temperature=sampling["temperature"],
            top_p=sampling["top_p"],
            max_tokens=capped,
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
        self, llm: Any, *, reasoning_effort: str, adaptive: bool = True
    ) -> Any:
        effort = (reasoning_effort or "").strip().lower()
        model_name = _get_model_name(llm)
        control = _get_thinking_control(model_name)

        if control is None:
            return llm  # Model doesn't support thinking control

        if effort in ("minimal", "low"):
            return llm.bind(extra_body=control["disable"])
        # Explicitly enable thinking for high/medium effort.
        # This handles models where thinking is off by default.
        return llm.bind(extra_body=control["enable"])

    def bind_reasoning_trace(self, llm: Any) -> Any:
        return llm  # No-op — encrypted reasoning traces are OpenAI-specific

    def invoke(
        self,
        llm: Any,
        messages: list[BaseMessage],
        *,
        reasoning_effort: str | None = None,
    ) -> Any:
        messages = _consolidate_system_messages(list(messages))
        messages = _fix_trailing_assistant(messages)
        return llm.invoke(messages)

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
    ) -> Any:
        kwargs: dict[str, Any] = {"include_raw": include_raw}
        if strict is not None:
            kwargs["strict"] = strict
        return llm.with_structured_output(schema, **kwargs)
