#!/usr/bin/env python3
"""GMSP 环境检查脚本 — 逐项检测依赖，缺失时报告而非崩溃"""

import sys

ALL_OK = True


def check(name, import_fn):
    """尝试导入模块，返回 (module_or_None, version_str)"""
    global ALL_OK
    try:
        mod = import_fn()
        ver = getattr(mod, "__version__", "已安装(版本未知)")
        print(f"  [OK] {name}: {ver}")
        return mod
    except ImportError as e:
        print(f"  [MISSING] {name}: {e}")
        ALL_OK = False
        return None
    except Exception as e:
        print(f"  [ERROR] {name}: {e}")
        ALL_OK = False
        return None


print("============== 依赖检查 ==============")
torch = check("torch", lambda: __import__("torch"))
check("triton", lambda: __import__("triton"))
check("xformers", lambda: __import__("xformers"))
check("unsloth", lambda: __import__("unsloth"))
check("trl", lambda: __import__("trl"))
check("transformers", lambda: __import__("transformers"))
check("datasets", lambda: __import__("datasets"))
check("peft", lambda: __import__("peft"))
check("accelerate", lambda: __import__("accelerate"))

print("\n============== CUDA / GPU ==============")
if torch is not None:
    if torch.cuda.is_available():
        print(f"  CUDA 可用: True")
        print(f"  CUDA 版本: {torch.version.cuda}")
        count = torch.cuda.device_count()
        print(f"  GPU 数量: {count}")
        for i in range(count):
            name = torch.cuda.get_device_name(i)
            mem = torch.cuda.get_device_properties(i).total_mem / (1024 ** 3)
            print(f"  GPU {i}: {name} ({mem:.1f} GB)")
        # 简单运算测试
        try:
            t = torch.tensor([1.0, 2.0, 3.0]).cuda()
            assert t.sum().item() == 6.0
            print(f"  GPU 张量运算: OK")
        except Exception as e:
            print(f"  GPU 张量运算: FAILED — {e}")
            ALL_OK = False
    else:
        print("  CUDA 可用: False")
        print("  [FAIL] 未检测到可用的 CUDA 设备")
        ALL_OK = False
else:
    print("  [SKIP] torch 未安装，无法检测 CUDA")

print("\n============== 结论 ==============")
if ALL_OK:
    print("  所有检查通过，环境就绪。")
else:
    print("  存在缺失或异常项，请根据上方输出修复后重试。")
    sys.exit(1)
