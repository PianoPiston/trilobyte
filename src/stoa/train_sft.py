#!/usr/bin/env python3
"""LoRA SFT of a Qwen-family VLM on the TRAIN split only.

One sample = one drawing: image + all its questions as a multi-turn chat (one random language per
EN/translation pair, order shuffled). The image is encoded once per drawing, so an epoch costs ~1 image
pass per drawing instead of one per question. Loss only on assistant answers.

Target per turn (compact; confidence comes from answer-token logprobs at inference):
    {"answer": 5, "unit": "count"}
Prompt rendering uses the model's own chat template (same as vLLM at inference), user content = image +
raw question (eval prompt "ft").

LoRA is applied to the language model only so vLLM can serve base + adapter (no merged copy on disk) and the
base (adapter off) stays available for evidence/grounding calls.

  python -m stoa.train_sft --model Qwen/Qwen3-VL-4B-Instruct --out /root/ckpt/run1 --epochs 2
"""
import argparse, json, math, os, random, re, sys, time
import torch
from torch.utils.data import Dataset, DataLoader

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from stoa.data import load_questions, image_path_for  # noqa: E402
from stoa.images import load_image  # noqa: E402


def fmt_answer(q):
    a = q.answer
    if q.type == "count":
        a = int(round(float(a)))
    elif isinstance(a, float):
        a = round(a, 3)
    return json.dumps({"answer": a, "unit": q.unit or "text"}, ensure_ascii=False)


def build_conversations(seed, max_turns, sources=None):
    qs = [q for q in load_questions() if q.split == "train" and image_path_for(q.path) is not None]
    if sources:
        qs = [q for q in qs if q.source in sources]
    rng = random.Random(seed)
    by_pair = {}
    for q in qs:
        by_pair.setdefault(q.pair, []).append(q)
    by_img = {}
    for v in by_pair.values():
        q = rng.choice(v)
        by_img.setdefault(q.path, []).append(q)
    convs = []
    for path, lst in by_img.items():
        rng.shuffle(lst)
        for i in range(0, len(lst), max_turns):
            convs.append((path, [(q.question, fmt_answer(q)) for q in lst[i:i + max_turns]]))
    rng.shuffle(convs)
    return convs


