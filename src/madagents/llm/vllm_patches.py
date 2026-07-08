"""Monkey-patches for ``langchain_openai``'s chat-completions converters.

vLLM's OpenAI-compatible responses carry fields that langchain-openai 1.1.6
drops or mishandles. One wrapper per conversion direction:

- Inbound (``_convert_dict_to_message``): capture the reasoning parser's
  ``reasoning_content`` and coerce malformed tool calls into valid-shaped
  ones so graphs route them and replay stays parseable.
- Outbound (``_convert_message_to_dict``): replay captured reasoning on
  historical assistant turns when the served template preserves thinking.

Both patches only fire on the chat-completions path used by ``VLLMRuntime``;
the Responses API path (``api="responses"``, used by ``OpenAILLMRuntime``)
passes through untouched. Pinned for ``langchain-openai==1.1.6`` via the
assert below.
"""

from __future__ import annotations

import logging
import uuid
from importlib.metadata import version as _pkg_version

from madagents.llm import vllm_tokens

logger = logging.getLogger(__name__)

_EXPECTED_LANGCHAIN_OPENAI = "1.1.6"
assert _pkg_version("langchain-openai") == _EXPECTED_LANGCHAIN_OPENAI, (
    f"vllm_patches pins langchain-openai=={_EXPECTED_LANGCHAIN_OPENAI}; "
    f"found {_pkg_version('langchain-openai')}. Re-check the upstream "
    f"conversion paths in langchain_openai.chat_models.base before bumping."
)

_INBOUND_PATCH_FLAG = "_madagents_inbound_patch"
_OUTBOUND_PATCH_FLAG = "_madagents_outbound_patch"


def install_inbound_patch() -> None:
    """Install the ``_convert_dict_to_message`` wrapper. Idempotent.

    Captures the reasoning parser's chain-of-thought (dropped by the stock
    converter) into ``additional_kwargs["reasoning_content"]``, and
    neutralizes malformed tool calls, which land in ``invalid_tool_calls``
    where graphs and the recorder never see them and whose raw arguments
    400 every replay: named ones become empty-arguments ``tool_calls``
    entries (tool validation then reports the failure to the model),
    nameless ones are dropped, and every original is stashed verbatim in
    ``additional_kwargs["malformed_tool_calls"]``.
    """
    from langchain_core.messages import AIMessage
    from langchain_openai.chat_models import base as lc_base

    if getattr(lc_base._convert_dict_to_message, _INBOUND_PATCH_FLAG, False):
        return

    original = lc_base._convert_dict_to_message

    def patched(_dict):
        msg = original(_dict)
        if not isinstance(msg, AIMessage):
            return msg
        rc = _dict.get("reasoning_content") or _dict.get("reasoning")
        # Only a non-empty string, and never overwrite a value the underlying
        # converter may have already placed there.
        if isinstance(rc, str) and rc:
            msg.additional_kwargs.setdefault("reasoning_content", rc)
        if msg.invalid_tool_calls:
            for itc in msg.invalid_tool_calls:
                name = itc.get("name")
                msg.additional_kwargs.setdefault(
                    "malformed_tool_calls", []
                ).append(dict(itc))
                if name:
                    logger.warning(
                        "Coercing malformed tool call %r (arguments %.200r) "
                        "into an empty-arguments call so the tool node can "
                        "report the failure to the model.", name, itc.get("args"),
                    )
                    msg.tool_calls.append({
                        "name": name,
                        "args": {},
                        "id": itc.get("id") or str(uuid.uuid4()),
                        "type": "tool_call",
                    })
                else:
                    logger.warning(
                        "Dropping nameless malformed tool call (arguments "
                        "%.200r); it is unexecutable and unreplayable.",
                        itc.get("args"),
                    )
            msg.invalid_tool_calls = []
        return msg

    setattr(patched, _INBOUND_PATCH_FLAG, True)
    lc_base._convert_dict_to_message = patched
    logger.debug("Installed inbound converter patch on langchain_openai")


def install_outbound_patch() -> None:
    """Install the ``_convert_message_to_dict`` wrapper. Idempotent.

    Replays stored ``reasoning_content`` on assistant messages under the
    ``reasoning`` key (the only one vLLM 0.21 forwards to the template),
    gated at call time on ``preserve_thinking_enabled()``; capability off
    stays byte-identical to the stock converter. The wire request, the
    ``/tokenize`` body, and the recorder's ``input_messages`` all use this
    converter, so they stay consistent by construction.
    """
    from langchain_core.messages import AIMessage
    from langchain_openai.chat_models import base as lc_base

    if getattr(lc_base._convert_message_to_dict, _OUTBOUND_PATCH_FLAG, False):
        return

    original = lc_base._convert_message_to_dict

    def patched(message, **kwargs):
        d = original(message, **kwargs)
        api = kwargs.get("api", "chat/completions")
        if api != "chat/completions" or not isinstance(message, AIMessage):
            return d
        rc = (message.additional_kwargs or {}).get("reasoning_content")
        # Check the capability last: it may probe the vLLM server on first
        # use, and only messages that actually carry reasoning (i.e.
        # vLLM-originated ones) should ever trigger that.
        if isinstance(rc, str) and rc and vllm_tokens.preserve_thinking_enabled():
            d.setdefault("reasoning", rc)
        return d

    setattr(patched, _OUTBOUND_PATCH_FLAG, True)
    lc_base._convert_message_to_dict = patched
    logger.debug("Installed outbound converter patch on langchain_openai")


install_inbound_patch()
install_outbound_patch()
