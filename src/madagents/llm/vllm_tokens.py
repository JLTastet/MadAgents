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

# Reserved output budget for the summarizer when it fires. The trigger threshold
# in ``config._apply_vllm_summarizer_defaults`` is ``MAX_MODEL_LEN -
# VLLM_MAX_SUMMARIZER_OUTPUT``, so when the conversation reaches the trigger
# there is this much room left in the context window for the summarizer to write
# its summary. It does not, by itself, prevent a single oversized tool result
# from overflowing the window when the summarizer cannot shrink the prompt; that
# preserved-tail case is caught by the dynamic-max backstop in
# ``compute_dynamic_max_tokens``.
VLLM_MAX_SUMMARIZER_OUTPUT: int = int(os.environ.get("VLLM_MAX_SUMMARIZER_OUTPUT", "3072"))

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


def _check_summarizer_output_within_window() -> None:
    """The reserve must be a positive fraction of the context window. Otherwise
    the derived threshold ``MAX_MODEL_LEN - VLLM_MAX_SUMMARIZER_OUTPUT`` is <= 0
    (the gate fires every turn) or >= MAX_MODEL_LEN (the gate never fires). This
    guards a misconfigured ``VLLM_MAX_SUMMARIZER_OUTPUT`` env override.
    """
    if not 0 < VLLM_MAX_SUMMARIZER_OUTPUT < MAX_MODEL_LEN:
        raise RuntimeError(
            f"vllm_tokens misconfigured: VLLM_MAX_SUMMARIZER_OUTPUT "
            f"({VLLM_MAX_SUMMARIZER_OUTPUT}) must be in the open interval "
            f"(0, MAX_MODEL_LEN={MAX_MODEL_LEN})."
        )


_check_min_output_below_summarizer_output()
_check_agent_output_ceilings()
_check_summarizer_output_within_window()


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


def _post_tokenize(body: dict[str, Any], *, timeout: float = 60.0) -> list[int]:
    """POST ``body`` to vLLM's ``/tokenize`` endpoint and return the token ids.

    The ids, not just the count: they are the server's own tokenization of the
    prompt, which is what training must reproduce, and the endpoint returns
    them anyway.

    Raises ``RuntimeError`` with the HTTP status and response body on any
    failure, so the caller sees a self-contained error rather than a bare
    ``URLError``.

    Opens a fresh socket per call, measured at ~3-15 ms on a loopback path,
    well below the inference latency it guards. Memoising buys nothing: each
    invocation carries a different conversation. If it ever matters, the next
    step is HTTP keep-alive.
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
    except (OSError, ValueError) as e:
        # OSError covers URLError and mid-read socket timeouts; ValueError
        # covers a non-JSON response body.
        raise RuntimeError(
            f"vllm_tokens: POST {_tokenize_url()} failed: {e}"
        ) from e
    try:
        ids = [int(t) for t in out["tokens"]]
    except (KeyError, TypeError, ValueError) as e:
        raise RuntimeError(
            f"vllm_tokens: unexpected /tokenize response shape: {out!r}"
        ) from e
    assert len(ids) == int(out["count"]), (
        f"/tokenize: {len(ids)} ids for count {out['count']}"
    )
    return ids


# ---------------------------------------------------------------------------
# preserve_thinking capability
# ---------------------------------------------------------------------------

_PRESERVE_THINKING_ENV = "VLLM_PRESERVE_THINKING"

# A historical assistant turn carrying reasoning before a trailing user
# query: the default render drops the reasoning while preserve_thinking
# renders it, so the token-count differential is the capability signal.
_PRESERVE_THINKING_PROBE: list[dict[str, str]] = [
    {"role": "user", "content": "ping"},
    {"role": "assistant", "content": "pong",
     "reasoning": "The user pings; I should reply pong."},
    {"role": "user", "content": "ping again"},
]

_preserve_thinking_cache: bool | None = None


def preserve_thinking_enabled() -> bool:
    """Whether the served model's chat template honours ``preserve_thinking``.

    ``VLLM_PRESERVE_THINKING=1``/``0`` forces the verdict without probing;
    otherwise autodetect by tokenizing a fixed conversation with and without
    the kwarg. Cached once resolved; a probe failure raises RuntimeError
    (not cached, so the next call retries). Runs per request, never at
    startup: the sole production caller is the replay patch in
    ``vllm_patches``.
    """
    global _preserve_thinking_cache
    if _preserve_thinking_cache is not None:
        return _preserve_thinking_cache

    env = os.environ.get(_PRESERVE_THINKING_ENV, "").strip()
    if env and env not in ("0", "1"):
        raise RuntimeError(
            f"vllm_tokens: {_PRESERVE_THINKING_ENV}={env!r} is invalid; "
            f"use '1' or '0', or leave unset to autodetect."
        )
    if env:
        enabled = env == "1"
        logger.info(
            "vllm_tokens: preserve_thinking %s (forced via %s=%s)",
            "enabled" if enabled else "disabled", _PRESERVE_THINKING_ENV, env,
        )
    else:
        # Short timeout: fail the calling request quickly with a clear error.
        try:
            base = len(_post_tokenize({
                "messages": _PRESERVE_THINKING_PROBE,
                "add_generation_prompt": True,
            }, timeout=5.0))
            preserved = len(_post_tokenize({
                "messages": _PRESERVE_THINKING_PROBE,
                "add_generation_prompt": True,
                "chat_template_kwargs": {"preserve_thinking": True},
            }, timeout=5.0))
        except RuntimeError as exc:
            raise RuntimeError(
                f"preserve_thinking autodetect probe failed: {exc}. Ensure "
                f"the vLLM server is up, or set {_PRESERVE_THINKING_ENV}=1/0 "
                f"to skip the probe."
            ) from exc
        enabled = preserved != base
        logger.info(
            "vllm_tokens: preserve_thinking %s (autodetected via /tokenize "
            "probe: %d tokens without the kwarg vs %d with it)",
            "enabled" if enabled else "disabled", base, preserved,
        )
    _preserve_thinking_cache = enabled
    return enabled


def _reset_preserve_thinking_for_tests() -> None:
    """Clear the cached capability. Test-only — never call from production code."""
    global _preserve_thinking_cache
    _preserve_thinking_cache = None


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
    {"enable_thinking": ..., "preserve_thinking": ...}}``, which changes how
    vLLM renders the prompt. The /tokenize request body must carry the same
    kwargs or the count will diverge from what /chat/completions reports for
    the same input (e.g. Qwen's template emits an empty ``<think></think>``
    block when thinking is disabled, and renders historical ``<think>``
    blocks when ``preserve_thinking`` is on). Returning the whole dict keeps
    every bound key riding along without per-key plumbing.

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


def tokenize_prompt(
    messages: list[BaseMessage] | list[dict],
    tools: list[dict] | None = None,
    chat_template_kwargs: dict[str, Any] | None = None,
) -> list[int]:
    """Return vLLM's own token ids for the prompt these messages render to.

    The ids are the server's rendering, so training can assert that its local
    re-render reproduces the exact prompt the model conditioned on rather than
    only matching its length.
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


