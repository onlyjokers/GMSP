#!/usr/bin/env python3
"""
GMSP 端到端网络测试脚本

发送 4 个简单的 bpy 材质代码到 Blender 端，等待返回结果。
用于验证 训练端 → 中转服务器 → Blender 端 的完整链路是否正常。

用法：
    python scripts/test_network.py
    python scripts/test_network.py --timeout 15
"""
import argparse
import sys
import time
from pathlib import Path

# Bootstrap src/
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from gmsp.config import load_gmsp_config, get_default_profile_name, get_profile
from gmsp.clients import create_transport_client

# 4 个简单的 Blender 材质代码，覆盖不同类型
TEST_MATERIALS = [
    {
        "id": 1,
        "name": "测试_红色材质",
        "code": """
import bpy

material = bpy.data.materials.new(name="测试_红色材质")
material.use_nodes = True
nodes = material.node_tree.nodes
links = material.node_tree.links

nodes.clear()

output_node = nodes.new(type='ShaderNodeOutputMaterial')
output_node.location = (300, 0)

bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
bsdf.location = (0, 0)
bsdf.inputs['Base Color'].default_value = (0.8, 0.1, 0.1, 1.0)

links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])
""",
    },
    {
        "id": 2,
        "name": "测试_蓝色金属",
        "code": """
import bpy

material = bpy.data.materials.new(name="测试_蓝色金属")
material.use_nodes = True
nodes = material.node_tree.nodes
links = material.node_tree.links

nodes.clear()

output_node = nodes.new(type='ShaderNodeOutputMaterial')
output_node.location = (300, 0)

bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
bsdf.location = (0, 0)
bsdf.inputs['Base Color'].default_value = (0.1, 0.2, 0.8, 1.0)
bsdf.inputs['Metallic'].default_value = 1.0
bsdf.inputs['Roughness'].default_value = 0.2

links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])
""",
    },
    {
        "id": 3,
        "name": "测试_绿色渐变",
        "code": """
import bpy

material = bpy.data.materials.new(name="测试_绿色渐变")
material.use_nodes = True
nodes = material.node_tree.nodes
links = material.node_tree.links

nodes.clear()

output_node = nodes.new(type='ShaderNodeOutputMaterial')
output_node.location = (600, 0)

bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
bsdf.location = (300, 0)

color_ramp = nodes.new(type='ShaderNodeValToRGB')
color_ramp.location = (0, 0)
color_ramp.color_ramp.elements[0].color = (0.0, 0.5, 0.0, 1.0)
color_ramp.color_ramp.elements[1].color = (0.8, 1.0, 0.2, 1.0)

tex_coord = nodes.new(type='ShaderNodeTexCoord')
tex_coord.location = (-300, 0)

links.new(tex_coord.outputs['Generated'], color_ramp.inputs['Fac'])
links.new(color_ramp.outputs['Color'], bsdf.inputs['Base Color'])
links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])
""",
    },
    {
        "id": 4,
        "name": "测试_透明玻璃",
        "code": """
import bpy

material = bpy.data.materials.new(name="测试_透明玻璃")
material.use_nodes = True
nodes = material.node_tree.nodes
links = material.node_tree.links

nodes.clear()

output_node = nodes.new(type='ShaderNodeOutputMaterial')
output_node.location = (300, 0)

bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
bsdf.location = (0, 0)
bsdf.inputs['Base Color'].default_value = (0.9, 0.95, 1.0, 1.0)
bsdf.inputs['Roughness'].default_value = 0.0
bsdf.inputs['IOR'].default_value = 1.45
bsdf.inputs['Alpha'].default_value = 0.1

links.new(bsdf.outputs['BSDF'], output_node.inputs['Surface'])
""",
    },
]


