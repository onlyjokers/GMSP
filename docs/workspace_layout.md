## Workspace Layout

The active GMSP workspace now follows a standard research-project split:

- `src/` contains reusable code
- `scripts/` contains runnable entrypoints
- `configs/` contains default and local config files
- `notebooks/` contains exploratory and training notebooks
- `data/` contains datasets
- `docs/` contains operational notes

### Active Code

- `src/gmsp/config.py`: runtime configuration loader and path resolver
- `src/gmsp/clients/blender_client.py`: Blender material request client
- `src/gmsp/clients/glsl_client.py`: GLSL request client
- `src/gmsp/training/rl_training.py`: training argument and reward construction
- `src/gmsp/tracking/experiment_tracking.py`: run artifact and metadata tracking

### Entrypoints

- `notebooks/gmsp_main.ipynb`: main end-to-end notebook entrypoint
- `scripts/send_material.py`: CLI wrapper for the Blender material client
- `scripts/send_glsl.py`: CLI wrapper for the GLSL client
- `scripts/manual_runner.py`: ad-hoc Blender request runner
- `scripts/check_cuda.py`: environment preflight for CUDA-side dependencies
- `scripts/setup_model_sources.py`: ModelScope / Hugging Face model wiring

### Config

- `configs/default.json`: shared default config
- `configs/local.example.json`: local override template
- `configs/local.json`: machine-local override, intentionally gitignored

### Data

- `data/external/`: research datasets used by notebooks and training flows

### Local Machine State

- `models/`: local model artifacts and provider-specific links
- `runs/`: generated run outputs and tracking artifacts

### Rules

- Keep reusable Python code under `src/gmsp/`
- Put runnable operational commands under `scripts/`
- Keep notebooks under `notebooks/`
- Treat `models/` and `runs/` as local machine state
- Leave `experiments/` as legacy or scratch space unless it is being actively promoted into the main workflow
