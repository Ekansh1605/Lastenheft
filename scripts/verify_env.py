"""Day-1 environment verification: torch+CUDA, ML libs, ColQwen2 class."""
import importlib

import torch

print(f"torch: {torch.__version__}")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    props = torch.cuda.get_device_properties(0)
    print(f"CUDA device: {torch.cuda.get_device_name(0)}")
    print(f"VRAM total: {props.total_memory / 1e9:.2f} GB")
    print(f"Compute capability: {props.major}.{props.minor}")
print()

packages = [
    "transformers", "colpali_engine", "fastapi", "langgraph", "langchain",
    "langchain_anthropic", "pypdfium2", "pgvector", "psycopg", "ragas",
    "langfuse", "peft", "sentence_transformers", "ragas",
]
for p in packages:
    try:
        m = importlib.import_module(p)
        v = getattr(m, "__version__", "?")
        print(f"  OK   {p:25s} {v}")
    except ImportError as e:
        print(f"  MISS {p:25s} {e}")

print()
print("--- ColQwen2 + ColPali class import (should both succeed) ---")
try:
    from colpali_engine.models import ColPali, ColPaliProcessor, ColQwen2, ColQwen2Processor
    print(f"  OK   ColQwen2={ColQwen2.__name__}, ColPali={ColPali.__name__}")
    print(f"  OK   Processors: {ColQwen2Processor.__name__}, {ColPaliProcessor.__name__}")
except Exception as e:
    print(f"  FAIL {type(e).__name__}: {e}")
