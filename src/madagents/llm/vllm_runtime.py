from __future__ import annotations

import functools
import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from madagents.config import REASONING_EFFORT_LEVELS
from madagents.llm import trace_recorder, vllm_patches  # noqa: F401  -- vllm_patches installs reasoning_content patch on import
from madagents.llm import vllm_tokens
from madagents.llm.runtime import LLMRuntime
from madagents.tools import local_read_pdf_tool, local_web_search_tool

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
        "xhigh":   {"chat_template_kwargs": {"enable_thinking": True}},
        "max":     {"chat_template_kwargs": {"enable_thinking": True}},
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


@functools.lru_cache(maxsize=8)
def _resolve_base_model_name(served_name: str, base_url: str) -> str:
    """Resolve a served name to its base model's name via ``/v1/models``.

    The base name is the ``parent`` field of a LoRA adapter's model card, or
    the served name itself for base models. Failure is a hard error: guessing
    a family from an arbitrary adapter name silently picks wrong defaults.
    """
    req = urllib.request.Request(
        f"{base_url}/models",
        headers={"Authorization": f"Bearer {os.environ.get('VLLM_API_KEY', 'dummy')}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            cards = json.load(resp).get("data", [])
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Cannot resolve the model family of {served_name!r}: "
            f"GET {base_url}/models failed ({exc}). The vLLM server must be "
            f"reachable when the runtime starts."
        ) from exc
    for card in cards:
        if card.get("id") == served_name:
            return card.get("parent") or served_name
    raise RuntimeError(
        f"VLLM_MODEL={served_name!r} is not served at {base_url} "
        f"(available: {[c.get('id') for c in cards]}). It must exactly match "
        f"a served model or loaded adapter name."
    )


def _get_sampling_defaults(base_name: str) -> dict[str, float]:
    """Look up the sampling preset by prefix of the base name (resolve
    adapter names via ``_resolve_base_model_name`` first)."""
    lower = base_name.lower()
    for prefix, preset in _SAMPLING_PRESETS.items():
        if prefix != "default" and lower.startswith(prefix):
            return preset
    return _SAMPLING_PRESETS["default"]


def _thinking_family(base_name: str) -> str | None:
    """Return the ``_THINKING_CONTROL`` key by prefix of the base name (same
    contract as ``_get_sampling_defaults``)."""
    lower = base_name.lower()
    for prefix in _THINKING_CONTROL:
        if lower.startswith(prefix):
            return prefix
    return None


def _get_effective_extra_body(llm: Any) -> dict[str, Any]:
    """Return the ``extra_body`` in effect for ``llm``'s next request.

    The outermost RunnableBinding layer carrying one wins (``.bind()``
    flattens chained binds into it; the walk handles manually-nested
    bindings), falling back to the constructor field, then ``{}``.
    """
    base = llm
    while hasattr(base, "bound") and base.bound is not None:
        base = base.bound
    cur = llm
    while cur is not None and cur is not base:
        kw = getattr(cur, "kwargs", None)
        if isinstance(kw, dict) and isinstance(kw.get("extra_body"), dict):
            return kw["extra_body"]
        cur = getattr(cur, "bound", None)
    candidate = getattr(base, "extra_body", None)
    return candidate if isinstance(candidate, dict) else {}


def _bind_extra_body(llm: Any, updates: dict[str, Any]) -> Any:
    """Bind ``extra_body`` merged over what's already in effect on ``llm``.

    ``.bind(extra_body=...)`` replaces wholesale, which would drop
    constructor sampling params; ``chat_template_kwargs`` merges one level
    deep so template flags from different bind sites compose.
    """
    current = _get_effective_extra_body(llm)
    merged = {**current, **updates}
    cur_ctk = current.get("chat_template_kwargs")
    new_ctk = updates.get("chat_template_kwargs")
    if isinstance(cur_ctk, dict) and isinstance(new_ctk, dict):
        merged["chat_template_kwargs"] = {**cur_ctk, **new_ctk}
    return llm.bind(extra_body=merged)


def _default_template_kwargs() -> dict[str, Any]:
    """The ``chat_template_kwargs`` every agent request carries by default.

    ``VLLM_PRESERVE_THINKING=0`` is a full kill switch: on Qwen3.6 the kwarg
    alone renders empty think blocks on historical turns, so a clean baseline
    needs it gone entirely.
    """
    if os.environ.get("VLLM_PRESERVE_THINKING", "").strip() == "0":
        return {}
    return {"preserve_thinking": True}


def _extract_sampling_params(llm: Any) -> dict[str, Any]:
    """Return sampling params reflecting what's actually bound for the call.

    Reads native ChatOpenAI Pydantic fields (``temperature``, ``top_p``,
    ``seed``) which serialise at OpenAI request top-level, and the effective
    ``extra_body`` (``top_k``, ``min_p``) which is what's on the wire after
    any ``.bind(extra_body=...)`` override. Returns only the keys that are
    present and non-None — callers should treat absence as "not bound at
    this level".
    """
    base = llm
    while hasattr(base, "bound") and base.bound is not None:
        base = base.bound

    out: dict[str, Any] = {}
    for native in ("temperature", "top_p", "seed"):
        v = getattr(base, native, None)
        if v is not None:
            out[native] = v

    extra_body = _get_effective_extra_body(llm)
    for key in ("top_k", "min_p"):
        if extra_body.get(key) is not None:
            out[key] = extra_body[key]
    return out


def _extract_sampled_tokens(result: Any) -> dict[str, Any] | None:
    """Return the sampler's per-token ids and logprobs for one generation.

    The OpenAI-compat message carries only post-parser structure, so the tokens
    the model actually sampled are recoverable solely from the logprobs stream,
    which is pre-parser (think block, raw tool-call text, and the closing
    ``<|im_end|>`` all appear verbatim). Token identity comes from vLLM's
    ``return_tokens_as_token_ids``, which renders each token as ``token_id:N``;
    an entry in any other shape means the extension was not honoured, so the
    whole capture is dropped rather than half-trusted.

    Returns None when the response carries no logprobs (nothing was requested,
    or the backend ignored it).
    """
    metadata = getattr(result, "response_metadata", None) or {}
    entries = ((metadata.get("logprobs") or {}).get("content")) or None
    if not entries:
        return None

    token_ids: list[int] = []
    logprobs: list[float] = []
    try:
        for entry in entries:
            token = entry["token"]
            if not token.startswith("token_id:"):
                raise ValueError(f"token {token!r} is not a token id")
            token_ids.append(int(token.split(":", 1)[1]))
            logprobs.append(float(entry["logprob"]))
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        # Never raise into the caller: a capture is diagnostic, a live agent
        # turn is not. Needs return_tokens_as_token_ids for the id form.
        logger.warning(
            "vllm_runtime: dropping the sampled-token capture for this call "
            "(%s: %s)", type(exc).__name__, exc,
        )
        return None
    return {"token_ids": token_ids, "logprobs": logprobs}


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


# Content of the placeholder user turn inserted by _ensure_user_query: cheap
# (~2 tokens) and inert. Change here if it turns out to influence the model.
_PLACEHOLDER_USER_CONTENT = "."


def _ensure_user_query(messages: list[BaseMessage]) -> list[BaseMessage]:
    """Insert a placeholder user turn into a history with no user message.

    Qwen chat templates refuse to render such histories ("No user query
    found in messages."), which arise legitimately when summarization
    absorbs the last user message into the system prompt. The placeholder
    goes after the leading system messages (Qwen requires system first; a
    trailing user turn reads as a fresh instruction, see
    ``_fix_trailing_assistant``). Warns on every insertion.
    """
    # Ceiling: the template also discounts user turns that are entirely a
    # <tool_response> wrapper; MadAgents never produces those.
    if any(isinstance(m, HumanMessage) for m in messages):
        return messages
    idx = 0
    while idx < len(messages) and isinstance(messages[idx], SystemMessage):
        idx += 1
    logger.warning(
        "vllm_runtime: no user query in a %d-message list; inserting a "
        "placeholder user message at index %d so the chat template renders.",
        len(messages), idx,
    )
    return [
        *messages[:idx],
        HumanMessage(content=_PLACEHOLDER_USER_CONTENT),
        *messages[idx:],
    ]


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
        sampling = _get_sampling_defaults(_resolve_base_model_name(vllm_model, vllm_url))

        _reject_unsupported_caller_max_tokens(max_tokens)

        # Seed reproducibility for per-trial replay, via the native ChatOpenAI
        # Pydantic ``seed`` field: it lives on the inner Pydantic instance and
        # survives all .bind() calls, independent of extra_body merging.
        seed: int | None = None
        seed_env = os.environ.get("MADAGENTS_VLLM_SEED")
        if seed_env:
            try:
                seed = int(seed_env)
            except ValueError:
                logger.warning("MADAGENTS_VLLM_SEED=%r is not an int; ignoring", seed_env)

        kwargs: dict[str, Any] = dict(
            model=vllm_model,
            base_url=vllm_url,
            api_key=os.environ.get("VLLM_API_KEY", "dummy"),
            use_responses_api=False,
            temperature=sampling["temperature"],
            top_p=sampling["top_p"],
            extra_body={"top_k": sampling["top_k"], "min_p": sampling["min_p"]},
        )
        if seed is not None:
            kwargs["seed"] = seed
        # No static max_tokens on ChatOpenAI: ``invoke()`` binds a dynamic
        # value from the exact prompt size per call.
        return ChatOpenAI(**kwargs)

    def build_preamble(self, *, prompt: str) -> list[BaseMessage]:
        return [SystemMessage(content=prompt)]

    def prepare_tools(self, tools: list) -> tuple[list, list]:
        llm_tools: list = []
        node_tools: list = []
        for tool in tools:
            if isinstance(tool, dict):
                if tool.get("type") == "web_search":
                    # Provider-native web search has no vLLM equivalent;
                    # substitute the locally-executed SearXNG-backed tool.
                    llm_tools.append(local_web_search_tool)
                    node_tools.append(local_web_search_tool)
                continue  # Strip other provider-specific dict tools
            if getattr(tool, "name", None) == "read_pdf":
                # The default read_pdf variants return base64 content blocks
                # that vLLM rejects; substitute the local markdown converter.
                llm_tools.append(local_read_pdf_tool)
                node_tools.append(local_read_pdf_tool)
                continue
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
        family = _thinking_family(
            _resolve_base_model_name(_get_model_name(llm), _resolve_vllm_url()),
        )
        if not effort or family is None:
            return llm  # No applicable thinking control — use model default.
        # The merge keeps sampling params and the preserve_thinking kwarg
        # bound by bind_reasoning_trace (applied first at every call site).
        return _bind_extra_body(llm, _THINKING_CONTROL[family][effort])

    def bind_reasoning_trace(self, llm: Any) -> Any:
        """Bind ``preserve_thinking`` so historical think blocks render.

        Encrypted reasoning traces are OpenAI-specific, so none are requested
        here; but this is the one binding hook every agent's tool-bound LLM
        passes through (the planner never calls ``bind_reasoning``), so the
        template kwarg is injected here, without probing the server.
        Templates that lack the flag (Qwen3.5) ignore it.
        """
        ctk = _default_template_kwargs()
        if not ctk:
            return llm
        return _bind_extra_body(llm, {"chat_template_kwargs": ctk})

    def count_tokens(
        self,
        messages: list[BaseMessage],
        *,
        tools: list | None = None,
        chat_template_kwargs: dict | None = None,
    ) -> int | None:
        """Exact prompt-token count for ``messages`` via vLLM's ``/tokenize``.

        ``chat_template_kwargs=None`` counts with the kwargs every agent
        request carries by default, so gate counts match production renders
        (a bare render would under-count replayed reasoning on Qwen3.6);
        pass ``{}`` explicitly to count a bare render.

        Returns ``None`` when no exact count is available (``VLLM_TOKENIZE=0``,
        or a template-rejection HTTP 400) and callers fall back to their
        heuristic. Any other failure raises: a broken tokenizer or a
        misconfigured endpoint must surface.
        """
        if not vllm_tokens.tokenize_enabled():
            return None
        if chat_template_kwargs is None:
            chat_template_kwargs = _default_template_kwargs()
        messages = _ensure_user_query(messages)
        try:
            return vllm_tokens.count_prompt_tokens(
                messages, tools=tools, chat_template_kwargs=chat_template_kwargs,
            )
        except vllm_tokens.TokenizeHTTPError as e:
            if e.status != 400:
                raise
            logger.warning(
                "vllm_runtime: /tokenize rejected the count request (%s); "
                "returning None so the caller falls back to its heuristic.",
                e,
            )
            return None

    def invoke(
        self,
        llm: Any,
        messages: list[BaseMessage],
        *,
        # Unused here — base-class API parity with ``LLMRuntime.invoke``;
        # ``OpenAIRuntime`` etc. consume this kwarg. The vLLM path expresses
        # reasoning effort through ``bind_reasoning`` (which sets
        # ``chat_template_kwargs.enable_thinking``); the recorder reads the
        # wire-faithful indicator from there.
        reasoning_effort: str | None = None,
        agent_name: str | None = None,
    ) -> Any:
        messages = _consolidate_system_messages(list(messages))
        messages = _fix_trailing_assistant(messages)
        messages = _ensure_user_query(messages)
        if vllm_tokens.tokenize_enabled():
            try:
                plan = vllm_tokens.prepare_invocation(
                    llm, messages, agent_name=agent_name,
                )
            except vllm_tokens.TokenizeHTTPError as e:
                if e.status != 400:
                    raise
                logger.warning(
                    "vllm_runtime: /tokenize rejected the prompt for agent=%s "
                    "(%s); using a static output ceiling for this call. If "
                    "the chat template itself rejects the prompt, generation "
                    "will fail the same way.",
                    agent_name, e,
                )
                plan = vllm_tokens.prepare_invocation_static(
                    llm, agent_name=agent_name,
                )
        else:
            plan = vllm_tokens.prepare_invocation_static(llm, agent_name=agent_name)
        dynamic_max = plan["dynamic_max_tokens"]
        # Caller's ``.bind(max_tokens=N)`` takes precedence, in either
        # direction.  Tighter is safe and silent.  Looser is honoured with a
        # WARNING: it may exceed what the server accepts.
        caller_max = _get_existing_bound_max_tokens(llm)
        if caller_max is not None and caller_max != dynamic_max:
            if caller_max > dynamic_max:
                if plan["prompt_tokens_vllm"] is not None:
                    logger.warning(
                        "vllm_runtime: caller-bound max_tokens=%d exceeds the "
                        "dynamic cap %d for agent=%s. Honouring it; vLLM will "
                        "reject the request if prompt_tokens + max_tokens > "
                        "MAX_MODEL_LEN.",
                        caller_max, dynamic_max, agent_name,
                    )
                else:
                    logger.warning(
                        "vllm_runtime: caller-bound max_tokens=%d exceeds the "
                        "static cap %d for agent=%s. Honouring it; the server "
                        "may reject the request (context overflow, or a "
                        "gateway's balance pre-authorization).",
                        caller_max, dynamic_max, agent_name,
                    )
            dynamic_max = caller_max
        bound = llm.bind(max_tokens=dynamic_max)
        # Only while capturing: the logprobs stream is the sole source of the
        # tokens the model actually sampled, which importance-sampling
        # corrections and render-fidelity checks need. It costs roughly one
        # extra token's worth of record per generated token, so it is on by
        # default and MADAGENTS_CAPTURE_LOGPROBS=0 opts out where that
        # compounds (per-call SFT collection over many trials). Skipped
        # without /tokenize (VLLM_TOKENIZE=0): a server without vLLM's admin
        # endpoints is not expected to honour the vLLM-specific token-id
        # extension either.
        if (vllm_tokens.tokenize_enabled()
                and os.environ.get("_MADAGENTS_ENABLE_TRACE")
                and os.environ.get("MADAGENTS_CAPTURE_LOGPROBS", "1") != "0"):
            bound = _bind_extra_body(bound, {"return_tokens_as_token_ids": True})
            bound = bound.bind(logprobs=True)

        t0 = time.monotonic()
        result = bound.invoke(messages)
        duration_ms = int((time.monotonic() - t0) * 1000)

        # Runtime-invariant sanity check: the response's reported input_tokens
        # must equal the prompt_tokens vLLM gave us via /tokenize. A mismatch
        # means /tokenize and /chat/completions diverged, which would silently
        # break training/inference parity. Log + latch on the record; never
        # raise (the call already succeeded).
        latched_error: str | None = None
        usage = getattr(result, "usage_metadata", None) or {}
        response_input_tokens = (
            usage.get("input_tokens") if isinstance(usage, dict) else None
        )
        if (
            plan["prompt_tokens_vllm"] is not None
            and response_input_tokens is not None
            and response_input_tokens != plan["prompt_tokens_vllm"]
        ):
            latched_error = (
                f"prompt_tokens_vllm={plan['prompt_tokens_vllm']} != "
                f"usage_metadata.input_tokens={response_input_tokens}"
            )
            logger.warning(
                "trace_recorder: token-count mismatch trial_id=%s agent=%s "
                "prompt_tokens_vllm=%s input_tokens=%s",
                os.environ.get("MADAGENTS_TRIAL_ID"), agent_name,
                plan["prompt_tokens_vllm"], response_input_tokens,
            )

        # _MADAGENTS_ENABLE_TRACE is set by the benchmark runner; users opt
        # in via the --capture-traces CLI flag.
        if os.environ.get("_MADAGENTS_ENABLE_TRACE"):
            sampling_params = _extract_sampling_params(llm)
            trace_recorder.get_recorder().record(
                agent_name=agent_name,
                input_messages=messages,
                tools=plan["tools"],
                chat_template_kwargs=plan["chat_template_kwargs"],
                prompt_tokens_vllm=plan["prompt_tokens_vllm"],
                output_message=result,
                usage_metadata=usage if isinstance(usage, dict) else None,
                response_metadata=getattr(result, "response_metadata", None),
                sampling_params=sampling_params,
                sampled_tokens=_extract_sampled_tokens(result),
                # Same opt-out as the logprobs: these are the larger
                # contributor, since each call stores its whole prompt.
                prompt_token_ids=(
                    plan["prompt_token_ids"]
                    if os.environ.get("MADAGENTS_CAPTURE_LOGPROBS", "1") != "0"
                    else None),
                dynamic_max_tokens=dynamic_max,
                duration_ms=duration_ms,
                latched_error=latched_error,
            )
        return result

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
