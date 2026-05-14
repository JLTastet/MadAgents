"""TraceRecorder — append-only JSONL capture for ``VLLMRuntime.invoke()`` calls.

One record per invocation. Each record carries the post-transform
``input_messages`` (OpenAI dict shape, what vLLM saw on the wire), the bound
``tools`` and ``chat_template_kwargs``, the prompt-token count vLLM reported,
the assistant ``output_message`` (with flat ``reasoning_content``), and
per-call metadata (sampling params, duration, latched_error). Together they
let training-time code rebuild the exact training example via
``tokenizer.apply_chat_template(messages, tools=tools, ...)``.

The recorder is a module-level singleton constructed lazily via
``get_recorder()``. ``MADAGENTS_TRIAL_ID`` is re-read on every ``record()``
call so a recorder reused across trials stays correct.
"""
from __future__ import annotations

import atexit
import copy
import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any

from langchain_core.messages import AIMessage, BaseMessage
from langchain_openai.chat_models.base import _convert_message_to_dict

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
DEFAULT_LOG_PATH = "/diagnostics/traces.jsonl"
DROP_STUB_NAME = "trace_recorder_dropped.json"

# agent_name -> agent_role. Must cover every entry in
# madagents.config.WORKER_AGENTS / REVIEWER_AGENTS plus the singletons
# (orchestrator / planner / plan_updater / summarizer). A unit test asserts
# coverage so drift in MadAgents agent registration gets caught.
AGENT_ROLE: dict[str, str] = {
    "orchestrator": "orchestrator",
    "planner": "planner",
    "plan_updater": "planner",
    "summarizer": "summarizer",
    "plan_reviewer": "reviewer",
    "verification_reviewer": "reviewer",
    "presentation_reviewer": "reviewer",
    "script_operator": "specialist_worker",
    "researcher": "specialist_worker",
    "pdf_reader": "specialist_worker",
    "madgraph_operator": "specialist_worker",
    "plotter": "specialist_worker",
    "physics_expert": "specialist_worker",
    "user_cli_operator": "specialist_worker",
}


