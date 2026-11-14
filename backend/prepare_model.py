"""Explicit network step; only downloads model weights, never sends user text."""
import argparse
import json
from pathlib import Path

from ctranslate2.converters import TransformersConverter
from huggingface_hub import snapshot_download
from transformers import M2M100Tokenizer

parser = argparse.ArgumentParser()
parser.add_argument('--output', default='/models/m2m100')
parser.add_argument('--revision', default='main', help='Use an audited Hugging Face commit SHA for reproducibility')
args = parser.parse_args()
root = Path(args.output)
root.mkdir(parents=True, exist_ok=True)
if (root / 'ct2').exists():
    raise SystemExit('ct2 already exists; choose a new output directory to avoid overwriting it.')
snapshot = snapshot_download('facebook/m2m100_418M', revision=args.revision,
    allow_patterns=['*.json', '*.model', 'pytorch_model.bin', 'model.safetensors'])
staging = root / 'ct2-building'
if staging.exists():
    raise SystemExit('An interrupted ct2-building directory exists. Inspect/remove it before retrying.')
print('Downloaded snapshot:', snapshot, flush=True)
M2M100Tokenizer.from_pretrained(snapshot, local_files_only=True).save_pretrained(root / 'tokenizer')
TransformersConverter(snapshot).convert(str(staging), quantization='int8')
staging.rename(root / 'ct2')
(root / 'provenance.json').write_text(json.dumps({'repo': 'facebook/m2m100_418M',
    'requested_revision': args.revision, 'snapshot': Path(snapshot).name, 'quantization': 'int8'}, indent=2))
print('Model converted successfully:', root, flush=True)
