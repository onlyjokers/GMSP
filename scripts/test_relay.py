#!/usr/bin/env python3
"""
WebSocket 中转方案测试脚本
测试阿里云中转服务器的连通性和功能
"""
import asyncio
import json
import sys
import websockets
from datetime import datetime


async def test_trainer_client(relay_server: str):
    """测试训练端客户端"""
    print(f"\n[训练端] 连接到中转服务器: {relay_server}")

    try:
        async with websockets.connect(relay_server) as ws:
            # 注册
            await ws.send(json.dumps({
                "type": "trainer",
                "id": "test_trainer"
            }))

            # 等待确认
            response = await ws.recv()
            data = json.loads(response)
            print(f"[训练端] 注册响应: {data}")

            if data.get("type") != "registered":
                print("[训练端] ❌ 注册失败")
                return False

            print("[训练端] ✅ 注册成功")

            # 发送测试材质请求
            test_request = {
                "material_group": [
                    {
                        "id": 1,
                        "name": "test_material",
                        "code": "print('Hello from Blender')"
                    }
                ],
                "session_id": "test_session_001",
                "head": {
                    "input": "测试材质",
                    "taskid": "test_001",
                    "request": ["accuracy_rank"]
                },
                "timestamp": datetime.now().isoformat()
            }

            print(f"[训练端] 发送测试请求...")
            await ws.send(json.dumps(test_request))

            # 等待响应（最多 30 秒）
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=30.0)
                result = json.loads(response)
                print(f"[训练端] ✅ 收到响应: {result}")
                return True
            except asyncio.TimeoutError:
                print("[训练端] ⚠️  等待响应超时（可能没有 Blender 客户端在线）")
                return True  # 连接本身是成功的

    except Exception as e:
        print(f"[训练端] ❌ 错误: {e}")
        return False


async def test_blender_client(relay_server: str):
    """测试 Blender 端客户端"""
    print(f"\n[Blender] 连接到中转服务器: {relay_server}")

    try:
        async with websockets.connect(relay_server) as ws:
            # 注册
            await ws.send(json.dumps({
                "type": "blender",
                "id": "test_blender"
            }))

            # 等待确认
            response = await ws.recv()
            data = json.loads(response)
            print(f"[Blender] 注册响应: {data}")

            if data.get("type") != "registered":
                print("[Blender] ❌ 注册失败")
                return False

            print("[Blender] ✅ 注册成功")
            print("[Blender] 等待材质请求...")

            # 监听请求
            try:
                message = await asyncio.wait_for(ws.recv(), timeout=60.0)
                request = json.loads(message)
                print(f"[Blender] ✅ 收到请求: {request.get('session_id')}")

                # 模拟处理并返回结果
                response = {
                    "material_results": [
                        {
                            "id": 1,
                            "name": "test_material",
                            "status": True,
                            "accuracy_rank": 5,
                            "meaning_rank": 4
                        }
                    ],
                    "session_id": request.get("session_id"),
                    "taskid": request.get("head", {}).get("taskid")
                }

                await ws.send(json.dumps(response))
                print(f"[Blender] ✅ 已发送响应")
                return True

            except asyncio.TimeoutError:
                print("[Blender] ⚠️  等待请求超时（可能没有训练端发送请求）")
                return True

    except Exception as e:
        print(f"[Blender] ❌ 错误: {e}")
        return False


async def test_ping(relay_server: str):
    """测试服务器连通性"""
    print(f"\n[Ping] 测试连接: {relay_server}")

    try:
        async with websockets.connect(relay_server, open_timeout=5) as ws:
            print("[Ping] ✅ 连接成功")
            await ws.close()
            return True
    except Exception as e:
        print(f"[Ping] ❌ 连接失败: {e}")
        return False


async def main():
    if len(sys.argv) < 2:
        print("用法: python test_relay.py <中转服务器地址> [模式]")
        print("示例: python test_relay.py ws://阿里云IP:8080 trainer")
        print("模式: ping | trainer | blender | full")
        sys.exit(1)

    relay_server = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "ping"

    print("=" * 60)
    print("GMSP WebSocket 中转方案测试")
    print("=" * 60)

    if mode == "ping":
        success = await test_ping(relay_server)
    elif mode == "trainer":
        success = await test_trainer_client(relay_server)
    elif mode == "blender":
        success = await test_blender_client(relay_server)
    elif mode == "full":
        # 完整测试：先启动 Blender 监听，再发送训练请求
        print("\n[完整测试] 需要同时运行两个客户端")
        print("1. 在一个终端运行: python test_relay.py ws://IP:8080 blender")
        print("2. 在另一个终端运行: python test_relay.py ws://IP:8080 trainer")
        return
    else:
        print(f"未知模式: {mode}")
        sys.exit(1)

    print("\n" + "=" * 60)
    if success:
        print("✅ 测试通过")
    else:
        print("❌ 测试失败")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
