"""Exact prompt-token counting and dynamic max_tokens cap for the vLLM runtime.

Problem this solves
-------------------
``VLLMRuntime`` needs to choose a ``max_tokens`` value for every call that
satisfies ``prompt_tokens + max_tokens <= MAX_MODEL_LEN`` (vLLM rejects
otherwise) while still leaving a useful output budget. A static cap breaks
once conversations grow past the reserved fraction of the context window.

Approach
--------
1. Count prompt tokens *exactly* by POSTing to vLLM's ``/tokenize`` endpoint.
   The server uses its own tokenizer, so the count is by construction the
   same one ``/chat/completions`` will report as ``usage.prompt_tokens``.
2. Compute ``max_tokens = min(agent_ceiling, remaining)`` where
   ``remaining = MAX_MODEL_LEN - prompt_tokens``. No safety margin:
   exactness is a hard guarantee.
3. Enforce ``VLLM_MIN_OUTPUT`` as a floor: if the budget falls below it,
   raise ``RuntimeError`` rather than silently truncate. This should never
   happen if the summarizer fires at the configured threshold.

The HTTP round-trip to ``/tokenize`` adds ~3-15 ms per invocation on a
loopback path, well below the inference latency of the call it guards.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_MODEL_LEN: int = int(os.environ.get("MAX_MODEL_LEN", "65536"))

# Optional override capping the summarizer trigger from above. Useful for
# models that degrade after a fixed prompt size regardless of their
# advertised context window (e.g. a 256K-context model that retrieves
# poorly past 130K). ``None`` means "no ceiling, use the context window".
VLLM_SUMMARIZER_THRESHOLD_CEILING: int | None = None

# Default per-call output ceiling (applied when an agent has no entry in
# VLLM_AGENT_OUTPUT_CEILINGS). Sized to leave comfortable headroom above
# observed typical outputs so reviewer/worker growth does not force a re-tune.
VLLM_DEFAULT_MAX_OUTPUT: int = 4096

# Floor below which we refuse to invoke — summarizer should have fired.
VLLM_MIN_OUTPUT: int = 1024

# Reserved output budget for the summarizer when it fires. The summarizer's
# trigger threshold in ``config._apply_vllm_summarizer_defaults`` is derived
# as ``MAX_MODEL_LEN - VLLM_MAX_SUMMARIZER_OUTPUT`` so the summary can always
# fit once the conversation reaches the trigger.
VLLM_MAX_SUMMARIZER_OUTPUT: int = 8_192

# Per-agent ceilings. Use ``None`` to let an agent consume all remaining
# context (e.g. summarizer, whose output can legitimately grow with input).
# Unknown names default to VLLM_DEFAULT_MAX_OUTPUT.
VLLM_AGENT_OUTPUT_CEILINGS: dict[str, int | None] = {
    "summarizer": None,
}

# Module-load invariants on the constants above. Wrapped in functions so
# they can be exercised from unit tests with monkey-patched constants.


def _check_min_output_below_summarizer_output() -> None:
    """The floor must leave room for the summarizer to actually run once the
    summarizer threshold is crossed.
    """
    if VLLM_MIN_OUTPUT > VLLM_MAX_SUMMARIZER_OUTPUT:
        raise RuntimeError(
            f"vllm_tokens misconfigured: VLLM_MIN_OUTPUT ({VLLM_MIN_OUTPUT}) "
            f"must be at most VLLM_MAX_SUMMARIZER_OUTPUT "
            f"({VLLM_MAX_SUMMARIZER_OUTPUT}). Otherwise the raise-on-exhaustion "
            f"branch in compute_dynamic_max_tokens can fire before the "
            f"summarizer has had a chance to run."
        )


def _check_agent_output_ceilings() -> None:
    """Every explicit per-agent ceiling must be at or above the floor, so a
    typo like ``{"foo": 500}`` can't silently bypass VLLM_MIN_OUTPUT.
    """
    for name, ceiling in VLLM_AGENT_OUTPUT_CEILINGS.items():
        if ceiling is not None and ceiling < VLLM_MIN_OUTPUT:
            raise RuntimeError(
                f"vllm_tokens misconfigured: VLLM_AGENT_OUTPUT_CEILINGS[{name!r}] "
                f"= {ceiling} is below VLLM_MIN_OUTPUT ({VLLM_MIN_OUTPUT}). "
                f"Per-agent ceilings must be None (unbounded) or >= the floor."
            )


_check_min_output_below_summarizer_output()
_check_agent_output_ceilings()


def summarizer_token_threshold() -> int:
    """Return the prompt-token count at which the summarizer should fire.

    Derived from the current ``MAX_MODEL_LEN`` so it scales with whatever
    context window vLLM was started with — no hard-coded constants tied to
    a specific model family. Can be capped from above via
    ``VLLM_SUMMARIZER_THRESHOLD_CEILING`` for models that degrade before
    their advertised context limit.
    """
    base = MAX_MODEL_LEN - VLLM_MAX_SUMMARIZER_OUTPUT
    if VLLM_SUMMARIZER_THRESHOLD_CEILING is not None:
        return min(base, VLLM_SUMMARIZER_THRESHOLD_CEILING)
    return base


# ---------------------------------------------------------------------------
# vLLM /tokenize plumbing
# ---------------------------------------------------------------------------


def _tokenize_url() -> str:
    """Return the absolute URL of vLLM's ``/tokenize`` endpoint.

    The endpoint lives at the server root, while ``VLLM_API_BASE`` is the
    OpenAI-compatible prefix (typically ending in ``/v1``). Strip the
    trailing ``/v1`` segment if present, then append ``/tokenize``.
    """
    base = os.environ.get("VLLM_API_BASE", "http://localhost:8200/v1").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base + "/tokenize"


def _post_tokenize(body: dict[str, Any], *, timeout: float = 60.0) -> int:
    """POST ``body`` to vLLM's ``/tokenize`` endpoint and return the token count.

    Uses ``urllib.request`` with a fresh socket per call — see the
    ``count_prompt_tokens`` perf note. Raises ``RuntimeError`` with the HTTP
    status / response body on any failure so the caller sees a self-contained
    error rather than a bare ``URLError``.
    """
    req = urllib.request.Request(
        _tokenize_url(),
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_excerpt = e.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(
            f"vllm_tokens: POST {_tokenize_url()} returned HTTP {e.code}: "
            f"{body_excerpt}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"vllm_tokens: POST {_tokenize_url()} failed: {e.reason}"
        ) from e
    try:
        return int(out["count"])
    except (KeyError, TypeError, ValueError) as e:
        raise RuntimeError(
            f"vllm_tokens: unexpected /tokenize response shape: {out!r}"
        ) from e


# ---------------------------------------------------------------------------
# Message / tool extraction
# ---------------------------------------------------------------------------


def _messages_to_openai_dicts(messages: list[BaseMessage]) -> list[dict]:
    """Convert LangChain BaseMessages to OpenAI chat-dict form.

    Uses ``langchain_openai``'s internal converter so the shape matches
    exactly what vLLM sees when the runtime invokes the model.
    """
    from langchain_openai.chat_models.base import _convert_message_to_dict

    return [_convert_message_to_dict(m) for m in messages]


def _extract_bound_tools(llm: Any) -> list[dict] | None:
    """Walk a RunnableBinding chain and return the tools schema list, if any.

    ``ChatOpenAI.bind_tools(...)`` stores the OpenAI-format tool dicts under
    ``llm.kwargs["tools"]``; subsequent ``.bind(...)`` calls merge into the
    same dict. Returns ``None`` if no tools are bound, or if the bound value
    is an empty list — both are treated identically by vLLM's chat template
    (empty ``tools=[]`` produces the same prompt as no tools at all, so
    skipping the kwarg in the request body matches what vLLM does).
    """
    cur: Any = llm
    while cur is not None:
        kwargs = getattr(cur, "kwargs", None)
        if isinstance(kwargs, dict) and "tools" in kwargs:
            return kwargs.get("tools") or None
        cur = getattr(cur, "bound", None)
    return None


def _extract_chat_template_kwargs(llm: Any) -> dict[str, Any]:
    """Return chat_template_kwargs from any ``extra_body`` binding on ``llm``.

    ``bind_reasoning`` injects ``extra_body={"chat_template_kwargs":
    {"enable_thinking": ...}}``, which changes how vLLM renders the prompt.
    The /tokenize request body must carry the same kwargs or the count will
    diverge from what /chat/completions reports for the same input (e.g.
    Qwen's template emits an empty ``<think></think>`` block when thinking
    is disabled, roughly +2 tokens).

    Walks outward-to-inward and returns the first match; does not merge
    nested bindings. This matches the actual bind semantics of our current
    call sites (only one layer ever sets ``chat_template_kwargs``, via
    ``bind_reasoning``) but would lose inner keys if a future caller stacked
    two bindings that each populate different ``chat_template_kwargs`` keys.
    """
    cur: Any = llm
    while cur is not None:
        kwargs = getattr(cur, "kwargs", None)
        if isinstance(kwargs, dict):
            extra = kwargs.get("extra_body") or {}
            ctk = extra.get("chat_template_kwargs")
            if isinstance(ctk, dict):
                return dict(ctk)
        cur = getattr(cur, "bound", None)
    return {}


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------


def count_prompt_tokens(
    messages: list[BaseMessage] | list[dict],
    tools: list[dict] | None = None,
    chat_template_kwargs: dict[str, Any] | None = None,
) -> int:
    """Return exact prompt token count for the given messages (+ optional tools).

    Accepts either LangChain ``BaseMessage`` instances or already-converted
    OpenAI dicts. The ``add_generation_prompt`` flag matches vLLM's behaviour
    for generation requests. ``chat_template_kwargs`` (e.g. ``enable_thinking``)
    must match whatever is sent to vLLM via ``extra_body`` or the count will
    diverge from what /chat/completions reports.

    Performance note: this opens a fresh HTTP socket per call. Measured
    ~3–15 ms on a loopback path, well below the inference latency it guards.
    Memoising the request body buys nothing — each invocation produces a
    different conversation, so the cache-hit rate is effectively zero. If
    profiling ever shows the per-call cost becoming a bottleneck, the next
    optimisation is HTTP keep-alive (``http.client.HTTPConnection`` with
    ``Connection: keep-alive``), which saves the ~1–2 ms TCP handshake on
    every call after the first.
    """
    if messages and isinstance(messages[0], BaseMessage):
        dicts = _messages_to_openai_dicts(messages)  # type: ignore[arg-type]
    else:
        dicts = list(messages)  # type: ignore[arg-type]
    body: dict[str, Any] = {
        "messages": dicts,
        "add_generation_prompt": True,
    }
    if tools:
        body["tools"] = tools
    if chat_template_kwargs:
        body["chat_template_kwargs"] = chat_template_kwargs
    return _post_tokenize(body)


# ---------------------------------------------------------------------------
# Dynamic cap
# ---------------------------------------------------------------------------


def compute_dynamic_max_tokens(
    prompt_tokens: int,
    *,
    agent_name: str | None = None,
) -> int:
    """Return ``max_tokens`` for a single vLLM invocation.

    Rules:
      * Never exceed ``MAX_MODEL_LEN - prompt_tokens`` (vLLM rejects otherwise).
      * Cap at ``VLLM_AGENT_OUTPUT_CEILINGS[agent_name]`` (or
        ``VLLM_DEFAULT_MAX_OUTPUT`` for unknown names); ``None`` means no ceiling.
      * Raise ``RuntimeError`` if the remaining budget falls below
        ``VLLM_MIN_OUTPUT`` — this is only reachable after the summarizer
        should already have fired (enforced by the module-load invariant
        ``VLLM_MIN_OUTPUT < VLLM_MAX_SUMMARIZER_OUTPUT``).
      * Log WARNING for non-summarizer agents when ``prompt_tokens`` has
        already crossed ``summarizer_token_threshold()`` — the summarizer
        should have fired before this call but didn't.

    Note: the caller-configured ``max_tokens`` (from ``create_chat_model``) is
    deliberately *not* consulted here. Every MadAgents caller hardcodes
    1 000 000, so the value never affects ``min()``; propagating it would be
    noise. Callers who want a genuine per-call cap should ``llm.bind(
    max_tokens=N)`` before invoking — the runtime's own bind merges at the
    kwarg level, so the smaller value wins.
    """
    if prompt_tokens < 0 or prompt_tokens > MAX_MODEL_LEN:
        raise RuntimeError(
            f"vllm_tokens: prompt_tokens={prompt_tokens} out of range "
            f"[0, MAX_MODEL_LEN={MAX_MODEL_LEN}]. This indicates a bug in "
            f"the counter or a stale session rehydrated against a smaller "
            f"context window."
        )
    remaining = MAX_MODEL_LEN - prompt_tokens
    summarizer_trigger = summarizer_token_threshold()

    if remaining < VLLM_MIN_OUTPUT:
        raise RuntimeError(
            f"vllm_tokens: context budget exhausted — prompt={prompt_tokens}, "
            f"remaining={remaining} < min={VLLM_MIN_OUTPUT}. The summarizer "
            f"should have fired at prompt_tokens >= {summarizer_trigger}; "
            f"check agents.summarizer.token_threshold and that the summarizer "
            f"is actually being invoked for agent={agent_name!r}."
        )

    ceiling = VLLM_AGENT_OUTPUT_CEILINGS.get(agent_name, VLLM_DEFAULT_MAX_OUTPUT)  # type: ignore[arg-type]
    dynamic = remaining if ceiling is None else min(remaining, ceiling)

    # The summarizer is itself the remedy for large prompts, so it never
    # warns about itself. For everyone else, warn only when the summarizer
    # should already have fired — i.e. prompt_tokens has crossed the trigger.
    if agent_name != "summarizer" and prompt_tokens >= summarizer_trigger:
        logger.warning(
            "vllm_tokens: prompt=%d has crossed summarizer trigger %d but "
            "agent=%s is still invoking without summarization (dynamic "
            "max_tokens=%d). Summarization should happen before the next call.",
            prompt_tokens, summarizer_trigger, agent_name, dynamic,
        )
    return dynamic


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def prepare_invocation(
    llm: Any,
    messages: list[BaseMessage],
    *,
    agent_name: str | None,
) -> int:
    """Run all pre-call accounting and return the dynamic ``max_tokens`` to bind.

    Walks ``llm`` for any bound tools and ``chat_template_kwargs``, posts to
    ``/tokenize`` to get the exact prompt size, then resolves the per-agent
    output ceiling against the remaining context. Caller is expected to do
    ``llm.bind(max_tokens=<return value>).invoke(messages)``.
    """
    tools = _extract_bound_tools(llm)
    chat_template_kwargs = _extract_chat_template_kwargs(llm)
    prompt_tokens = count_prompt_tokens(
        messages, tools=tools, chat_template_kwargs=chat_template_kwargs,
    )
    return compute_dynamic_max_tokens(prompt_tokens, agent_name=agent_name)
