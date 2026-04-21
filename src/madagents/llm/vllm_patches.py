"""Monkey-patches for ``langchain_openai`` so vLLM ``reasoning_content`` survives.

vLLM's reasoning parsers (``qwen3``, ``deepseek_r1``, ``hunyuan``, GPT-OSS
harmony, ...) return the model's chain-of-thought in the OpenAI-compatible
response under ``message.reasoning_content``. ``langchain_openai==1.1.6``
silently drops this field during the dict→``AIMessage`` conversion, so by
the time downstream code inspects the response it is gone.

This module wraps ``_convert_dict_to_message`` so that any non-empty
``reasoning_content`` (or fallback ``reasoning``) on the source dict is
copied into ``AIMessage.additional_kwargs["reasoning_content"]``.
Non-reasoning model responses are unaffected because the patch only adds a
key when the source dict actually contains the field.

Pinned for ``langchain-openai==1.1.6`` — enforced by the assert below.
"""

from __future__ import annotations

import logging
from importlib.metadata import version as _pkg_version

logger = logging.getLogger(__name__)

_EXPECTED_LANGCHAIN_OPENAI = "1.1.6"
assert _pkg_version("langchain-openai") == _EXPECTED_LANGCHAIN_OPENAI, (
    f"vllm_patches pins langchain-openai=={_EXPECTED_LANGCHAIN_OPENAI}; "
    f"found {_pkg_version('langchain-openai')}. Re-check the upstream "
    f"conversion path in langchain_openai.chat_models.base before bumping."
)

_PATCH_FLAG = "_madagents_reasoning_content_patch"


def install_reasoning_content_patch() -> None:
    """Install the ``_convert_dict_to_message`` wrapper. Idempotent."""
    from langchain_core.messages import AIMessage
    from langchain_openai.chat_models import base as lc_base

    if getattr(lc_base._convert_dict_to_message, _PATCH_FLAG, False):
        return

    original = lc_base._convert_dict_to_message

    def patched(_dict):
        msg = original(_dict)
        if isinstance(msg, AIMessage):
            rc = _dict.get("reasoning_content") or _dict.get("reasoning")
            # Only accept a non-empty string, and don't overwrite a value
            # the underlying converter (or some future langchain_openai
            # release) may have already placed there.
            if isinstance(rc, str) and rc:
                msg.additional_kwargs.setdefault("reasoning_content", rc)
        return msg

    setattr(patched, _PATCH_FLAG, True)
    lc_base._convert_dict_to_message = patched
    logger.debug("Installed reasoning_content patch on langchain_openai")


install_reasoning_content_patch()
