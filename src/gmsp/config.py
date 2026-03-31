import copy
import json
import os
from pathlib import Path


PRIMARY_CONFIG_ENV_VAR = "GMSP_CONFIG_PATH"
LEGACY_CONFIG_ENV_VAR = "GSMP_CONFIG_PATH"
DEFAULT_CONFIG_NAME = "default.json"
LEGACY_CONFIG_NAME = "gmsp_config.json"
LOCAL_OVERRIDE_NAME = "local.json"
LEGACY_LOCAL_OVERRIDE_NAME = "gmsp_config.local.json"
DEFAULT_PROFILE_NAME = "blenderllm_qwen3_5_4b"

FALLBACK_CONFIG = {
    "schema_version": 1,
    "webtrans": {
        "timeout_ms": 15000,
        "material_timeout_sec": 30.0,
        "full_results_cache_size": 10,
        "response_cache_size": 128,
        "output_dir": "~/GMSPforBlender/output",
    },
    "tracking": {
        "enabled": True,
        "runs_dir": "./runs",
        "save_reward_payloads": True,
        "save_samples": True,
        "save_dataset_summary": True,
    },
    "default_profile": DEFAULT_PROFILE_NAME,
    "profile_defaults": {
        "transport": {
            "relay_server": "ws://106.15.195.17:8080",
            "timeout_ms": 15000,
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
            "algorithm": "dapo",
            "loss_type": "dapo",
            "mask_truncated_completions": True,
            "epsilon": 0.2,
            "epsilon_high": 0.28,
            "beta": 0.0,
            "use_soft_overlong_punishment": True,
            "soft_overlong_cache_ratio": 0.2,
            "dynamic_sampling": False,
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
            "report_to": "tensorboard",
        },
    },
    "profiles": {},
}


def get_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _config_dir() -> Path:
    return get_project_root() / "configs"


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
    root = Path(base_dir) if base_dir else get_project_root()
    return (root / expanded).resolve()


def _first_env_value(*names):
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _find_existing_config_path(config_path=None):
    if config_path:
        explicit_path = expand_path(config_path)
        if explicit_path and explicit_path.exists():
            return explicit_path
        return explicit_path

    env_config_path = _first_env_value(PRIMARY_CONFIG_ENV_VAR, LEGACY_CONFIG_ENV_VAR)
    if env_config_path:
        env_path = expand_path(env_config_path)
        if env_path and env_path.exists():
            return env_path
        return env_path

    config_dir = _config_dir()
    candidates = [
        config_dir / DEFAULT_CONFIG_NAME,
        get_project_root() / LEGACY_CONFIG_NAME,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return config_dir / DEFAULT_CONFIG_NAME


def load_gmsp_config(config_path=None):
    config = copy.deepcopy(FALLBACK_CONFIG)

    chosen_path = _find_existing_config_path(config_path)

    if chosen_path.exists():
        _deep_merge(config, _load_json_file(chosen_path))

    local_override_path = chosen_path.with_name(LOCAL_OVERRIDE_NAME)
    if not local_override_path.exists():
        legacy_local_override_path = chosen_path.with_name(LEGACY_LOCAL_OVERRIDE_NAME)
        if legacy_local_override_path.exists():
            local_override_path = legacy_local_override_path
    if not local_override_path.exists():
        config_dir_override = _config_dir() / LOCAL_OVERRIDE_NAME
        if config_dir_override.exists():
            local_override_path = config_dir_override
    if not local_override_path.exists():
        legacy_root_override = get_project_root() / LEGACY_LOCAL_OVERRIDE_NAME
        if legacy_root_override.exists():
            local_override_path = legacy_root_override
    if local_override_path.exists():
        _deep_merge(config, _load_json_file(local_override_path))

    config["_resolved_config_path"] = str(chosen_path.resolve())
    config["_resolved_local_override_path"] = str(local_override_path.resolve())
    return config


def load_gsmp_config(config_path=None):
    return load_gmsp_config(config_path=config_path)


def get_default_profile_name(config):
    profiles = config.get("profiles", {})
    requested = str(config.get("default_profile", "")).strip()
    if requested and requested in profiles:
        return requested
    if profiles:
        return next(iter(profiles))
    return DEFAULT_PROFILE_NAME


def get_profile(config, profile_name):
    profiles = config.get("profiles", {})
    if profile_name not in profiles:
        raise KeyError(f"Unknown GMSP profile: {profile_name}")

    profile = copy.deepcopy(config.get("profile_defaults", {}))
    _deep_merge(profile, copy.deepcopy(profiles[profile_name]))
    profile["profile_name"] = profile_name
    return profile
