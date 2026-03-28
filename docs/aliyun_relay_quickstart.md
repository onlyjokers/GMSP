# 阿里云中转方案 - 快速指南

## 项目结构

GMSP 生态系统现在分为三个独立项目：

```
/home/GSMP/
├── GMSP/              # 训练端（本项目）
├── GMSPforBlender/    # Blender 插件
└── GMSPforServer/     # 阿里云中转服务器 ⭐
```

---

## 快速开始

### 1. 部署中转服务器

详见：[GMSPforServer/README.md](../../GMSPforServer/README.md)

```bash
# 在阿里云服务器
cd /root
# 上传 GMSPforServer 代码
pip3 install -r GMSPforServer/requirements.txt
python3 GMSPforServer/src/relay_server.py --host 0.0.0.0 --port 8080
```

### 2. 配置 GMSP 训练端

编辑 `configs/local.json`：

```json
{
  "profiles": {
    "blenderllm_qwen3_5_4b": {
      "transport": {
        "type": "websocket",
        "relay_server": "ws://你的阿里云IP:8080",
        "client_id": "gmsp_trainer"
      }
    }
  }
}
```

### 3. 使用 WebSocket 客户端

```python
import asyncio
from gmsp.clients.websocket_client import GMSPWebSocketClient

async def main():
    client = GMSPWebSocketClient(
        relay_server="ws://阿里云IP:8080",
        client_id="gmsp_trainer"
    )

    await client.connect()

    result = await client.send_material_request(
        material_group=[{
            "id": 1,
            "name": "test_material",
            "code": "bpy.data.materials.new('Test')"
        }],
        session_id="session_001",
        head={"input": "测试", "taskid": "001"}
    )

    print(result)
    await client.close()

asyncio.run(main())
```

---

## 架构

```
云端 GMSP (训练服务器)
    ↓ WebSocket
    ↓
阿里云中转服务器 (ws://IP:8080)
    ↓ WebSocket
    ↓
本地 Blender (局域网)
```

**优势：**
- ✅ 一个地址：`ws://阿里云IP:8080`
- ✅ 零配置：无需端口映射
- ✅ 大文件：支持 100MB
- ✅ 自动重连

---

## 测试

```bash
# 测试连通性
cd /home/GSMP/GMSPforServer
python3 scripts/test_connection.py ws://阿里云IP:8080

# 完整测试（需要两个终端）
# 终端 1
python3 scripts/test_blender.py ws://阿里云IP:8080

# 终端 2
python3 scripts/test_trainer.py ws://阿里云IP:8080
```

---

## 详细文档

- [GMSPforServer 部署指南](../../GMSPforServer/docs/deployment.md)
- [GMSPforServer README](../../GMSPforServer/README.md)

---

## 成本

**阿里云 ECS：**
- 最低配置：1核2G，5Mbps
- 约 ¥50-100/月

---

## 对比 ZeroMQ 方案

| 特性 | ZeroMQ | WebSocket 中转 |
|------|--------|----------------|
| 配置 | 中等 | 极简 ⭐ |
| NAT 穿透 | 需要反向连接 | 自动 ⭐ |
| 性能 | 高 ⭐ | 中等 |
| 成本 | 免费 ⭐ | ¥50-100/月 |

**推荐场景：**
- 本地在 NAT 后 → WebSocket 中转 ⭐
- 双方都有公网 IP → ZeroMQ 直连
