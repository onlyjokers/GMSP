from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from gmsp.training import rl_training


class DummyConfig:
    def __init__(
        self,
        *,
        use_vllm=None,
        vllm_mode=None,
        vllm_gpu_memory_utilization=None,
        generation_batch_size=None,
        max_prompt_length=None,
        max_completion_length=None,
        output_dir=None,
        **kwargs,
    ):
        self.kwargs = {
            "use_vllm": use_vllm,
            "vllm_mode": vllm_mode,
            "vllm_gpu_memory_utilization": vllm_gpu_memory_utilization,
            "generation_batch_size": generation_batch_size,
            "max_prompt_length": max_prompt_length,
            "max_completion_length": max_completion_length,
            "output_dir": output_dir,
            **kwargs,
        }


class RLTrainingTests(unittest.TestCase):
    def test_build_training_args_enables_colocated_vllm_defaults(self):
        training_config = {
            "algorithm": "dapo",
            "learning_rate": 5e-6,
            "adam_beta1": 0.9,
            "adam_beta2": 0.99,
            "weight_decay": 0.1,
            "warmup_steps": 12,
            "lr_scheduler_type": "cosine",
            "optim": "adamw_torch_fused",
            "logging_steps": 1,
            "per_device_train_batch_size": 6,
            "gradient_accumulation_steps": 1,
            "num_generations": 6,
            "max_steps": 1200,
            "save_steps": 200,
            "max_grad_norm": 0.1,
            "report_to": "tensorboard",
            "use_vllm": True,
            "vllm_gpu_memory_utilization": 0.25,
        }

        with mock.patch.object(
            rl_training, "_load_trl_classes", return_value=(DummyConfig, object())
        ):
            training_args = rl_training.build_training_args(
                training_config,
                max_prompt_length=256,
                max_seq_length=2048,
                output_dir="/tmp/out",
            )

        self.assertTrue(training_args.kwargs["use_vllm"])
        self.assertEqual(training_args.kwargs["vllm_mode"], "colocate")
        self.assertEqual(training_args.kwargs["vllm_gpu_memory_utilization"], 0.25)
        self.assertEqual(training_args.kwargs["generation_batch_size"], 6)

    def test_describe_training_recipe_reports_vllm_settings(self):
        training_config = {
            "algorithm": "dapo",
            "num_generations": 6,
            "per_device_train_batch_size": 6,
            "use_vllm": True,
            "vllm_mode": "server",
            "vllm_tensor_parallel_size": 2,
        }

        recipe = rl_training.describe_training_recipe(
            training_config,
            max_prompt_length=256,
            max_completion_length=1792,
            reward_functions=[lambda **_: [1.0]],
        )

        self.assertTrue(recipe["use_vllm"])
        self.assertEqual(recipe["vllm_mode"], "server")
        self.assertEqual(recipe["vllm_tensor_parallel_size"], 2)
        self.assertEqual(recipe["generation_batch_size"], 6)


if __name__ == "__main__":
    unittest.main()