class ConvDataset(Dataset):
    def __init__(self, convs, processor, max_pixels, template_kwargs, min_pixels=0):
        self.convs, self.proc, self.max_pixels, self.tk = convs, processor, max_pixels, template_kwargs
        self.min_pixels = min_pixels
        tok = processor.tokenizer
        self.im_end = tok.convert_tokens_to_ids("<|im_end|>")

    def _render(self, content):
        s = self.proc.apply_chat_template([{"role": "user", "content": content}], tokenize=False,
                                          add_generation_prompt=True, **self.tk)
        return s

    def __len__(self):
        return len(self.convs)

    def __getitem__(self, i):
        path, turns = self.convs[i]
        img = load_image(image_path_for(path), self.max_pixels, self.min_pixels)
        tok = self.proc.tokenizer
        first = self._render([{"type": "image"}, {"type": "text", "text": turns[0][0]}])
        enc = self.proc(text=[first], images=[img], return_tensors="pt")
        ids = enc["input_ids"][0].tolist()
        labels = [-100] * len(ids)
        sys_prefix = None
        for k, (q, a) in enumerate(turns):
            if k > 0:
                p = self._render([{"type": "text", "text": q}])
                if sys_prefix is None:
                    m = re.match(r"(<\|im_start\|>system.*?<\|im_end\|>\n)", p, re.S)
                    sys_prefix = m.group(1) if m else ""
                if sys_prefix and p.startswith(sys_prefix):
                    p = p[len(sys_prefix):]
                pid = tok(p, add_special_tokens=False)["input_ids"]
                ids += pid; labels += [-100] * len(pid)
            aid = tok(a, add_special_tokens=False)["input_ids"] + [self.im_end]
            nl = tok("\n", add_special_tokens=False)["input_ids"]
            ids += aid + nl; labels += aid + [-100] * len(nl)
        L0 = enc["input_ids"].shape[1]
        out = {}
        for k, v in enc.items():
            if k in ("input_ids", "attention_mask"):
                continue
            if torch.is_tensor(v) and v.dim() == 2 and v.shape[0] == 1 and v.shape[1] == L0:
                # per-token tensors (e.g. mm_token_type_ids): later turns are text -> 0
                v = torch.cat([v, torch.zeros(1, len(ids) - L0, dtype=v.dtype)], dim=1)
            out[k] = v
        out["input_ids"] = torch.tensor([ids])
        out["attention_mask"] = torch.ones_like(out["input_ids"])
        out["labels"] = torch.tensor([labels])
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=float, default=2); ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=32); ap.add_argument("--alpha", type=int, default=64)
    ap.add_argument("--grad-accum", type=int, default=8); ap.add_argument("--max-pixels", type=int, default=2_000_000); ap.add_argument("--min-pixels", type=int, default=0)
    ap.add_argument("--max-turns", type=int, default=24); ap.add_argument("--save-every", type=int, default=150)
    ap.add_argument("--keep", type=int, default=4); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--no-thinking", action="store_true", help="render with enable_thinking=False (Qwen3.5)")
    ap.add_argument("--sources", nargs="*"); ap.add_argument("--max-steps", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    a = ap.parse_args()
    from transformers import AutoProcessor, AutoModelForImageTextToText, get_cosine_schedule_with_warmup
    from peft import LoraConfig, get_peft_model

    torch.manual_seed(a.seed)
    os.makedirs(a.out, exist_ok=True)
    json.dump(vars(a), open(os.path.join(a.out, "train_args.json"), "w"), indent=1)
    proc = AutoProcessor.from_pretrained(a.model)
    tk = {"enable_thinking": False} if a.no_thinking else {}
    model = AutoModelForImageTextToText.from_pretrained(a.model, dtype=torch.bfloat16, attn_implementation="sdpa").cuda()
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    # language-model linear layers only (vLLM-servable LoRA); vision tower frozen
    names = {n.split(".")[-1] for n, m in model.named_modules() if isinstance(m, torch.nn.Linear)
             and "visual" not in n and "lm_head" not in n and "vision" not in n}
    target = [n for n in names if n in {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj",
                                        "in_proj_qkvz", "in_proj_ba", "in_proj_qkv", "in_proj_z", "in_proj_b", "in_proj_a", "out_proj"}]
    regex = r"^(?!.*(visual|vision)).*\.(" + "|".join(target) + r")$"
    print("lora targets:", target, flush=True)
    model = get_peft_model(model, LoraConfig(r=a.rank, lora_alpha=a.alpha, lora_dropout=0.05,
                                             target_modules=regex, task_type="CAUSAL_LM"))
    model.print_trainable_parameters()

    convs = build_conversations(a.seed, a.max_turns, a.sources)
    n_turns = sum(len(t) for _, t in convs)
    print(f"{len(convs)} conversations, {n_turns} answer turns", flush=True)
    ds = ConvDataset(convs, proc, a.max_pixels, tk, a.min_pixels)
    total_steps = a.max_steps or math.ceil(len(ds) * a.epochs / a.grad_accum)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0)
    sched = get_cosine_schedule_with_warmup(opt, min(50, total_steps // 10), total_steps)
    model.train()
    step, micro, t0, run_loss, run_tok = 0, 0, time.time(), 0.0, 0
    t_win = time.time()
    saved = []
    log = open(os.path.join(a.out, "train_log.jsonl"), "a")
    epoch = 0
    while step < total_steps:
        g = torch.Generator(); g.manual_seed(a.seed + epoch)
        dl = DataLoader(ds, batch_size=None, shuffle=True, num_workers=a.workers, generator=g,
                        persistent_workers=False, prefetch_factor=4)
        for batch in dl:
            batch = {k: v.cuda(non_blocking=True) for k, v in batch.items()}
            with torch.autocast("cuda", dtype=torch.bfloat16):
                out = model(**batch)
            ntok = int((batch["labels"] != -100).sum())
            (out.loss / a.grad_accum).backward()
            run_loss += out.loss.item(); run_tok += batch["input_ids"].shape[1]; micro += 1
            if micro % a.grad_accum == 0:
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step(); sched.step(); opt.zero_grad(set_to_none=True); step += 1
                if step % 10 == 0:
                    el = time.time() - t0
                    rec = {"step": step, "of": total_steps, "epoch": epoch, "loss": run_loss / (10 * a.grad_accum),
                           "lr": sched.get_last_lr()[0], "tok_per_s": run_tok / (time.time() - t_win), "elapsed_min": el / 60,
                           "eta_min": el / step * (total_steps - step) / 60 if step else None}
                    print(json.dumps(rec), flush=True); log.write(json.dumps(rec) + "\n"); log.flush()
                    run_loss = 0.0; run_tok = 0; t_win = time.time()
                if step % a.save_every == 0 or step == total_steps:
                    d = os.path.join(a.out, f"step{step}")
                    model.save_pretrained(d); saved.append(d)
                    print("saved", d, flush=True)
                    while len(saved) > a.keep:
                        import shutil; shutil.rmtree(saved.pop(0), ignore_errors=True)
                if step >= total_steps:
                    break
        epoch += 1
    print("TRAIN_DONE", flush=True)


if __name__ == "__main__":
    main()
