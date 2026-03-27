import copy
import json
import os
from pathlib import Path


CONFIG_ENV_VAR = "GSMP_CONFIG_PATH"
DEFAULT_CONFIG_NAME = "gsmp_config.json"
LOCAL_OVERRIDE_NAME = "gsmp_config.local.json"

FALLBACK_CONFIG = {
    "schema_version": 1,
    "webtrans": {
        "timeout_ms": 15000,
        "material_timeout_sec": 30.0,
        "full_results_cache_size": 10,
        "response_cache_size": 128,
        "output_dir": "~/GSMPforBlender/output",
    },
    "tracking": {
        "enabled": True,
        "runs_dir": "./runs",
        "save_reward_payloads": True,
        "save_samples": True,
        "save_dataset_summary": True,
    },
    "profile_defaults": {
        "transport": {
            "server_address": "localhost",
            "port": 5555,
            "timeout_ms": 15000,
            "reverse_mode": False,
        },
        "lora": {
            "finetune_vision_layers": False,
            "finetune_language_layers": True,
            "finetune_attention_modules": True,
            "finetune_mlp_modules": True,
            "lora_dropout": 0,
            "bias": "none",
            "random_state": 3407,
        },
        "training": {
            "learning_rate": 5e-6,
            "adam_beta1": 0.9,
            "adam_beta2": 0.99,
            "weight_decay": 0.1,
            "warmup_ratio": 0.1,
            "lr_scheduler_type": "cosine",
            "optim": "adamw_torch_fused",
            "logging_steps": 1,
            "per_device_train_batch_size": 4,
            "gradient_accumulation_steps": 1,
            "num_generations": 4,
            "max_prompt_length": 256,
            "max_steps": 1200,
            "save_steps": 200,
            "max_grad_norm": 0.1,
            "report_to": "none",
        },
    },
    "profiles": {},
}


def _repo_root():
    return Path(__file__).resolve().parent


def _deep_merge(base, override):
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _load_json_file(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def expand_path(path_value, *, base_dir=None):
    if not path_value:
        return None
    expanded = Path(os.path.expanduser(path_value))
    if expanded.is_absolute():
        return expanded
    root = Path(base_dir) if base_dir else _repo_root()
    return (root / expanded).resolve()


def load_gsmp_config(config_path=None):
    config = copy.deepcopy(FALLBACK_CONFIG)

    env_config_path = os.getenv(CONFIG_ENV_VAR, "").strip()
    chosen_path = expand_path(config_path) if config_path else None
    if chosen_path is None and env_config_path:
        chosen_path = expand_path(env_config_path)
    if chosen_path is None:
        chosen_path = _repo_root() / DEFAULT_CONFIG_NAME

    if chosen_path.exists():
        _deep_merge(config, _load_json_file(chosen_path))

    local_override_path = chosen_path.with_name(LOCAL_OVERRIDE_NAME)
    if local_override_path.exists():
        _deep_merge(config, _load_json_file(local_override_path))

    config["_resolved_config_path"] = str(chosen_path.resolve())
    config["_resolved_local_override_path"] = str(local_override_path.resolve())
    return config


def get_profile(config, profile_name):
    profiles = config.get("profiles", {})
    if profile_name not in profiles:
        raise KeyError(f"Unknown GSMP profile: {profile_name}")

    profile = copy.deepcopy(config.get("profile_defaults", {}))
    _deep_merge(profile, copy.deepcopy(profiles[profile_name]))
    profile["profile_name"] = profile_name
    return profile
