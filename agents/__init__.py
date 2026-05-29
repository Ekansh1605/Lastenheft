"""Lastenheft agents — LangGraph multi-agent orchestration.

Apply compatibility shims (RAGAS / langchain) before any agent code imports
LangChain so the shim is in place by the time it's needed.
"""

from ml import compat  # noqa: F401
