"""
Compatibility shims for the third-party dependency ecosystem.

Currently fixes:
    - RAGAS 0.4.3 hard-imports `langchain_community.chat_models.vertexai.ChatVertexAI`,
      a path removed in langchain-community 1.x. Since we don't use Vertex AI,
      we inject a no-op stub class so the import succeeds.

Imported by ml/__init__.py so the shim is in place before anything else loads.
"""

from __future__ import annotations

import sys
import types


def _install_vertexai_stub() -> None:
    """Inject a stub for the removed langchain_community.chat_models.vertexai module."""
    name = "langchain_community.chat_models.vertexai"
    if name in sys.modules:
        return
    try:
        from langchain_core.language_models import BaseChatModel
    except ImportError:
        # If langchain_core isn't even installed, there's nothing to shim
        return

    class ChatVertexAI(BaseChatModel):  # type: ignore[misc]
        """Stub - real ChatVertexAI is in langchain_google_vertexai now."""

        def _generate(self, *args, **kwargs):  # pragma: no cover
            raise NotImplementedError(
                "ChatVertexAI stub: install langchain-google-vertexai for the real class."
            )

        @property
        def _llm_type(self) -> str:
            return "stub-vertexai"

    module = types.ModuleType(name)
    module.ChatVertexAI = ChatVertexAI
    sys.modules[name] = module


_install_vertexai_stub()
