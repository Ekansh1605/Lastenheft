"""Quick load test for ColPali v1.3 - should produce NO 'MISSING' LoRA warnings now."""
import io
import sys
import warnings

import torch
from PIL import Image

# Capture warnings to see if any MISSING/UNEXPECTED LoRA messages appear
warnings.filterwarnings("error", message=".*MISSING.*", append=True)

import transformers
print(f"transformers: {transformers.__version__}")

import colpali_engine
print(f"colpali_engine module path: {colpali_engine.__file__}")

from colpali_engine.models import ColPali, ColPaliProcessor

print("Loading ColPali v1.3...")
device = "cuda" if torch.cuda.is_available() else "cpu"
dtype = torch.bfloat16 if device == "cuda" else torch.float32

model = ColPali.from_pretrained("vidore/colpali-v1.3", torch_dtype=dtype, device_map=device).eval()
proc = ColPaliProcessor.from_pretrained("vidore/colpali-v1.3")
print(f"  Loaded. VRAM in use: {torch.cuda.memory_allocated()/1e9:.2f} GB")

# Run an actual embedding to make sure forward pass works
print("Running forward pass on a dummy image + query...")
img = Image.new("RGB", (448, 448), color=(127, 127, 127))
with torch.inference_mode():
    img_inputs = proc.process_images([img]).to(model.device)
    img_emb = model(**img_inputs)
    print(f"  Image embedding shape: {tuple(img_emb.shape)}  dtype: {img_emb.dtype}")

    q_inputs = proc.process_queries(["What is the operating voltage?"]).to(model.device)
    q_emb = model(**q_inputs)
    print(f"  Query embedding shape: {tuple(q_emb.shape)}  dtype: {q_emb.dtype}")

print("\n[OK] ColPali loaded and embeds without errors.")
