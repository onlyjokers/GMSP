from __future__ import annotations

import inspect
from typing import Any, Callable, Iterable


DEFAULT_ALGORITHM = "dapo"
DEFAULT_SOFT_OVERLONG_CACHE_RATIO = 0.2


def _normalize_algorithm_name(training_config: dict[str, Any]) -> str:
    algorithm = str(training_config.get("algorithm", DEFAULT_ALGORITHM)).strip().lower()
    if algorithm != "dapo":
        raise ValueError(f"Unsupported policy optimization algorithm: {algorithm}")
    return algorithm


def _load_trl_classes():
    from trl import GRPOConfig, GRPOTrainer

    return GRPOConfig, GRPOTrainer


def _filter_supported_kwargs(config_cls, kwargs: dict[str, Any]) -> dict[str, Any]:
    try:
        supported = inspect.signature(config_cls).parameters
    except (TypeError, ValueError):
        return {key: value for key, value in kwargs.items() if value is not None}
    return {
        key: value
        for key, value in kwargs.items()
        if value is not None and key in supported
    }


def _resolve_max_completion_length(
    training_config: dict[str, Any],
    *,
    max_prompt_length: int,
    max_seq_length: int,
) -> int:
    max_completion_length = training_config.get("max_completion_length")
    if max_completion_length is None:
        max_completion_length = max_seq_length - max_prompt_length
    max_completion_length = int(max_completion_length)
    if max_completion_length <= 0:
        raise ValueError(
            f"Invalid max_completion_length={max_completion_length}; "
            f"expected a positive integer."
        )
    return max_completion_length


def _resolve_soft_overlong_cache(
    training_config: dict[str, Any], max_completion_length: int
) -> int:
    cache_tokens = training_config.get("soft_overlong_cache_tokens")
    if cache_tokens is not None:
        resolved = int(cache_tokens)
    else:
        ratio = float(
            training_config.get(
                "soft_overlong_cache_ratio",
                DEFAULT_SOFT_OVERLONG_CACHE_RATIO,
            )
        )
        ratio = max(0.0, min(1.0, ratio))
        resolved = int(max_completion_length * ratio)
    return max(0, min(resolved, max_completion_length))


def get_policy_trainer_class():
    _, trainer_cls = _load_trl_classes()
    return trainer_cls


def build_training_args(
    training_config: dict[str, Any],
    *,
    max_prompt_length: int,
    max_seq_length: int,
    output_dir: str,
):
    _normalize_algorithm_name(training_config)
    config_cls, _ = _load_trl_classes()
    max_completion_length = _resolve_max_completion_length(
        training_config,
        max_prompt_length=max_prompt_length,
        max_seq_length=max_seq_length,
    )

    raw_args = {
        "loss_type": training_config.get("loss_type", "dapo"),
        "mask_truncated_completions": training_config.get(
            "mask_truncated_completions", True
        ),
        "epsilon": training_config.get("epsilon", 0.2),
        "epsilon_high": training_config.get("epsilon_high", 0.28),
        "beta": training_config.get("beta", 0.0),
        "learning_rate": training_config["learning_rate"],
        "adam_beta1": training_config["adam_beta1"],
        "adam_beta2": training_config["adam_beta2"],
        "weight_decay": training_config["weight_decay"],
        "warmup_ratio": training_config["warmup_ratio"],
        "lr_scheduler_type": training_config["lr_scheduler_type"],
        "optim": training_config["optim"],
        "logging_steps": training_config["logging_steps"],
        "per_device_train_batch_size": training_config["per_device_train_batch_size"],
        "gradient_accumulation_steps": training_config["gradient_accumulation_steps"],
        "num_generations": training_config["num_generations"],
        "max_prompt_length": max_prompt_length,
        "max_completion_length": max_completion_length,
        "max_steps": training_config["max_steps"],
        "save_steps": training_config["save_steps"],
        "max_grad_norm": training_config["max_grad_norm"],
        "report_to": training_config["report_to"],
        "output_dir": output_dir,
        "scale_rewards": training_config.get("scale_rewards"),
        "top_entropy_quantile": training_config.get("top_entropy_quantile"),
        "num_iterations": training_config.get("num_iterations"),
        "steps_per_generation": training_config.get("steps_per_generation"),
        "importance_sampling_level": training_config.get("importance_sampling_level"),
        "use_vllm": training_config.get("use_vllm"),
        "temperature": training_config.get("temperature"),
        "top_p": training_config.get("top_p"),
        "top_k": training_config.get("top_k"),
        "min_p": training_config.get("min_p"),
        "repetition_penalty": training_config.get("repetition_penalty"),
    }

    supported_args = _filter_supported_kwargs(config_cls, raw_args)
    return config_cls(**supported_args)


