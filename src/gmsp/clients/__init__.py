"""Client modules for Blender and GLSL service interactions."""

from .blender_client import ClientSender


def create_transport_client(transport_config: dict):
    """根据配置自动选择 ZeroMQ 或 WebSocket 客户端

    如果 transport_config 中配置了 relay_server（非空），使用 WebSocket 中转；
    否则使用 ZeroMQ 直连。两种客户端提供相同的接口：
        - connect() -> bool
        - send_materials(materials_json) -> dict
        - close()
        - 支持 with 语句

    Args:
        transport_config: profile 中的 transport 配置字典

    Returns:
        ClientSender 或 WebSocketClientSender 实例
    """
    relay_server = transport_config.get("relay_server")

    if relay_server:
        from .websocket_client import WebSocketClientSender
        return WebSocketClientSender(
            relay_server=relay_server,
            timeout=transport_config.get("timeout_ms", 15000),
        )
    else:
        return ClientSender(
            server_address=transport_config.get("server_address", "localhost"),
            port=transport_config.get("port", 5555),
            timeout=transport_config.get("timeout_ms", 15000),
            reverse_mode=transport_config.get("reverse_mode", False),
        )
