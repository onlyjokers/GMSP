#!/usr/bin/env python3
"""
GMSP 训练端 WebSocket 客户端
连接到阿里云中转服务器

提供两个类：
- GMSPWebSocketClient: 异步客户端
- WebSocketClientSender: 同步包装，接口与 ClientSender (ZeroMQ) 一致
"""
import asyncio
import json
import threading
import websockets
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class GMSPWebSocketClient:
    def __init__(
        self,
        relay_server: str,
        client_id: str = "gmsp_trainer",
        auto_reconnect: bool = True
    ):
        """
        Args:
            relay_server: 中转服务器地址，如 "ws://阿里云IP:8080"
            client_id: 客户端标识
            auto_reconnect: 是否自动重连
        """
        self.relay_server = relay_server
        self.client_id = client_id
        self.auto_reconnect = auto_reconnect
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.response_futures: Dict[str, asyncio.Future] = {}

    async def connect(self):
        """连接到中转服务器"""
        try:
            self.websocket = await websockets.connect(
                self.relay_server,
                max_size=100 * 1024 * 1024,  # 100MB
                ping_interval=20,
                ping_timeout=10
            )

            # 发送身份注册
            await self.websocket.send(json.dumps({
                "type": "trainer",
                "id": self.client_id
            }))

            # 等待确认
            response = await self.websocket.recv()
            data = json.loads(response)

            if data.get("type") == "registered":
                self.connected = True
                logger.info(f"已连接到中转服务器: {self.relay_server}")
                # 启动接收循环
                asyncio.create_task(self._receive_loop())
                return True
            else:
                logger.error(f"注册失败: {data}")
                return False

        except Exception as e:
            logger.error(f"连接失败: {e}")
            if self.auto_reconnect:
                await asyncio.sleep(5)
                return await self.connect()
            return False

    async def _receive_loop(self):
        """接收消息循环"""
        try:
            async for message in self.websocket:
                await self._handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            logger.warning("连接已关闭")
            self.connected = False
            if self.auto_reconnect:
                await asyncio.sleep(5)
                await self.connect()
        except Exception as e:
            logger.error(f"接收消息出错: {e}")

    async def _handle_message(self, message: str):
        """处理收到的消息"""
        try:
            data = json.loads(message)
            # 移除中转服务器注入的 _sender 字段
            data.pop("_sender", None)

            session_id = data.get("session_id")

            if session_id and session_id in self.response_futures:
                future = self.response_futures.pop(session_id)
                if not future.done():
                    future.set_result(data)
            else:
                logger.debug(f"收到消息: {data}")

        except Exception as e:
            logger.error(f"处理消息出错: {e}")

    async def send_material_request(
        self,
        material_group: list,
        session_id: str,
        head: dict,
        timeout: float = 60.0
    ) -> dict:
        """
        发送材质生成请求

        Args:
            material_group: 材质列表
            session_id: 会话ID
            head: 请求头信息
            timeout: 超时时间（秒）

        Returns:
            Blender 返回的结果（字段映射格式）
        """
        if not self.connected:
            raise ConnectionError("未连接到服务器")

        # 构造请求
        request = {
            "material_group": material_group,
            "session_id": session_id,
            "head": head,
        }

        # 创建响应 Future
        future = asyncio.Future()
        self.response_futures[session_id] = future

        # 发送请求
        await self.websocket.send(json.dumps(request))
        logger.info(f"已发送材质请求: {session_id}")

        # 等待响应
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            self.response_futures.pop(session_id, None)
            raise TimeoutError(f"请求超时: {session_id}")

    async def close(self):
        """关闭连接"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            logger.info("连接已关闭")


class WebSocketClientSender:
    """同步包装类，接口与 ClientSender (ZeroMQ) 一致

    用法与 ClientSender 完全相同：
        client = WebSocketClientSender(relay_server="ws://IP:8080")
        client.connect()
        results = client.send_materials(materials_json)
        client.close()

    也支持 with 语句：
        with WebSocketClientSender("ws://IP:8080") as client:
            results = client.send_materials(materials_json)
    """

    def __init__(
        self,
        relay_server: str,
        client_id: str = "gmsp_trainer",
        timeout: int = 60000,
        max_retries: int = 5,
        retry_delay: int = 1,
    ):
        """
        Args:
            relay_server: 中转服务器地址，如 "ws://阿里云IP:8080"
            client_id: 客户端标识
            timeout: 超时时间（毫秒）
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
        """
        self.relay_server = relay_server
        self.client_id = client_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.connected = False

        self._async_client: Optional[GMSPWebSocketClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

    def _ensure_loop(self):
        """确保后台事件循环在运行"""
        if self._loop is not None and self._loop.is_running():
            return
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    def _run_async(self, coro):
        """在后台事件循环中运行协程并等待结果"""
        self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        timeout_sec = self.timeout / 1000.0
        return future.result(timeout=timeout_sec)

    def connect(self) -> bool:
        """连接到中转服务器"""
        if self.connected and self._async_client:
            return True

        try:
            self._ensure_loop()
            self._async_client = GMSPWebSocketClient(
                relay_server=self.relay_server,
                client_id=self.client_id,
                auto_reconnect=False,
            )
            result = self._run_async(self._async_client.connect())
            self.connected = result
            if result:
                print(f"已连接到中转服务器 {self.relay_server}")
            else:
                print(f"无法连接到中转服务器 {self.relay_server}")
            return result
        except Exception as e:
            self.connected = False
            print(f"连接中转服务器时出错: {e}")
            return False

    def close(self):
        """关闭连接"""
        if self._async_client:
            try:
                self._run_async(self._async_client.close())
            except Exception:
                pass
        self.connected = False
        self._async_client = None

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._loop:
            self._loop.close()
            self._loop = None
        print("连接已关闭")

    def send_materials(self, materials_json) -> dict:
        """发送材质数据，接口与 ClientSender.send_materials() 一致

        Args:
            materials_json: 包含材质数据的字典或列表

        Returns:
            dict: 字段映射格式的结果（与 ZeroMQ 路径一致）
        """
        import time
        import uuid

        # 解析材质数据
        if isinstance(materials_json, dict):
            data = materials_json.copy()
            material_list = data.get('outputs', data.get('material_group', []))
        else:
            material_list = materials_json
            data = {"outputs": material_list}

        # 验证
        for idx, material in enumerate(material_list):
            if not isinstance(material, dict) or "name" not in material or "code" not in material:
                return [{'status': False, 'error_msg': f"材质 #{idx+1} 格式错误：缺少name或code字段"}]

        # 确保已连接
        if not self.connected:
            retry_count = 0
            while retry_count < self.max_retries:
                if self.connect():
                    break
                retry_count += 1
                if retry_count < self.max_retries:
                    time.sleep(self.retry_delay)
            if not self.connected:
                return {'status': {}, 'error_msg': {m.get('name', ''): f"经过 {self.max_retries} 次尝试后仍无法连接" for m in material_list}}

        # 构造请求
        head = data.get("head", {})
        session_id = data.get("session_id") or uuid.uuid4().hex[:8]

        # 发送并等待响应
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                result = self._run_async(
                    self._async_client.send_material_request(
                        material_group=material_list,
                        session_id=session_id,
                        head=head,
                        timeout=self.timeout / 1000.0,
                    )
                )
                if result:
                    return result
                retry_count += 1
                time.sleep(self.retry_delay)
            except Exception as e:
                print(f"发送材质时出错: {e}")
                retry_count += 1
                if retry_count < self.max_retries:
                    time.sleep(self.retry_delay)
                    # 尝试重连
                    self.close()
                    self.connect()

        return {'status': {}, 'error_msg': {m.get('name', ''): "多次尝试后仍无法获取响应" for m in material_list}}

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
