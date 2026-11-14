"""Paths and env configuration for the product backend. Everything is overridable via env."""
import os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(ROOT, "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

# dataset roots (all untrusted data; we only read images/CAD/IFC files and parse them with libraries)
DATA_MAIN = os.environ.get("STOA_DATA", os.path.join(ROOT, "DATA/junction-dataset"))
os.environ.setdefault("STOA_DATA", DATA_MAIN)  # stoa.data reads this at import
DATA_HISTORIC = os.environ.get("STOA_HISTORIC_DATA", os.path.join(ROOT, "DATA/historic-raw/junction-dataset"))
DATA_DEMO = os.environ.get("STOA_DEMO_DATA", os.path.join(ROOT, "DATA/demo-raw/junction-dataset"))
DATA_ROOTS = [DATA_MAIN, DATA_DEMO, DATA_HISTORIC]

APP_DATA = os.path.join(ROOT, "app", "data")          # generated: catalog, cache, index (small, committed)
APP_CACHE = os.environ.get("STOA_APP_CACHE", os.path.join(ROOT, "app", ".cache"))  # thumbs, renders (git-ignored)
CATALOG = os.path.join(APP_DATA, "catalog.json")
ANSWER_CACHE = os.path.join(APP_DATA, "answer_cache.jsonl")
LIVE_CACHE = os.path.join(APP_DATA, "answer_cache_live.jsonl")
SEARCH_INDEX = os.path.join(APP_DATA, "search_index.json")
TRANSFORMS = os.path.join(APP_DATA, "transforms.json")
STD_DIR = os.environ.get("STOA_STD_DIR", os.path.join(ROOT, "standardized"))  # model-derived std files (detector)

# model endpoint (OpenAI-compatible vLLM). Empty -> VLM disabled, cache only.
VLM_BASE_URL = os.environ.get("STOA_VLM_BASE_URL", "").rstrip("/")
VLM_API_KEY = os.environ.get("STOA_VLM_API_KEY", "EMPTY")
VLM_FT_MODEL = os.environ.get("STOA_VLM_FT_MODEL", "")       # LoRA adapter name; auto-detected from /v1/models
VLM_BASE_MODEL = os.environ.get("STOA_VLM_BASE_MODEL", "Qwen/Qwen3.5-4B")
VLM_GROUND = os.environ.get("STOA_VLM_GROUND", "1") == "1"   # second call for evidence boxes
VLM_TIMEOUT = float(os.environ.get("STOA_VLM_TIMEOUT", "60"))
PREFER_CACHE = os.environ.get("STOA_PREFER_CACHE", "0") == "1"

CONF_SUGGEST = float(os.environ.get("STOA_CONF_SUGGEST", "0.3"))  # below: model guess shown only as a suggestion
CONF_AUTO = float(os.environ.get("STOA_CONF_AUTO", "0.7"))  # leaderboard: >=0.7 -> ~96% precision on val

# cost model (EUR). GPU price of the reference serving setup (Verda A100, €1.65/h) amortised over measured batch
# throughput: fine-tuned answer €0.013/1k q, zero-shot grounding call ~€0.038/1k q (results/leaderboard.md, TEST).
COST_FT_CALL = float(os.environ.get("STOA_COST_FT_CALL", "0.000013"))
COST_GROUND_CALL = float(os.environ.get("STOA_COST_GROUND_CALL", "0.000038"))
# judge: text-only call (~450 prompt + ~30 output tokens, no image) on the same GPU. Estimated from the token ratio to the
# fine-tuned image call (~1,500 tokens -> €0.013/1k): ~€0.004/1k questions. Measured latency is reported per answer.
COST_JUDGE_CALL = float(os.environ.get("STOA_COST_JUDGE_CALL", "0.000004"))
USE_JUDGE = os.environ.get("STOA_USE_JUDGE", "1") == "1"
OCR_ON_ASK = os.environ.get("STOA_OCR_ON_ASK", "1") == "1"  # compute the words layer on first ask if missing
COST_CPU_CALL = float(os.environ.get("STOA_COST_CPU_CALL", "0.000001"))

os.makedirs(APP_DATA, exist_ok=True)
os.makedirs(APP_CACHE, exist_ok=True)