def main():
    parser = argparse.ArgumentParser(description="GMSP 端到端网络测试")
    parser.add_argument("--timeout", type=int, default=10, help="等待响应的超时时间（秒），默认 10")
    parser.add_argument("--profile", type=str, default=None, help="使用指定的 Profile 名称")
    args = parser.parse_args()

    print("=" * 60)
    print("GMSP 端到端网络测试")
    print("=" * 60)

    # 加载配置
    config = load_gmsp_config()
    profile_name = args.profile or get_default_profile_name(config)
    profile = get_profile(config, profile_name)
    transport_config = profile["transport"]
    relay_server = transport_config.get("relay_server", "ws://localhost:8080")

    print(f"\n配置信息:")
    print(f"  Profile: {profile_name}")
    print(f"  中转服务器: {relay_server}")
    print(f"  超时时间: {args.timeout}s")

    # 连接
    print(f"\n[1/3] 正在连接到中转服务器 {relay_server} ...")
    client = create_transport_client(transport_config)

    try:
        connected = client.connect()
        if not connected:
            print("\n连接失败！请检查：")
            print("  1. 中转服务器是否在运行")
            print("  2. configs/local.json 中的 relay_server 地址是否正确")
            print("  3. 防火墙是否放行了对应端口")
            sys.exit(1)
        print("  连接成功 ✓")
    except Exception as e:
        print(f"\n连接异常: {e}")
        sys.exit(1)

    # 发送测试材质
    print(f"\n[2/3] 正在发送 {len(TEST_MATERIALS)} 个测试材质到 Blender ...")
    for m in TEST_MATERIALS:
        print(f"  - {m['name']} (id={m['id']})")

    materials_payload = {
        "head": {
            "input": "网络测试",
            "taskid": "test_network",
            "request": [],
        },
        "outputs": TEST_MATERIALS,
    }

    start_time = time.time()
    try:
        # 临时调大超时
        original_timeout = client.timeout
        client.timeout = args.timeout * 1000
        result = client.send_materials(materials_payload)
        elapsed = time.time() - start_time
        client.timeout = original_timeout
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n发送失败（{elapsed:.1f}s）: {e}")
        print("\n请检查：")
        print("  1. Blender 端插件是否已启动并连接到中转服务器")
        print("  2. Blender 场景中是否有摄像机和网格对象")
        client.close()
        sys.exit(1)

    # 分析结果
    print(f"\n[3/3] 收到响应（耗时 {elapsed:.1f}s）")
    print("-" * 60)

    if isinstance(result, list):
        # 错误格式
        success_count = sum(1 for r in result if r.get("status"))
        fail_count = len(result) - success_count
        print(f"\n结果: {success_count} 成功, {fail_count} 失败")
        for r in result:
            status = "✓" if r.get("status") else "✗"
            name = r.get("name", "未知")
            err = r.get("error_msg", "")
            print(f"  {status} {name}" + (f" — {err}" if err else ""))
    elif isinstance(result, dict):
        # 可能是字段映射格式或包含 results 的格式
        results = result.get("results", [])
        if results:
            success_count = sum(1 for r in results if r.get("status"))
            fail_count = len(results) - success_count
            print(f"\n结果: {success_count} 成功, {fail_count} 失败")
            for r in results:
                status = "✓" if r.get("status") else "✗"
                name = r.get("name", "未知")
                err = r.get("error_msg", "")
                acc = r.get("accuracy_rank", "-")
                mean = r.get("meaning_rank", "-")
                print(f"  {status} {name} (准确度排名={acc}, 意义排名={mean})" + (f" — {err}" if err else ""))
        else:
            print(f"\n返回数据: {json.dumps(result, ensure_ascii=False, indent=2)[:500]}")

        accuracy_raw = result.get("accuracy_raw")
        meaning_raw = result.get("meaning_raw")
        if accuracy_raw:
            print(f"\n准确度排序原始结果: {accuracy_raw[:200]}")
        if meaning_raw:
            print(f"意义排序原始结果: {meaning_raw[:200]}")
    else:
        print(f"\n未知响应格式: {type(result)}")
        print(str(result)[:500])

    print("\n" + "=" * 60)
    if elapsed < args.timeout:
        print("网络测试通过 ✓ 训练端到 Blender 端的链路正常工作")
    else:
        print("网络测试超时 ✗ 请检查 Blender 端是否正常运行")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    import json
    main()
