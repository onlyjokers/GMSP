from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


DEFAULT_MODEL_ID = "Qwen/Qwen3.5-4B"
DEFAULT_MODEL_ALIAS = "qwen3.5-4b"
DEFAULT_HF_ENDPOINT = "https://huggingface.co"


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _models_dir() -> Path:
    return _project_root() / "models"


def _canonical_model_path() -> Path:
    return _models_dir() / DEFAULT_MODEL_ALIAS


def _modelscope_link_path() -> Path:
    return _models_dir() / "modelscope" / DEFAULT_MODEL_ALIAS


def _huggingface_model_dir() -> Path:
    return _models_dir() / "huggingface" / DEFAULT_MODEL_ALIAS


def _replace_path(path: Path, target: Path | None = None) -> None:
    if path.is_symlink() or path.exists():
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)
    if target is not None:
        path.symlink_to(target)


def _download_from_modelscope(model_id: str) -> Path:
    try:
        from modelscope.hub.snapshot_download import snapshot_download
    except ImportError as exc:
        raise SystemExit(
            "ModelScope is not installed in the current environment. "
            "Install it first, for example: pip install modelscope"
        ) from exc

    return Path(snapshot_download(model_id=model_id)).resolve()


def _download_from_huggingface(model_id: str, endpoint: str | None) -> Path:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise SystemExit(
            "huggingface_hub is not installed in the current environment. "
            "Install it first, for example: pip install huggingface_hub hf-xet"
        ) from exc

    local_dir = _huggingface_model_dir()
    local_dir.mkdir(parents=True, exist_ok=True)
    token = os.getenv("HF_TOKEN") or None
    endpoint = endpoint or os.getenv("HF_ENDPOINT") or DEFAULT_HF_ENDPOINT
    snapshot_download(
        repo_id=model_id,
        local_dir=str(local_dir),
        token=token,
        endpoint=endpoint,
    )
    return local_dir.resolve()


def _activate_model(target_path: Path) -> Path:
    canonical_path = _canonical_model_path()
    _replace_path(canonical_path, target_path.resolve())
    return canonical_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download and wire up Qwen/Qwen3.5-4B for the GMSP project."
    )
    parser.add_argument(
        "--source",
        choices=("modelscope", "huggingface", "both"),
        default="modelscope",
        help="Which source to prepare. Default: modelscope.",
    )
    parser.add_argument(
        "--activate-source",
        choices=("modelscope", "huggingface"),
        default="modelscope",
        help="Which prepared source should become ./models/qwen3.5-4b.",
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help=f"Model repo id to use. Default: {DEFAULT_MODEL_ID}.",
    )
    parser.add_argument(
        "--hf-endpoint",
        default=os.getenv("HF_ENDPOINT", DEFAULT_HF_ENDPOINT),
        help="Hugging Face endpoint to use for downloads.",
    )
    args = parser.parse_args()

    prepared_paths: dict[str, Path] = {}

    if args.source in {"modelscope", "both"}:
        modelscope_cache_path = _download_from_modelscope(args.model_id)
        modelscope_link_path = _modelscope_link_path()
        _replace_path(modelscope_link_path, modelscope_cache_path)
        prepared_paths["modelscope"] = modelscope_link_path.resolve()

    if args.source in {"huggingface", "both"}:
        huggingface_path = _download_from_huggingface(args.model_id, args.hf_endpoint)
        prepared_paths["huggingface"] = huggingface_path.resolve()

    if args.activate_source not in prepared_paths:
        raise SystemExit(
            f"Cannot activate source {args.activate_source!r}; "
            f"prepared sources are: {sorted(prepared_paths)}"
        )

    canonical_path = _activate_model(prepared_paths[args.activate_source])

    print(f"Prepared sources: {prepared_paths}")
    print(f"Active model path: {canonical_path} -> {canonical_path.resolve()}")


if __name__ == "__main__":
    main()
