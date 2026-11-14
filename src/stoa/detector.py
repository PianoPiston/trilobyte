"""Symbol detector for raster floor plans (torchvision Faster R-CNN v2, BSD-3; COCO-pretrained backbone).

Trained ONLY on TRAIN-split cubicasa drawings with boxes from the original CubiCasa5k SVG annotations
(scripts/build_det_dataset.py, scripts/train_detector.py). Classes: see CLASSES.
"""
import math, os
import torch, torchvision
from torchvision.models.detection import fasterrcnn_resnet50_fpn_v2
from torchvision.models.detection.anchor_utils import AnchorGenerator
from torchvision.models.detection.rpn import RPNHead

CLASSES_V1 = ["window", "door", "toilet", "sink", "shower", "bathtub", "sauna_stove"]
ROOM_CLASSES = ["room_bedroom", "room_kitchen", "room_bath", "room_wc", "room_balcony", "room_sauna"]
# det1 = v1 (symbols only); det2 = v2 (symbols + room-type boxes). Select with STOA_DET_CLASSES=v2.
CLASSES = CLASSES_V1 + (ROOM_CLASSES if os.environ.get("STOA_DET_CLASSES", "v1") == "v2" else [])
MAX_SIDE = int(os.environ.get("STOA_DET_MAX_SIDE", 1600))


def build_model(pretrained_path=None, max_side=MAX_SIDE):
    ratios = ((0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0),) * 5
    anchors = AnchorGenerator(sizes=((16,), (32,), (64,), (128,), (256,)), aspect_ratios=ratios)
    m = fasterrcnn_resnet50_fpn_v2(weights=None, weights_backbone=None, num_classes=91,
                                   min_size=max_side, max_size=max_side, box_detections_per_img=300,
                                   box_score_thresh=0.05)
    if pretrained_path:
        sd = torch.load(pretrained_path, map_location="cpu")
        m.load_state_dict(sd)
    m.rpn.anchor_generator = anchors
    m.rpn.head = RPNHead(256, len(ratios[0]), conv_depth=2)
    from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
    m.roi_heads.box_predictor = FastRCNNPredictor(1024, len(CLASSES) + 1)
    return m


def resize_for(w, h, max_side=MAX_SIDE):
    s = min(1.0, max_side / max(w, h))
    return s


@torch.no_grad()
def detect(model, pil_img, device="cuda", max_side=MAX_SIDE):
    """returns list of {cls, score, bbox_px} in ORIGINAL image pixels"""
    import torchvision.transforms.functional as TF
    w, h = pil_img.size
    s = resize_for(w, h, max_side)
    img = pil_img.convert("RGB")
    if s < 1:
        img = img.resize((max(1, int(w * s)), max(1, int(h * s))))
    t = TF.to_tensor(img).to(device)
    model.eval()
    out = model([t])[0]
    res = []
    for b, l, sc in zip(out["boxes"].tolist(), out["labels"].tolist(), out["scores"].tolist()):
        res.append({"cls": CLASSES[l - 1], "score": round(sc, 4), "bbox_px": [round(v / s, 1) for v in b]})
    return res
