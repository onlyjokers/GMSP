"""Client modules for WebSocket service interactions."""

from .websocket_client import WebSocketClientSender


def create_transport_client(transport_config: dict):
    """创建 WebSocket 客户端

    Args:
        transport_config: profile 中的 transport 配置字典

    Returns:
        WebSocketClientSender 实例
    """
    return WebSocketClientSender(
        relay_server=transport_config.get("relay_server", "ws://localhost:8080"),
        timeout=transport_config.get("timeout_ms", 15000),
    )
