# 阿里云中转方案部署指南

## 架构概览

```
云端 GMSP (训练服务器)
    ↓ WebSocket (ws://阿里云IP:8080)
    ↓
阿里云中转服务器 (公网 IP)
    ↓ WebSocket
    ↓
本地 Blender (局域网)
```

**核心优势：**
- ✅ 一个地址：双方都连接 `ws://阿里云IP:8080`
- ✅ 双向通信：实时消息转发
- ✅ 大文件支持：最大 100MB 单条消息
- ✅ 自动重连：断线自动恢复
- ✅ 简单部署：单个 Python 脚本

---

## 第一步：阿里云服务器部署

### 1.1 环境准备

```bash
# SSH 登录阿里云服务器
ssh root@你的阿里云IP

# 安装 Python 3.8+
apt update && apt install python3 python3-pip -y

# 安装依赖
pip3 install websockets
```

### 1.2 上传中转服务器代码

将 `scripts/relay_server.py` 上传到阿里云：

```bash
# 在本地执行
scp scripts/relay_server.py root@阿里云IP:/root/
```

### 1.3 启动中转服务器

```bash
# 在阿里云服务器执行
cd /root
python3 relay_server.py --host 0.0.0.0 --port 8080

# 或者使用 nohup 后台运行
nohup python3 relay_server.py --host 0.0.0.0 --port 8080 > relay.log 2>&1 &
```

### 1.4 配置防火墙

**阿里云控制台：**
1. 进入 ECS 实例 → 安全组
2. 添加入站规则：
   - 端口：8080
   - 协议：TCP
   - 授权对象：0.0.0.0/0

**服务器防火墙（如果有）：**
```bash
# Ubuntu/Debian
ufw allow 8080/tcp

# CentOS/RHEL
firewall-cmd --permanent --add-port=8080/tcp
firewall-cmd --reload
```

### 1.5 验证服务器运行

```bash
# 查看日志
tail -f relay.log

# 测试端口
netstat -tlnp | grep 8080
```

---

## 第二步：GMSP 训练端配置

### 2.1 安装依赖

```bash
pip install websockets
```

### 2.2 修改配置文件

编辑 `configs/local.json`：

```json
{
  "profiles": {
    "blenderllm_qwen3_5_4b": {
      "transport": {
        "type": "websocket",
        "relay_server": "ws://你的阿里云IP:8080",
        "client_id": "gmsp_trainer_1"
      }
    }
  }
}
```

### 2.3 使用示例

```python
import asyncio
from gmsp.clients.websocket_client import GMSPWebSocketClient

async def main():
    # 创建客户端
    client = GMSPWebSocketClient(
        relay_server="ws://你的阿里云IP:8080",
        client_id="gmsp_trainer"
    )

    # 连接
    await client.connect()

    # 发送材质请求
    result = await client.send_material_request(
        material_group=[
            {
                "id": 1,
                "name": "test_material",
                "code": "bpy.data.materials.new('TestMat')"
            }
        ],
        session_id="test_session_001",
        head={
            "input": "创建一个测试材质",
            "taskid": "task_001",
            "request": ["accuracy_rank", "meaning_rank"]
        },
        timeout=60.0
    )

    print(f"结果: {result}")
    await client.close()

asyncio.run(main())
```

---

## 第三步：Blender 端配置

### 3.1 安装依赖

在 Blender 的 Python 环境中：

```bash
# 找到 Blender 的 Python 路径
# Linux: ~/.config/blender/3.x/python/bin/python
# Windows: C:\Program Files\Blender Foundation\Blender 3.x\3.x\python\bin\python.exe

# 安装 websockets
/path/to/blender/python -m pip install websockets
```

### 3.2 修改 Blender 插件

在 GMSPforBlender 插件中添加 WebSocket 模式：

编辑 `webTrans/ui.py`，添加连接模式选择：

```python
# 添加属性
bpy.types.Scene.webtrans_mode = bpy.props.EnumProperty(
    name="连接模式",
    items=[
        ('ZMQ', 'ZeroMQ', '传统 ZMQ 模式'),
        ('WEBSOCKET', 'WebSocket', 'WebSocket 中转模式')
    ],
    default='ZMQ'
)

bpy.types.Scene.webtrans_relay_server = bpy.props.StringProperty(
    name="中转服务器",
    default="ws://阿里云IP:8080"
)
```

### 3.3 启动 Blender 客户端

在 Blender 中：
1. 打开 GMSPforBlender 插件面板
2. 选择 "WebSocket" 模式
3. 填入中转服务器地址：`ws://你的阿里云IP:8080`
4. 点击 "启动连接"

---

## 性能优化

### 大文件传输优化

如果需要传输超大文件（如高分辨率渲染图），建议：

**方案 A：分块传输**
```python
# 将大文件分成多个小块
chunk_size = 10 * 1024 * 1024  # 10MB
for i in range(0, len(data), chunk_size):
    chunk = data[i:i+chunk_size]
    await client.send(chunk)
```

**方案 B：使用对象存储**
```python
# 大文件上传到阿里云 OSS
# 只传输下载链接
result_url = upload_to_oss(image_data)
await client.send({"image_url": result_url})
```

### 消息压缩

对于大量文本数据，启用压缩：

```python
import gzip
import base64

# 发送前压缩
compressed = gzip.compress(json.dumps(data).encode())
encoded = base64.b64encode(compressed).decode()
await websocket.send(json.dumps({"compressed": encoded}))

# 接收后解压
decoded = base64.b64decode(data["compressed"])
decompressed = gzip.decompress(decoded)
original = json.loads(decompressed)
```

---

## 监控和维护

### 查看连接状态

```bash
# 在阿里云服务器
tail -f relay.log | grep "已连接"
```

### 重启服务

```bash
# 找到进程
ps aux | grep relay_server

# 杀死进程
kill <PID>

# 重新启动
nohup python3 relay_server.py --host 0.0.0.0 --port 8080 > relay.log 2>&1 &
```

### 设置开机自启

创建 systemd 服务：

```bash
# 创建服务文件
cat > /etc/systemd/system/gmsp-relay.service << EOF
[Unit]
Description=GMSP WebSocket Relay Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root
ExecStart=/usr/bin/python3 /root/relay_server.py --host 0.0.0.0 --port 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 启用服务
systemctl enable gmsp-relay
systemctl start gmsp-relay

# 查看状态
systemctl status gmsp-relay
```

---

## 故障排查

### 问题 1：连接超时

**检查：**
```bash
# 测试端口连通性
telnet 阿里云IP 8080

# 检查防火墙
iptables -L -n | grep 8080
```

### 问题 2：消息丢失

**解决：**
- 检查中转服务器日志
- 确认双方都已连接
- 增加超时时间

### 问题 3：传输速度慢

**优化：**
- 启用消息压缩
- 使用 msgpack 替代 JSON
- 大文件使用 OSS

---

## 成本估算

**阿里云 ECS：**
- 最低配置：1核2G，5Mbps 带宽
- 价格：约 ¥50-100/月
- 适用场景：单用户，中等流量

**带宽需求：**
- 每次材质请求：~100KB
- 每次渲染结果：~1-5MB
- 建议带宽：5Mbps 起

---

## 下一步

1. 部署阿里云中转服务器
2. 测试连通性
3. 修改 GMSP 和 Blender 代码
4. 运行完整流程测试

需要我帮你生成测试脚本或进一步优化吗？
