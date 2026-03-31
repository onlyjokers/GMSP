#!/usr/bin/env python3
"""GMSP 环境检查脚本 — 逐项检测依赖，缺失时报告而非崩溃"""

import sys
from pathlib import Path

# 添加 src 到路径以便导入 gmsp 模块
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

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
            mem = torch.cuda.get_device_properties(i).total_memory / (1024 ** 3)
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

print("\n============== 网络连接检查 ==============")
try:
    from gmsp.config import load_gmsp_config, get_default_profile_name, get_profile
    import socket
    from urllib.parse import urlparse

    config = load_gmsp_config()
    profile_name = get_default_profile_name(config)
    profile = get_profile(config, profile_name)

    print(f"  当前配置 profile: {profile_name}")

    # 获取 relay_server 配置
    relay_server = profile.get("transport", {}).get("relay_server", "")
    if relay_server:
        print(f"  Relay Server: {relay_server}")

        # 解析 WebSocket URL
        parsed = urlparse(relay_server)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8080

        # 测试 TCP 连接
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((host, port))
            sock.close()

            if result == 0:
                print(f"  连接测试 ({host}:{port}): OK")
            else:
                print(f"  连接测试 ({host}:{port}): FAILED (无法连接)")
                print(f"  [WARNING] 无法连接到 relay server，训练时可能无法与 Blender 通信")
                # 不设置 ALL_OK = False，因为这可能只是 Blender 端未启动
        except socket.gaierror:
            print(f"  连接测试 ({host}:{port}): FAILED (域名解析失败)")
            print(f"  [WARNING] 无法解析主机名，请检查网络配置")
        except Exception as e:
            print(f"  连接测试 ({host}:{port}): ERROR ({e})")
            print(f"  [WARNING] 连接测试出错")
    else:
        print("  [WARNING] 配置中未找到 relay_server")

except ImportError as e:
    print(f"  [SKIP] 无法导入配置模块: {e}")
except Exception as e:
    print(f"  [ERROR] 网络检查失败: {e}")
    ALL_OK = False

print("\n============== 结论 ==============")
if ALL_OK:
    print("  所有检查通过，环境就绪。")
else:
    print("  存在缺失或异常项，请根据上方输出修复后重试。")
    sys.exit(1)