def count_prompt_tokens(
    messages: list[BaseMessage] | list[dict],
    tools: list[dict] | None = None,
    chat_template_kwargs: dict[str, Any] | None = None,
) -> int:
    """Exact prompt token count, for callers that need the size but not the ids."""
    return len(tokenize_prompt(messages, tools, chat_template_kwargs))


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
      * Log WARNING for non-summarizer agents when ``prompt_tokens`` reaches
        ``summarizer_token_threshold()``. This is expected only when summarization
        fired but could not shrink the prompt; without a coincident can't-shrink
        warning, the gate under-counted, which is a bug.

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

    # The summarizer never warns about itself (it is the remedy). For other
    # agents this fires only if the prompt is still over the trigger at invoke
    # time, which should mean summarization ran but couldn't shrink it.
    if agent_name != "summarizer" and prompt_tokens >= summarizer_trigger:
        logger.warning(
            "vllm_tokens: prompt=%d (agent=%s) is at or above the summarizer "
            "trigger %d at invoke time (dynamic max_tokens=%d). This is expected "
            "only when summarization fired but could not shrink the prompt (an "
            "oversized tool result in the preserved tail); look for a coincident "
            "summarizer can't-shrink warning. If there is none, the gate "
            "under-counted, which is a bug.",
            prompt_tokens, agent_name, summarizer_trigger, dynamic,
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
) -> dict[str, Any]:
    """Run all pre-call accounting for a vLLM invocation.

    Walks ``llm`` for any bound tools and ``chat_template_kwargs``, posts to
    ``/tokenize`` to get the exact prompt size, then resolves the per-agent
    output ceiling against the remaining context.

    Returns a dict with:
      * ``dynamic_max_tokens`` (int): per-call output ceiling for this prompt.
      * ``prompt_tokens_vllm`` (int): the exact prompt-token count vLLM reported.
      * ``prompt_token_ids`` (list[int]): vLLM's own ids for that prompt.
      * ``tools`` (list[dict] | None): tool schemas as bound on ``llm``.
      * ``chat_template_kwargs`` (dict): chat-template kwargs as bound on ``llm``.

    All values reflect what was actually sent to ``/tokenize``.
    """
    tools = _extract_bound_tools(llm)
    chat_template_kwargs = _extract_chat_template_kwargs(llm)
    prompt_token_ids = tokenize_prompt(
        messages, tools=tools, chat_template_kwargs=chat_template_kwargs,
    )
    prompt_tokens = len(prompt_token_ids)
    dynamic_max = compute_dynamic_max_tokens(prompt_tokens, agent_name=agent_name)
    return {
        "dynamic_max_tokens": dynamic_max,
        "prompt_tokens_vllm": prompt_tokens,
        "prompt_token_ids": prompt_token_ids,
        "tools": tools,
        "chat_template_kwargs": chat_template_kwargs,
    }