def _estimate_completion_length(completion: Any) -> int:
    if isinstance(completion, (list, tuple)):
        if completion and isinstance(completion[0], dict):
            content = completion[0].get("content", "")
            return len(str(content).split())
        return len(completion)
    return 0


def _build_fallback_soft_overlong_punishment(
    max_completion_length: int, soft_overlong_cache: int
) -> Callable[..., list[float]]:
    threshold = max(0, max_completion_length - soft_overlong_cache)

    def _soft_overlong_punishment(
        completion_ids: list[Any] | None = None,
        completions: list[Any] | None = None,
        **kwargs,
    ) -> list[float]:
        values = completion_ids if completion_ids is not None else completions or []
        rewards: list[float] = []
        for item in values:
            length = _estimate_completion_length(item)
            if length <= threshold:
                rewards.append(0.0)
            elif length <= max_completion_length:
                if soft_overlong_cache <= 0:
                    rewards.append(0.0)
                else:
                    rewards.append(-(length - threshold) / soft_overlong_cache)
            else:
                rewards.append(-1.0)
        return rewards

    _soft_overlong_punishment.__name__ = "soft_overlong_punishment"
    return _soft_overlong_punishment


def build_soft_overlong_punishment_reward(
    training_config: dict[str, Any], *, max_completion_length: int
) -> Callable[..., list[float]] | None:
    if not training_config.get("use_soft_overlong_punishment", True):
        return None

    soft_overlong_cache = _resolve_soft_overlong_cache(
        training_config, max_completion_length
    )
    try:
        from trl.rewards import get_soft_overlong_punishment
    except Exception:
        reward_fn = _build_fallback_soft_overlong_punishment(
            max_completion_length=max_completion_length,
            soft_overlong_cache=soft_overlong_cache,
        )
    else:
        reward_fn = get_soft_overlong_punishment(
            max_completion_len=max_completion_length,
            soft_punish_cache=soft_overlong_cache,
        )
    reward_fn.__name__ = "soft_overlong_punishment"
    return reward_fn


def build_reward_functions(
    base_reward_functions: Iterable[Callable[..., Any]],
    training_config: dict[str, Any],
    *,
    max_completion_length: int,
) -> list[Callable[..., Any]]:
    _normalize_algorithm_name(training_config)
    reward_functions = list(base_reward_functions)
    soft_overlong_reward = build_soft_overlong_punishment_reward(
        training_config,
        max_completion_length=max_completion_length,
    )
    if soft_overlong_reward is not None:
        reward_functions.append(soft_overlong_reward)
    return reward_functions


def describe_training_recipe(
    training_config: dict[str, Any],
    *,
    max_prompt_length: int,
    max_completion_length: int,
    reward_functions: Iterable[Callable[..., Any]],
) -> dict[str, Any]:
    _normalize_algorithm_name(training_config)
    reward_names = [getattr(func, "__name__", type(func).__name__) for func in reward_functions]
    return {
        "algorithm": "dapo",
        "trainer_backend": "trl.GRPOTrainer",
        "dynamic_sampling_requested": bool(training_config.get("dynamic_sampling", False)),
        "dynamic_sampling_supported": False,
        "dynamic_sampling_note": (
            "Current TRL DAPO recipe does not implement dynamic sampling; "
            "this run uses the vanilla DAPO configuration."
        ),
        "loss_type": training_config.get("loss_type", "dapo"),
        "mask_truncated_completions": training_config.get(
            "mask_truncated_completions", True
        ),
        "epsilon": training_config.get("epsilon", 0.2),
        "epsilon_high": training_config.get("epsilon_high", 0.28),
        "beta": training_config.get("beta", 0.0),
        "num_generations": training_config["num_generations"],
        "max_prompt_length": max_prompt_length,
        "max_completion_length": max_completion_length,
        "use_soft_overlong_punishment": training_config.get(
            "use_soft_overlong_punishment", True
        ),
        "soft_overlong_cache_tokens": _resolve_soft_overlong_cache(
            training_config, max_completion_length
        ),
        "reward_functions": reward_names,
    }
