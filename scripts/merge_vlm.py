"""Merge LoRA adapters (in order) into the base VLM and save a full model directory that vLLM can serve.
Needed when an adapter also touches the vision tower (train_sft.py --train-vision).
usage: python -I scripts/merge_vlm.py --model Qwen/Qwen3.5-4B --adapters /root/adapters/run1-step1050 /root/ckpt/run2/step480 --out /root/models/run2"""
import argparse
import torch
from peft import PeftModel
from transformers import AutoModelForImageTextToText, AutoProcessor

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True); ap.add_argument("--adapters", nargs="+", required=True); ap.add_argument("--out", required=True)
a = ap.parse_args()
m = AutoModelForImageTextToText.from_pretrained(a.model, dtype=torch.bfloat16)
for ad in a.adapters:
    m = PeftModel.from_pretrained(m, ad).merge_and_unload()
    print("merged", ad, flush=True)
m.save_pretrained(a.out)
AutoProcessor.from_pretrained(a.model).save_pretrained(a.out)
print("saved", a.out)
