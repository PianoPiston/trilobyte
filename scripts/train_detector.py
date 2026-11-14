"""Train the floor-plan symbol detector (TRAIN-split cubicasa drawings only).
usage (inside the stoa-train container):
  python -I scripts/train_detector.py --labels det_train.jsonl --data /w/data/junction-dataset --out /w/ckpt/det1 \
      --coco /w/ckpt/fasterrcnn_resnet50_fpn_v2_coco.pth --epochs 12
"""
import argparse, json, math, os, random, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import torch
import torchvision.transforms.functional as TF
from PIL import Image
from stoa.detector import build_model, CLASSES, MAX_SIDE, resize_for

Image.MAX_IMAGE_PIXELS = None


class DS(torch.utils.data.Dataset):
    def __init__(self, rows, root, train):
        self.rows, self.root, self.train = rows, root, train

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        img = Image.open(os.path.join(self.root, r["path"])).convert("RGB")
        w, h = img.size
        s = resize_for(w, h)
        if s < 1:
            img = img.resize((int(w * s), int(h * s)), Image.BILINEAR)
        b = torch.tensor(r["boxes"], dtype=torch.float32).reshape(-1, 4) * s
        lab = torch.tensor([CLASSES.index(c) + 1 for c in r["labels"]], dtype=torch.int64)
        t = TF.to_tensor(img)
        if self.train:
            W, H = t.shape[2], t.shape[1]
            if random.random() < 0.5:
                t = t.flip(2); b = torch.stack([W - b[:, 2], b[:, 1], W - b[:, 0], b[:, 3]], 1) if len(b) else b
            if random.random() < 0.5:
                t = t.flip(1); b = torch.stack([b[:, 0], H - b[:, 3], b[:, 2], H - b[:, 1]], 1) if len(b) else b
            if random.random() < 0.5:  # transpose (with the flips this covers all 8 rotations/reflections)
                t = t.transpose(1, 2).contiguous(); b = b[:, [1, 0, 3, 2]] if len(b) else b
            if random.random() < 0.3:
                g = t.mean(0, keepdim=True); t = g.expand(3, -1, -1).contiguous()
            if random.random() < 0.3:
                t = (t * random.uniform(0.8, 1.2) + random.uniform(-0.1, 0.1)).clamp(0, 1)
        if len(b):
            W, H = t.shape[2], t.shape[1]
            b[:, 0::2] = b[:, 0::2].clamp(0, W); b[:, 1::2] = b[:, 1::2].clamp(0, H)
            keep = ((b[:, 2] - b[:, 0]) >= 1) & ((b[:, 3] - b[:, 1]) >= 1)
            b, lab = b[keep], lab[keep]
        return t, {"boxes": b.reshape(-1, 4), "labels": lab}


def collate(b):
    return tuple(zip(*b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True); ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--coco"); ap.add_argument("--epochs", type=int, default=12); ap.add_argument("--bs", type=int, default=4)
    ap.add_argument("--lr", type=float, default=0.02); ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int); ap.add_argument("--max-hours", type=float, default=3.5)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows = [json.loads(l) for l in open(a.labels)]
    miss = [r for r in rows if not os.path.exists(os.path.join(a.data, r["path"]))]
    rows = [r for r in rows if os.path.exists(os.path.join(a.data, r["path"]))]
    print("missing images skipped:", len(miss), flush=True)
    tr = [r for r in rows if not r["holdout"]]
    if a.limit:
        tr = tr[: a.limit]
    print("train drawings", len(tr), "holdout", sum(r["holdout"] for r in rows), flush=True)
    dl = torch.utils.data.DataLoader(DS(tr, a.data, True), batch_size=a.bs, shuffle=True, num_workers=a.workers,
                                     collate_fn=collate, drop_last=True, persistent_workers=True)
    dev = "cuda"
    model = build_model(a.coco).to(dev)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.SGD(params, lr=a.lr, momentum=0.9, weight_decay=1e-4)
    total = a.epochs * len(dl); warm = 300
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda it: min(1, (it + 1) / warm) * 0.5 * (1 + math.cos(math.pi * min(it, total) / total)))
    it, t0 = 0, time.time()
    for ep in range(a.epochs):
        model.train()
        for imgs, tg in dl:
            imgs = [x.to(dev, non_blocking=True) for x in imgs]
            tg = [{k: v.to(dev) for k, v in t.items()} for t in tg]
            with torch.autocast("cuda", dtype=torch.bfloat16):
                losses = model(imgs, tg)
            loss = sum(losses.values())
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 10.0)
            opt.step(); sched.step(); it += 1
            if it % 50 == 0:
                print(json.dumps({"it": it, "ep": ep, "loss": round(loss.item(), 4), **{k: round(v.item(), 4) for k, v in losses.items()},
                                  "lr": round(sched.get_last_lr()[0], 5), "min": round((time.time() - t0) / 60, 1)}), flush=True)
            if (time.time() - t0) / 3600 > a.max_hours:
                break
        torch.save(model.state_dict(), os.path.join(a.out, f"ep{ep}.pt"))
        print("saved epoch", ep, round((time.time() - t0) / 60, 1), "min", flush=True)
        if (time.time() - t0) / 3600 > a.max_hours:
            print("time budget reached"); break
    torch.save(model.state_dict(), os.path.join(a.out, "last.pt"))


if __name__ == "__main__":
    main()
