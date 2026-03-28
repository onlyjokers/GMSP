#!/usr/bin/env python3
"""
WebSocket 中转服务器 - 部署在阿里云
连接 GMSP 训练服务器和本地 Blender 实例
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Optional
import websockets
from websockets.server import WebSocketServerProtocol

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

class RelayServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.trainer_clients: Dict[str, WebSocketServerProtocol] = {}
        self.blender_clients: Dict[str, WebSocketServerProtocol] = {}
        self.message_queue = asyncio.Queue()

    async def register_client(self, websocket: WebSocketServerProtocol):
        """客户端注册：第一条消息必须是身份标识"""
        try:
            # 等待客户端发送身份信息
            identity_msg = await asyncio.wait_for(
                websocket.recv(), timeout=10.0
            )
            identity = json.loads(identity_msg)

            client_type = identity.get("type")  # "trainer" or "blender"
            client_id = identity.get("id", f"{client_type}_{id(websocket)}")

            if client_type == "trainer":
                self.trainer_clients[client_id] = websocket
                logger.info(f"训练客户端已连接: {client_id}")
            elif client_type == "blender":
                self.blender_clients[client_id] = websocket
                logger.info(f"Blender 客户端已连接: {client_id}")
            else:
                await websocket.close(1008, "未知客户端类型")
                return None

            # 发送确认
            await websocket.send(json.dumps({
                "type": "registered",
                "client_id": client_id,
                "timestamp": datetime.now().isoformat()
            }))

            return client_type, client_id

        except asyncio.TimeoutError:
            logger.error("客户端注册超时")
            await websocket.close(1008, "注册超时")
            return None
        except Exception as e:
            logger.error(f"注册失败: {e}")
            await websocket.close(1011, str(e))
            return None

    async def handle_client(self, websocket: WebSocketServerProtocol):
        """处理单个客户端连接"""
        client_info = await self.register_client(websocket)
        if not client_info:
            return

        client_type, client_id = client_info

        try:
            async for message in websocket:
                # 转发消息
                if client_type == "trainer":
                    # 训练端发来的消息，转发给所有 Blender
                    await self.broadcast_to_blender(message, client_id)
                elif client_type == "blender":
                    # Blender 发来的消息，转发给所有训练端
                    await self.broadcast_to_trainer(message, client_id)

        except websockets.exceptions.ConnectionClosed:
            logger.info(f"客户端断开: {client_id}")
        except Exception as e:
            logger.error(f"处理客户端消息出错 {client_id}: {e}")
        finally:
            # 清理连接
            if client_type == "trainer":
                self.trainer_clients.pop(client_id, None)
            elif client_type == "blender":
                self.blender_clients.pop(client_id, None)
            logger.info(f"客户端已移除: {client_id}")

    async def broadcast_to_blender(self, message, sender_id: str):
        """转发消息给所有 Blender 客户端"""
        if not self.blender_clients:
            logger.warning(f"没有 Blender 客户端在线，消息丢弃")
            return

        # 添加发送者信息
        try:
            data = json.loads(message) if isinstance(message, str) else message
            data["_sender"] = sender_id
            message = json.dumps(data)
        except:
            pass  # 如果不是 JSON，直接转发

        dead_clients = []
        for client_id, ws in self.blender_clients.items():
            try:
                await ws.send(message)
                logger.debug(f"消息已转发到 Blender: {client_id}")
            except Exception as e:
                logger.error(f"转发失败 {client_id}: {e}")
                dead_clients.append(client_id)

        # 清理死连接
        for client_id in dead_clients:
            self.blender_clients.pop(client_id, None)

    async def broadcast_to_trainer(self, message, sender_id: str):
        """转发消息给所有训练客户端"""
        if not self.trainer_clients:
            logger.warning(f"没有训练客户端在线，消息丢弃")
            return

        # 添加发送者信息
        try:
            data = json.loads(message) if isinstance(message, str) else message
            data["_sender"] = sender_id
            message = json.dumps(data)
        except:
            pass

        dead_clients = []
        for client_id, ws in self.trainer_clients.items():
            try:
                await ws.send(message)
                logger.debug(f"消息已转发到训练端: {client_id}")
            except Exception as e:
                logger.error(f"转发失败 {client_id}: {e}")
                dead_clients.append(client_id)

        for client_id in dead_clients:
            self.trainer_clients.pop(client_id, None)

    async def start(self):
        """启动服务器"""
        logger.info(f"中转服务器启动: {self.host}:{self.port}")
        async with websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            max_size=100 * 1024 * 1024,  # 100MB 最大消息
            ping_interval=20,  # 20秒心跳
            ping_timeout=10
        ):
            await asyncio.Future()  # 永久运行


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GMSP WebSocket 中转服务器")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8080, help="监听端口")
    args = parser.parse_args()

    server = RelayServer(host=args.host, port=args.port)
    asyncio.run(server.start())
