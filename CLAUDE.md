# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

GMSP is a research workspace for training LLMs to generate Blender materials (and GLSL shaders) using reinforcement learning. The core loop: an LLM generates Python code for Blender node-based materials → code is sent over ZeroMQ to a remote Blender instance (the companion `GMSPforBlender` add-on) → Blender returns accuracy/meaning rankings → rankings feed as reward signals into a DAPO RL training loop.

The Blender add-on lives in a separate `GMSPforBlender` repository. This repo is the training and experimentation side.

## Commands

```bash
# Install (editable, src layout)
pip install -e .

# CUDA/torch/triton/xformers/unsloth environment check
python scripts/check_cuda.py

# Download and set up model weights (Qwen3.5-4B from ModelScope)
python scripts/setup_model_sources.py --source modelscope

# Send a material file to Blender
python scripts/send_material.py path/to/material.py --server 127.0.0.1 --port 5555

# Send a GLSL shader file
python scripts/send_glsl.py path/to/shader.glsl

# Ad-hoc test runners (hardcoded test payloads)
python scripts/manual_runner.py
python scripts/glsl_runner.py
```

No test framework is set up yet — `tests/` is empty. No linter, formatter, or type checker is configured.

## Architecture

### Config system (`src/gmsp/config.py`)
Three-layer deep-merge: hardcoded `FALLBACK_CONFIG` → `configs/default.json` → `configs/local.json` (gitignored). Supports env vars `GMSP_CONFIG_PATH` / `GSMP_CONFIG_PATH`. Uses a profile system — default profile is `blenderllm_qwen3_5_4b`. Profile defaults are merged under the resolved profile via `get_profile()`.

### Clients (`src/gmsp/clients/`)
- `blender_client.py` — `MaterialSender` (ZMQ REQ-REP or ROUTER for reverse-connect), `ClientSender` (persistent connection wrapper). Batch material sending with retry (up to 5), heartbeat, msgpack serialization. Returns `accuracy_rank` and `meaning_rank`.
- `glsl_client.py` — `GLSLShaderClient`, parallel structure to blender_client for GLSL shaders.

### Training (`src/gmsp/training/rl_training.py`)
Only supports DAPO algorithm (raises on anything else). `build_training_args()` constructs a `trl.GRPOConfig`. `build_reward_functions()` composes reward list with optional soft overlong punishment.

### Tracking (`src/gmsp/tracking/experiment_tracking.py`)
`ExperimentTracker` creates structured run directories under `./runs/` with manifest, config snapshots, metrics (JSONL), reward events, checkpoint logs. `ExperimentTrackingCallback` hooks into HuggingFace `TrainerCallback`.

### Training surface
Training is notebook-driven — `notebooks/gmsp_main.ipynb` is the main end-to-end entrypoint. Not yet scriptified.

## Key Conventions

- Reusable code goes in `src/gmsp/`, runnable entrypoints in `scripts/`, exploratory work in `notebooks/`
- `models/` and `runs/` are local machine state (gitignored)
- `experiments/` is legacy scratch space
- Scripts use `scripts/_bootstrap.py` to add `src/` to `sys.path`
- Python >= 3.11 required; key deps: `unsloth`, `trl`, `torch`, `datasets`, `pyzmq`, `msgpack`
- Code comments and some docs are in Chinese
- The ranking config in `default.json` references `gpt-4.1-mini` as an external LLM-as-judge on the Blender evaluation side
