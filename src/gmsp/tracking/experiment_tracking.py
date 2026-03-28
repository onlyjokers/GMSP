import datetime as _dt
import json
import os
import platform
import socket
import subprocess
import sys
from pathlib import Path

from gmsp.config import expand_path, get_project_root


def _json_default(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _safe_git(args):
    try:
        result = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            cwd=get_project_root(),
        )
        return result.stdout.strip()
    except Exception:
        return None


class ExperimentTracker:
    def __init__(self, run_dir, profile_name, profile_config, full_config):
        self.run_dir = Path(run_dir)
        self.profile_name = profile_name
        self.profile_config = profile_config
        self.full_config = full_config
        self.output_dir = self.run_dir / "checkpoints"
        self.files_dir = self.run_dir / "files"
        self.samples_dir = self.run_dir / "samples"
        self.run_id = self.run_dir.name

    def initialize(self):
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.samples_dir.mkdir(parents=True, exist_ok=True)

        manifest = {
            "run_id": self.run_id,
            "profile_name": self.profile_name,
            "created_at_utc": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "hostname": socket.gethostname(),
            "python": sys.version,
            "platform": platform.platform(),
            "git_commit": _safe_git(["git", "rev-parse", "HEAD"]),
            "git_branch": _safe_git(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
            "git_status": _safe_git(["git", "status", "--short"]),
            "config_path": self.full_config.get("_resolved_config_path"),
            "local_override_path": self.full_config.get("_resolved_local_override_path"),
        }
        self.write_json("manifest.json", manifest)
        self.write_json("config.profile.json", self.profile_config)
        self.write_json("config.full.json", self.full_config)
        self.write_json("environment.json", self._environment_snapshot())
        self.write_text(
            "notes.md",
            "\n".join(
                [
                    "# Run Notes",
                    "",
                    "## Objective",
                    "",
                    "## Dataset / Split Notes",
                    "",
                    "## Reward Design Changes",
                    "",
                    "## RL Recipe Notes",
                    "",
                    "## Failure Cases",
                    "",
                    "## Checkpoint Selection Rationale",
                    "",
                    "## Paper-worthy Findings",
                    "",
                ]
            ),
        )

    def _environment_snapshot(self):
        return {
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python_version": sys.version,
            "cwd": os.getcwd(),
            "env": {
                key: os.getenv(key)
                for key in (
                    "CUDA_VISIBLE_DEVICES",
                    "GMSP_CONFIG_PATH",
                    "GSMP_CONFIG_PATH",
                    "GMSP_OPENAI_API_KEY",
                    "GSMP_OPENAI_API_KEY",
                    "OPENAI_API_KEY",
                )
                if os.getenv(key) is not None
            },
        }

    def write_json(self, relative_path, payload):
        path = self.run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=_json_default)

    def write_text(self, relative_path, content):
        path = self.run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            handle.write(content)

    def append_jsonl(self, relative_path, payload):
        path = self.run_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=_json_default))
            handle.write("\n")

    def log_dataset_summary(self, dataset, split="train", extra=None):
        summary = {
            "split": split,
            "length": len(dataset) if hasattr(dataset, "__len__") else None,
            "columns": list(getattr(dataset, "column_names", []) or []),
        }
        if extra:
            summary["extra"] = extra
        self.write_json("dataset_summary.json", summary)

    def log_reward_event(self, reward_name, request_payload, response_payload, scores, extra=None):
        self.append_jsonl(
            "reward_events.jsonl",
            {
                "timestamp_utc": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "reward_name": reward_name,
                "request": request_payload,
                "response": response_payload,
                "scores": scores,
                "extra": extra or {},
            },
        )

    def log_sample(self, sample_name, payload):
        self.append_jsonl("samples/samples.jsonl", {"sample_name": sample_name, **payload})

    def log_metrics(self, step, metrics):
        self.append_jsonl(
            "metrics.jsonl",
            {
                "timestamp_utc": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "step": step,
                "metrics": metrics,
            },
        )

    def log_checkpoint(self, step, checkpoint_path=None):
        self.append_jsonl(
            "checkpoints.jsonl",
            {
                "timestamp_utc": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "step": step,
                "checkpoint_path": checkpoint_path or str(self.output_dir),
            },
        )

    def finalize(self, status="completed", extra=None):
        self.write_json(
            "summary.json",
            {
                "status": status,
                "finished_at_utc": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
                "extra": extra or {},
            },
        )


def create_experiment_tracker(profile_name, profile_config, full_config):
    tracking = full_config.get("tracking", {})
    runs_dir = expand_path(
        tracking.get("runs_dir", "./runs"),
        base_dir=get_project_root(),
    )
    timestamp = _dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_profile = profile_name.replace("/", "_")
    run_dir = runs_dir / f"{timestamp}_{safe_profile}"
    tracker = ExperimentTracker(run_dir, profile_name, profile_config, full_config)
    tracker.initialize()
    return tracker


try:
    from transformers import TrainerCallback
except Exception:  # pragma: no cover - notebook environments may not have transformers imported yet.
    TrainerCallback = object


class ExperimentTrackingCallback(TrainerCallback):
    def __init__(self, tracker):
        self.tracker = tracker

    def on_train_begin(self, args, state, control, **kwargs):
        if hasattr(args, "to_dict"):
            self.tracker.write_json("trainer_args.json", args.to_dict())
        return control

    def on_log(self, args, state, control, logs=None, **kwargs):
        if logs:
            self.tracker.log_metrics(state.global_step, logs)
        return control

    def on_save(self, args, state, control, **kwargs):
        checkpoint_path = os.path.join(args.output_dir, f"checkpoint-{state.global_step}")
        self.tracker.log_checkpoint(state.global_step, checkpoint_path)
        return control

    def on_train_end(self, args, state, control, **kwargs):
        self.tracker.finalize("completed")
        return control