def _now_iso_ms() -> str:
    """ISO-8601 UTC timestamp with millisecond precision (e.g. 2026-05-02T14:32:11.457+00:00)."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _output_message_to_dict(msg: AIMessage) -> dict[str, Any]:
    """Extract a flat OpenAI-style assistant message + flat ``reasoning_content``.

    We do **not** round-trip through ``_convert_message_to_dict`` because that
    function drops ``additional_kwargs["reasoning_content"]`` on outbound (the
    LangChain behaviour the parity argument depends on). Instead we read
    directly from the AIMessage attributes.

    Example::

        AIMessage(
            content="hello",
            additional_kwargs={"reasoning_content": "<think>plan</think>"},
        )
        ->
        {
            "role": "assistant",
            "content": "hello",
            "reasoning_content": "<think>plan</think>",
        }

    With tool calls, ``tool_calls`` is appended to the dict in LangChain's
    native ``[{id, name, args, type}, ...]`` shape; ``reasoning_content`` is
    omitted when absent or empty.
    """
    out: dict[str, Any] = {"role": "assistant"}
    content = getattr(msg, "content", None)
    out["content"] = content if content is not None else ""

    tool_calls = getattr(msg, "tool_calls", None) or []
    if tool_calls:
        # Keep LangChain's ``[{id, name, args, type}, ...]`` shape — downstream
        # readers can convert to OpenAI's nested function-tool-call form if
        # needed; the recorder preserves the native shape so tool_call_id
        # round-trips losslessly.
        out["tool_calls"] = [dict(tc) for tc in tool_calls]

    additional = getattr(msg, "additional_kwargs", None) or {}
    rc = additional.get("reasoning_content")
    if isinstance(rc, str) and rc:
        out["reasoning_content"] = rc
    return out


class TraceRecorder:
    """Append-only JSONL writer. Lazy file open, never raises into the runtime."""

    def __init__(
        self,
        path: str | None = None,
        trial_id: str | None = None,
        meta_ref: str = "meta.json",
        model: str = "",
        tokenizer_revision: str = "",
    ) -> None:
        # path is resolved at construction; trial_id is re-resolved on every
        # record() call so a recorder reused across trials stays correct.
        self._path = Path(path or os.environ.get("MADAGENTS_TRACE_JSONL")
                          or DEFAULT_LOG_PATH)
        self._trial_id_explicit = trial_id  # if non-None, takes precedence over env
        self._meta_ref = meta_ref
        self._model = model
        self._tokenizer_revision = tokenizer_revision
        self._turn_index = 0
        self._dropped = 0  # internal counter for write-path failures
        self._lock = threading.Lock()
        self._fh: IO[str] | None = None  # lazy file handle
        self._stub_initialized = False  # eager stub written on first record()
        # Warn-once guard so a misconfigured run that re-resolves trial_id
        # every record() doesn't spam the log.
        self._warned_unset_trial_id = False

    def _resolve_trial_id(self) -> str:
        """Re-read ``MADAGENTS_TRIAL_ID`` every call.

        Cheap (an env-var read), and keeps the recorder correct if a single
        MadAgents process is reused across multiple trials with different
        trial IDs. Logs the "unset" warning at most once via
        ``_warned_unset_trial_id`` so the log isn't spammed.
        """
        if self._trial_id_explicit:
            return self._trial_id_explicit
        tid = os.environ.get("MADAGENTS_TRIAL_ID") or ""
        if not tid and not self._warned_unset_trial_id:
            self._warned_unset_trial_id = True
            logger.warning(
                "TraceRecorder: MADAGENTS_TRIAL_ID is unset on first record(); "
                "records will carry trial_id=''. Check env-var threading from "
                "the benchmark runner. (Warning logged once per recorder.)"
            )
        return tid

    def _ensure_open(self) -> None:
        if self._fh is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self._path, "a", encoding="utf-8")

    # ------------------------------------------------------------------
    # Drop-stub invariant (matters for SIGTERM safety):
    #   * Stub (DROP_STUB_NAME) is written eagerly on the first successful
    #     record() with ``dropped: 0``, then re-written on every drop and
    #     on close().
    #   * Stub absent + traces.jsonl present  → recorder never started writing.
    #   * Stub present with ``dropped: 0``    → clean run.
    #   * Stub present with ``dropped > 0``   → records lost.
    # If the parent directory is itself broken, both _ensure_open AND
    # _write_stub_unsafe fail; the stub is then absent and indistinguishable
    # from "recorder never started" without independently observing
    # traces.jsonl. _write_stub_unsafe logs the consequence at ERROR level
    # so the failure mode is greppable from the run log.
    # ------------------------------------------------------------------

    def _write_stub_unsafe(self, trial_id: str) -> None:
        """Write the dropped-records stub. Caller must hold ``self._lock``.

        Failure here is logged at ERROR level but never raised — the stub
        is observability, not load-bearing for the call's success path.
        """
        stub_path = self._path.parent / DROP_STUB_NAME
        try:
            stub_path.write_text(json.dumps({
                "trial_id": trial_id,
                "dropped": self._dropped,
                "wrote": self._turn_index,
            }))
        except Exception:  # noqa: BLE001
            logger.exception(
                "TraceRecorder: failed to write dropped-records stub at %s. "
                "Dropped records in this trial will not appear in "
                "meta.json's errors block; verify traces.jsonl is complete "
                "for trial_id=%s before trusting the run summary.",
                stub_path, trial_id,
            )

    def close(self) -> None:
        """Close the file handle; finalise the dropped-records stub."""
        with self._lock:
            if self._fh is not None:
                try:
                    self._fh.close()
                except Exception:  # noqa: BLE001
                    pass
                self._fh = None
            if self._dropped:
                logger.warning(
                    "TraceRecorder: dropped %d record(s) due to write-path "
                    "failures; trial_id=%s wrote=%d dropped=%d",
                    self._dropped, self._resolve_trial_id() or "?",
                    self._turn_index, self._dropped,
                )
            # Always write the final stub if any records were attempted, so
            # the runner can disambiguate "clean run" from "recorder never
            # started" / "SIGTERM mid-run". This is a no-op on a fresh
            # recorder that never recorded anything.
            if self._stub_initialized:
                self._write_stub_unsafe(self._resolve_trial_id())

    def record(
        self,
        *,
        agent_name: str | None,
        input_messages: list[BaseMessage],
        tools: list[dict] | None,
        chat_template_kwargs: dict[str, Any],
        prompt_tokens_vllm: int,
        output_message: AIMessage,
        usage_metadata: dict | None,
        response_metadata: dict | None,
        sampling_params: dict[str, Any],
        dynamic_max_tokens: int,
        duration_ms: int,
        latched_error: str | None,
    ) -> None:
        """Record one VLLMRuntime.invoke call.

        ``reasoning_effort`` is intentionally not a parameter: the wire-faithful
        signal for whether thinking was on lives in
        ``chat_template_kwargs.enable_thinking`` (which is extracted from the
        actual binding by ``vllm_tokens._extract_chat_template_kwargs``). A
        caller-passed ``reasoning_effort`` kwarg can disagree with the binding,
        so we don't record it.
        """
        try:
            self._record_unsafe(
                agent_name=agent_name,
                input_messages=input_messages,
                tools=tools,
                chat_template_kwargs=chat_template_kwargs,
                prompt_tokens_vllm=prompt_tokens_vllm,
                output_message=output_message,
                usage_metadata=usage_metadata,
                response_metadata=response_metadata,
                sampling_params=sampling_params,
                dynamic_max_tokens=dynamic_max_tokens,
                duration_ms=duration_ms,
                latched_error=latched_error,
            )
        except Exception as exc:  # noqa: BLE001 — recorder must never raise into the runtime
            with self._lock:
                self._dropped += 1
                tid = self._resolve_trial_id()
                turn_index_at_failure = self._turn_index  # snapshot inside lock
                # Persist the updated drop count immediately so SIGTERM can't
                # silently lose it.
                self._write_stub_unsafe(tid)
                # Log inside the lock so a concurrent record() can't increment
                # _turn_index between the snapshot and the log call.
                logger.exception(
                    "TraceRecorder.record swallowed exception: trial_id=%s "
                    "agent_name=%s turn_index~%d exc=%r",
                    tid, agent_name, turn_index_at_failure, exc,
                )

    def _record_unsafe(
        self,
        *,
        agent_name: str | None,
        input_messages: list[BaseMessage],
        tools: list[dict] | None,
        chat_template_kwargs: dict[str, Any],
        prompt_tokens_vllm: int,
        output_message: AIMessage,
        usage_metadata: dict | None,
        response_metadata: dict | None,
        sampling_params: dict[str, Any],
        dynamic_max_tokens: int,
        duration_ms: int,
        latched_error: str | None,
    ) -> None:
        agent_role = AGENT_ROLE.get(agent_name or "", "unknown")
        if agent_role == "unknown":
            logger.warning(
                "TraceRecorder: unknown agent_name=%r; recording with "
                "agent_role='unknown'. If this agent should be tracked, add it "
                "to AGENT_ROLE in trace_recorder.py.",
                agent_name,
            )

        # OpenAI-shape input messages — same converter vllm_tokens uses for
        # the /tokenize body, so what the recorder writes matches what the
        # audit script (validate_trace_retokenize.py) re-POSTs.
        input_dicts = [_convert_message_to_dict(m) for m in input_messages]

        # tools are deep-copied so mutations to the live binding's tool dicts
        # (e.g. prompt-engineering experiments that patch a description) don't
        # retroactively rewrite captured records.
        tools_snapshot = copy.deepcopy(tools) if tools else None

        record: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "trial_id": self._resolve_trial_id(),
            # turn_index assigned under lock below so concurrent record()
            # calls don't collide. (MadAgents is single-threaded per agent
            # invocation but the orchestrator may dispatch in parallel; the
            # lock protects against that and keeps file writes ordered.)
            "turn_index": -1,
            "timestamp": _now_iso_ms(),
            "agent_name": agent_name,
            "agent_role": agent_role,
            "model": self._model,
            "tokenizer_revision": self._tokenizer_revision,
            "chat_template_kwargs": dict(chat_template_kwargs or {}),
            "input_messages": input_dicts,
            "tools": tools_snapshot,
            "output_message": _output_message_to_dict(output_message),
            "prompt_tokens_vllm": int(prompt_tokens_vllm),
            "usage_metadata": dict(usage_metadata) if isinstance(usage_metadata, dict) else None,
            "response_metadata": dict(response_metadata) if isinstance(response_metadata, dict) else None,
            "sampling_params": dict(sampling_params or {}),
            "dynamic_max_tokens": int(dynamic_max_tokens),
            "duration_ms": int(duration_ms),
            "latched_error": latched_error,
            "capture_meta_ref": self._meta_ref,
        }

        with self._lock:
            # Open + write FIRST, increment ONLY after success: if anything
            # before the increment raises, the next call retries with the
            # same turn_index (gap-free numbering). The triage path in
            # record() reads self._turn_index, which under this ordering
            # equals "the index the failed call would have used".
            #
            # Edge: a flush() failure can leave a partial line on disk and
            # the next call will then write the same turn_index again.
            # Detectable on disk by deduping (trial_id, turn_index) on the
            # affected trial; the trial is itself already flagged via the
            # dropped-records stub.
            self._ensure_open()
            assert self._fh is not None  # _ensure_open guarantees this
            record["turn_index"] = self._turn_index
            self._fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._fh.flush()
            self._turn_index += 1
            # Eager stub write on the first successful record(): from this
            # point on, "stub absent" means "recorder never started".
            if not self._stub_initialized:
                self._stub_initialized = True
                self._write_stub_unsafe(record["trial_id"])


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_recorder: TraceRecorder | None = None
_recorder_lock = threading.Lock()


def get_recorder() -> TraceRecorder:
    """Return the process-wide TraceRecorder, constructing on first access.

    ``close()`` is registered with ``atexit`` so the dropped-records stub
    gets finalised on normal interpreter shutdown. SIGTERM / hard-kill paths
    skip atexit, but the eager-stub-on-first-record() invariant guarantees
    the stub exists on disk with up-to-date drop counts even in that case.
    """
    global _recorder
    if _recorder is None:
        with _recorder_lock:
            if _recorder is None:
                _recorder = TraceRecorder(
                    model=os.environ.get("VLLM_MODEL", ""),
                    tokenizer_revision=os.environ.get("MADAGENTS_TOKENIZER_REVISION", ""),
                )
                atexit.register(_recorder.close)
    return _recorder


def _reset_recorder_for_tests() -> None:
    """Reset the module-level singleton. Test-only — never call from production code."""
    global _recorder
    with _recorder_lock:
        if _recorder is not None:
            try:
                _recorder.close()
            except Exception:  # noqa: BLE001
                pass
        _recorder = None
