# GMSP

GMSP is a research workspace for Blender material generation, remote Blender execution, and RL-style training loops.

The project is now organized around a more standard AI research layout:

- `src/` for reusable Python modules
- `scripts/` for runnable entrypoints and diagnostics
- `configs/` for shared and local config files
- `notebooks/` for exploratory and training notebooks
- `data/` for datasets
- `docs/` for operating notes

The Blender add-on itself lives in the separate `GMSPforBlender` repository. This repository is the training and experimentation side.

## Layout

```text
GMSP/
├─ pyproject.toml
├─ README.md
├─ configs/
│  ├─ default.json
│  └─ local.example.json
├─ data/
│  └─ external/
├─ docs/
├─ notebooks/
│  └─ gmsp_main.ipynb
├─ scripts/
│  ├─ send_material.py
│  ├─ send_glsl.py
│  ├─ manual_runner.py
│  ├─ check_cuda.py
│  └─ setup_model_sources.py
├─ src/
│  └─ gmsp/
│     ├─ config.py
│     ├─ clients/
│     ├─ tracking/
│     └─ training/
├─ tests/
└─ models/
```

## Core Modules

- [config.py](/home/GSMP/GMSP/src/gmsp/config.py)
  Loads the project config, resolves paths, and selects profiles.
- [blender_client.py](/home/GSMP/GMSP/src/gmsp/clients/blender_client.py)
  ZeroMQ client for sending Blender material jobs.
- [glsl_client.py](/home/GSMP/GMSP/src/gmsp/clients/glsl_client.py)
  ZeroMQ client for GLSL-side experiments.
- [rl_training.py](/home/GSMP/GMSP/src/gmsp/training/rl_training.py)
  RL training argument construction and reward composition.
- [experiment_tracking.py](/home/GSMP/GMSP/src/gmsp/tracking/experiment_tracking.py)
  Run manifests, metrics, reward payload logging, and checkpoint metadata.

## Main Entrypoints

- Main notebook: [gmsp_main.ipynb](/home/GSMP/GMSP/notebooks/gmsp_main.ipynb)
- Material send CLI: [send_material.py](/home/GSMP/GMSP/scripts/send_material.py)
- GLSL send CLI: [send_glsl.py](/home/GSMP/GMSP/scripts/send_glsl.py)
- Manual Blender request runner: [manual_runner.py](/home/GSMP/GMSP/scripts/manual_runner.py)
- CUDA preflight: [check_cuda.py](/home/GSMP/GMSP/scripts/check_cuda.py)
- Model source setup: [setup_model_sources.py](/home/GSMP/GMSP/scripts/setup_model_sources.py)

## Configuration

Shared defaults live in:

- [default.json](/home/GSMP/GMSP/configs/default.json)

Local machine overrides should live in:

- `configs/local.json`

Start from:

- [local.example.json](/home/GSMP/GMSP/configs/local.example.json)

Current default profile is `blenderllm_qwen3_5_4b`.

## Model Setup

The canonical project model path is:

```text
./models/qwen3.5-4b
```

Default provider:

- ModelScope: `Qwen/Qwen3.5-4B`

Backup provider:

- Hugging Face: `Qwen/Qwen3.5-4B`

Prepare ModelScope and make it active:

```bash
/home/ziqi/miniconda3/bin/python scripts/setup_model_sources.py --source modelscope
```

Prepare both ModelScope and Hugging Face while keeping ModelScope active:

```bash
/home/ziqi/miniconda3/bin/python scripts/setup_model_sources.py --source both --activate-source modelscope
```

Switch the active project model to the Hugging Face copy:

```bash
/home/ziqi/miniconda3/bin/python scripts/setup_model_sources.py --source huggingface --activate-source huggingface
```

More detail is in [model_setup.md](/home/GSMP/GMSP/docs/model_setup.md).

## Quick Start

1. Prepare your Python environment with the training dependencies you already use for `unsloth`, `trl`, `torch`, `datasets`, `pyzmq`, `msgpack`, `modelscope`, and `huggingface_hub`.
2. Prepare the default model:

```bash
/home/ziqi/miniconda3/bin/python scripts/setup_model_sources.py --source modelscope
```

3. Create a local config override from [local.example.json](/home/GSMP/GMSP/configs/local.example.json) and save it as `configs/local.json`.
4. Start the Blender-side service in the `GMSPforBlender` add-on.
5. Open [gmsp_main.ipynb](/home/GSMP/GMSP/notebooks/gmsp_main.ipynb) and run the main workflow.

The main notebook now bootstraps `src/` automatically and switches its working directory to the project root so relative paths stay stable.

## CLI Usage

Send a material file to Blender:

```bash
python scripts/send_material.py path/to/material.py --server 127.0.0.1 --port 5555
```

Run the CUDA environment check:

```bash
python scripts/check_cuda.py
```

## Data

Datasets are now stored under:

- [external](/home/GSMP/GMSP/data/external)

Current research assets include:

- [blendnet](/home/GSMP/GMSP/data/external/blendnet)
- [gsm8k](/home/GSMP/GMSP/data/external/gsm8k)
- [medical_o1_reasoning_sft](/home/GSMP/GMSP/data/external/medical_o1_reasoning_sft)
- [ruozhiba_r1](/home/GSMP/GMSP/data/external/ruozhiba_r1)
- [verl](/home/GSMP/GMSP/data/external/verl)

## Outputs

Run artifacts are written under `./runs` by [experiment_tracking.py](/home/GSMP/GMSP/src/gmsp/tracking/experiment_tracking.py).

Typical run outputs include:

- `manifest.json`
- `config.profile.json`
- `config.full.json`
- `environment.json`
- `dataset_summary.json`
- `metrics.jsonl`
- `checkpoints.jsonl`
- `summary.json`

## Notes

- `notebooks/` is still the main training surface; the project is cleaner now, but training has not been fully scriptified yet.
- `experiments/` remains intentionally messy historical space and was not normalized as part of this restructuring.
- `models/` is treated as local machine state and is ignored by Git.

## Related Docs

- [workspace_layout.md](/home/GSMP/GMSP/docs/workspace_layout.md)
- [model_setup.md](/home/GSMP/GMSP/docs/model_setup.md)
