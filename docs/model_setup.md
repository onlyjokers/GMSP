# Model Setup

The canonical model path used by the project is:

```text
./models/qwen3.5-4b
```

The default config at [default.json](/home/GSMP/GMSP/configs/default.json) points the main workflow to that path.

## Sources

- Default source: ModelScope
- Backup source: Hugging Face
- Default model id: `Qwen/Qwen3.5-4B`

The goal is to keep notebooks and training code source-agnostic. They should load `./models/qwen3.5-4b` and not care whether the files were prepared from ModelScope or Hugging Face.

## Commands

Prepare ModelScope and activate it:

```bash
/home/ziqi/miniconda3/bin/python scripts/setup_model_sources.py --source modelscope
```

Prepare both ModelScope and Hugging Face while keeping ModelScope active:

```bash
/home/ziqi/miniconda3/bin/python scripts/setup_model_sources.py --source both --activate-source modelscope
```

Prepare Hugging Face and switch the project to it:

```bash
/home/ziqi/miniconda3/bin/python scripts/setup_model_sources.py --source huggingface --activate-source huggingface
```

## Local Paths

After setup, the project may contain:

- `models/qwen3.5-4b`
- `models/modelscope/qwen3.5-4b`
- `models/huggingface/qwen3.5-4b`

`models/qwen3.5-4b` is the active path the project will load.

## Notes

- If you need authenticated Hugging Face access, export `HF_TOKEN` first.
- `models/` is gitignored and treated as local machine state.
- The main notebook now lives at [gmsp_main.ipynb](/home/GSMP/GMSP/notebooks/gmsp_main.ipynb).
