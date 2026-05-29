"""Quick import test for Day 3 deps."""
import importlib

packages = [
    "langgraph", "langchain", "langchain_anthropic", "langchain_openai",
    "langchain_community", "langfuse", "ragas",
]
for p in packages:
    try:
        m = importlib.import_module(p)
        v = getattr(m, "__version__", "?")
        print(f"  OK   {p:25s} {v}")
    except Exception as e:
        print(f"  FAIL {p:25s} {type(e).__name__}: {str(e)[:120]}")
