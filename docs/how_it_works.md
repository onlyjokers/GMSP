# GMSP 项目运行原理详解

## 一、整体架构

GMSP 是一个用强化学习训练 LLM 生成 Blender 材质的系统。整个系统由三个独立进程组成：

```
┌─────────────────────┐        ┌──────────────────────┐        ┌─────────────────────┐
│   训练服务器（GPU）   │        │  中转服务器（阿里云）  │        │  本地 Blender 实例   │
│                     │        │                      │        │                     │
│  gmsp_main.ipynb    │◄──────►│  relay_server.py     │◄──────►│  GMSPforBlender     │
│  GRPOTrainer        │  WS    │  :8080               │  WS    │  插件               │
│  WebSocketClient    │        │                      │        │  BlenderWSClient    │
└─────────────────────┘        └──────────────────────┘        └─────────────────────┘
         │                                                               │
         │ 生成材质代码                                              执行代码 + 渲染
         │ 等待奖励信号                                              调用 GPT-4.1-mini
         │                                                          返回排名结果
         ▼
    DAPO 策略更新
```

**为什么需要中转服务器？**
训练服务器在云端，Blender 在本地（NAT 后面，没有公网 IP）。两端都主动连接到中转服务器，由中转服务器负责消息路由。

---

## 二、启动顺序

正确的启动顺序非常重要：

```
1. 启动中转服务器（阿里云）
   python scripts/relay_server.py

2. 启动 Blender，加载 GMSPforBlender 插件
   在 UI 面板中填入中转服务器地址，点击"启动服务"

3. 在训练服务器上运行 notebooks/gmsp_main.ipynb
```

---

## 三、中转服务器（relay_server.py）

**文件**：`scripts/relay_server.py`

中转服务器是一个纯粹的消息路由器，不理解消息内容，只负责转发。

### 连接注册流程

每个客户端连接后，第一条消息必须是身份注册：

```json
// 训练端发送
{"type": "trainer", "id": "gmsp_trainer"}

// Blender 端发送
{"type": "blender", "id": "blender_local"}
```

服务器回复确认：
```json
{"type": "registered", "client_id": "...", "timestamp": "..."}
```

### 消息路由规则

- 训练端发来的消息 → 广播给**所有** Blender 客户端
- Blender 端发来的消息 → 广播给**所有**训练客户端
- 转发时自动注入 `_sender` 字段标识来源

### 关键参数

- 监听地址：`0.0.0.0:8080`
- 最大消息：100MB（材质代码 + 渲染图片）
- 心跳间隔：20 秒

---

## 四、训练端（gmsp_main.ipynb）

### 4.1 初始化（Cell 0-4）

```python
# 1. 自动找到项目根目录，把 src/ 加入 sys.path
# 2. 加载配置
gmsp_config = load_gmsp_config()
profile = get_profile(gmsp_config, default_profile_name)

# 3. 创建实验追踪器（在 runs/ 下建目录）
run_tracker = create_experiment_tracker(...)

# 4. 创建 WebSocket 客户端（此时还未连接）
client = create_transport_client(transport_config)

# 5. 加载模型（Unsloth 加速，8bit 量化）
model, tokenizer = FastModel.from_pretrained(
    model_name=model_config["model_name"],  # ./models/qwen3.5-9b
    load_in_8bit=True,
    ...
)

# 6. 应用 LoRA
model = FastModel.get_peft_model(model, r=lora_rank, ...)
```

### 4.2 数据集构造（Cell 7-9）

系统提示词要求模型用特定格式回答：

```
你是一个 Blender 的材质生成器...
请将思考过程放在 <think> 和 </think> 之间。
然后，请在 <code> 和 </code> 之间提供你的答案。
```

数据集由三个难度等级的材质描述构成：

| 等级 | 数量 | 示例 |
|---|---|---|
| Level 1 | ~60 条 | "红色的材质"、"蓝色到黄色的渐变材质" |
| Level 2 | 20 条 | "红色的金属材质：表面光滑，金属光泽突出..." |
| Level 3 | 10 条 | "红色的拉丝金属材质：具有拉丝效果，表面有细微划痕..." |

每条描述与 ~26 种用户前缀变体组合（"帮我生成"、"做这个材质"、""等），最终生成约 **2340 条训练样本**。

每条样本格式：
```python
{
    "prompt": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "帮我生成这个：红色的材质"},
    ],
    "taskid": "uuid...",
    "goal": "红色的材质",
}
```

### 4.3 奖励函数（Cell 11-18）

共 5 个奖励函数，分两类：

#### 格式奖励（本地计算，不需要 Blender）

**① match_format_exactly**（严格格式，+3.0 分）
```python
# 正则匹配：必须有且仅有一对 <think>...</think><code>...</code>
if match_format.search(response) is not None:
    score += 3.0
```

**② match_format_approximately**（弱格式，±0.5 分/标签）
```python
# 每个标签出现恰好 1 次 → +0.5，否则 → -0.5
# 4 个标签：<think> </think> <code> </code>
# 最高 +2.0，最低 -2.0
```

#### 渲染奖励（需要发送到 Blender）

三个函数（accuracy_reward、meaning_reward、error_check）的流程完全相同：

```
1. 从每个 completion 中提取 <code>...</code> 内的 Python 代码
2. 构造材质请求包：
   {
     "head": {"input": "红色的材质", "taskid": "uuid..."},
     "outputs": [
       {"name": "M1", "code": "import bpy\n..."},
       {"name": "M2", "code": "import bpy\n..."},
       ...  # num_generations 个
     ]
   }
3. 调用 client.send_materials(materials) → 等待 Blender 返回
4. 从返回结果中取对应字段（accuracy_rank / meaning_rank / status）
5. 归一化为 [0, WEIGHT] 范围的奖励分数
```

**③ accuracy_reward**（权重 2）
- 取 `accuracy_rank` 字段：排名越靠前（数字越小）→ 奖励越高
- 归一化：`score = (max_rank - rank + 1)` 后线性归一化到 `[0, 2]`

**④ meaning_reward**（权重 1）
- 取 `meaning_rank` 字段，同上归一化到 `[0, 1]`

**⑤ error_check**（权重 2）
- 取 `status` 字段：代码执行成功 → 2.0，失败 → 0.0
- 如果所有 completion 结果相同（全成功或全失败），奖励归零（无梯度信号）

**⑥ soft_overlong_punishment**（自动添加）
- 补全长度超过 `max_completion_length * (1 - 0.2)` 时开始线性惩罚
- 超过 `max_completion_length` 时惩罚 -1.0

### 4.4 训练循环（Cell 20-22）

```python
# 构建 DAPO 训练参数
training_args = build_training_args(training_config, ...)

# 组合奖励函数（5个基础 + 1个超长惩罚）
reward_funcs = build_reward_functions(base_reward_funcs, training_config, ...)

# 启动 GRPOTrainer
trainer = GRPOTrainer(
    model=model,
    reward_funcs=reward_funcs,
    callbacks=[tracking_callback],  # 自动记录 metrics
    args=training_args,
    train_dataset=final_dataset,
)
trainer.train()
```

**每一个训练步骤的内部流程：**

```
Step N:
  1. 从 final_dataset 采样 per_device_train_batch_size(2) 个 prompt
  2. 对每个 prompt 生成 num_generations(4) 个补全
     → 本步共 2×4=8 个补全
  3. 对 8 个补全分别计算 6 个奖励函数
     → 格式奖励：本地立即计算
     → 渲染奖励：打包发送到 Blender，等待返回（最多 15s）
  4. 汇总奖励分数
  5. DAPO 策略梯度更新
     - clip 范围：epsilon=0.2 ~ epsilon_high=0.28
     - beta=0（不使用 KL 惩罚）
     - loss_type="dapo"
  6. 记录 metrics 到 TensorBoard 和 metrics.jsonl
```

---

## 五、Blender 端（GMSPforBlender 插件）

### 5.1 连接建立

用户在 Blender UI 中点击"启动服务"后：

```python
# ui.py → NTPStartReceiverOperator.execute()
start_websocket_client(relay_url)
# → 创建 BlenderWebSocketClient 实例
# → 在后台线程中启动 asyncio 事件循环
# → 连接到中转服务器，注册为 "blender" 类型
# → 进入监听循环，等待训练端发来的材质请求
```

### 5.2 处理材质请求

收到训练端的材质请求后（`websocket_client.py`）：

```python
async def _handle_material_request(self, message):
    data = json.loads(message)
    material_group = data["outputs"]  # 4 个材质

    # 在线程池中调用 MaterialProcessor（避免阻塞 asyncio）
    proc_output = await run_in_executor(
        self._processor.process_material_group, material_group
    )

    # 构造响应并发回
    response = {
        "session_id": session_id,
        "accuracy_rank": {"M1": 2, "M2": 1, "M3": 4, "M4": 3},
        "meaning_rank":  {"M1": 1, "M2": 3, "M3": 2, "M4": 4},
        "status":        {"M1": True, "M2": True, "M3": False, "M4": True},
        "error_msg":     {"M1": "", "M2": "", "M3": "SyntaxError...", "M4": ""},
    }
    await self.websocket.send(json.dumps(response))
```

### 5.3 MaterialProcessor 处理流程

**文件**：`webTrans/material_processor.py`

```
对每个材质（共 num_generations 个）：
  1. AST 安全校验
     - 只允许 import bpy 和 import mathutils
     - 禁止调用 open/exec/eval/os/sys/subprocess 等
  2. 在 Blender 主线程中执行材质代码（通过 bpy.app.timers）
     - 创建材质对象
     - 将材质应用到场景中的网格对象（优先找名为"平面"的对象）
     - 调用 bpy.ops.render.render() 渲染并保存 PNG
  3. 恢复对象原来的材质（清理现场）

所有材质处理完毕后（如果成功渲染 > 1 张图片）：
  4. 并行调用两次 GPT-4.1-mini（通过 OpenAI API）
     - accuracy_rank：把所有渲染图片发给 GPT，按与描述的相似度排序
     - meaning_rank：按图片的美学/意义程度排序
     - GPT 返回 JSON 格式的排名结果
  5. 将排名结果映射回各材质
```

### 5.4 GPT 排名调用（GPT_API.py）

```python
# 把所有渲染图片转为 base64，连同提示词一起发给 GPT
response = client.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": [
            {"type": "text", "text": accuracy_prompt},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
            # ... 每张图片
        ]}
    ],
    response_format={
        "type": "json_schema",
        "json_schema": {
            # 强制 GPT 返回结构化 JSON：
            # {"ranking_reason": {...}, "final_ranking": ["M2", "M1", "M4", "M3"]}
        }
    }
)
```

提示词优先级（从高到低）：
1. Blender UI 中填写的自定义提示词
2. `configs/local.json` 中的 `ranking.system_prompt`
3. `configs/default.json` 中的默认值
4. 代码中的硬编码默认值

---

## 六、WebSocket 通信协议

### 训练端 → Blender 端（材质请求）

```json
{
  "session_id": "a1b2c3d4",
  "head": {
    "input": "红色的材质",
    "taskid": "uuid-xxx",
    "request": []
  },
  "outputs": [
    {"name": "M1", "code": "import bpy\n..."},
    {"name": "M2", "code": "import bpy\n..."},
    {"name": "M3", "code": "import bpy\n..."},
    {"name": "M4", "code": "import bpy\n..."}
  ]
}
```

### Blender 端 → 训练端（排名结果）

```json
{
  "session_id": "a1b2c3d4",
  "taskid": "uuid-xxx",
  "accuracy_rank": {"M1": 2, "M2": 1, "M3": 4, "M4": 3},
  "meaning_rank":  {"M1": 1, "M2": 2, "M3": 4, "M4": 3},
  "status":        {"M1": true, "M2": true, "M3": false, "M4": true},
  "error_msg":     {"M1": "", "M2": "", "M3": "执行出错...", "M4": ""}
}
```

训练端通过 `session_id` 匹配请求和响应（`response_futures` 字典）。

---

## 七、配置系统

三层深度合并（优先级从低到高）：

```
FALLBACK_CONFIG（config.py 硬编码）
    ↓ 覆盖
configs/default.json（项目共享默认值，提交到 git）
    ↓ 覆盖
configs/local.json（本机配置，gitignored）
```

Profile 系统：`profile_defaults` 提供所有 profile 的基础值，各 profile 可覆盖任意字段。

```
profile = deep_merge(profile_defaults, profiles["blenderllm_qwen3_5_9b"])
```

最终 profile 包含：`transport`、`model`、`lora`、`training` 四个子配置。

---

## 八、实验追踪

每次运行 `create_experiment_tracker()` 时，在 `./runs/` 下创建：

```
runs/20260328_143000_blenderllm_qwen3_5_9b/
├── manifest.json        # run ID、git commit、hostname
├── config.profile.json  # 本次 profile 配置快照
├── config.full.json     # 完整配置快照
├── environment.json     # 环境变量、CUDA 设备
├── trainer_args.json    # HuggingFace TrainingArguments（训练开始时写入）
├── dataset_summary.json # 数据集大小、列名
├── rl_recipe.json       # 算法、奖励函数列表、关键超参
├── metrics.jsonl        # 每步指标（loss、各 reward 分数）
├── reward_events.jsonl  # 每次 reward 调用的完整请求/响应/分数
├── checkpoints.jsonl    # checkpoint 保存记录
├── summary.json         # 训练结束状态（completed / failed）
├── notes.md             # 手动笔记模板
├── checkpoints/         # 模型 checkpoint 文件
└── samples/
    └── samples.jsonl    # 采样记录
```

`ExperimentTrackingCallback` 自动挂载到 HuggingFace Trainer，无需手动调用。

TensorBoard 日志由 HuggingFace Trainer 自动写入 `runs/` 目录，启动方式：

```bash
tensorboard --logdir runs/
# 浏览器打开 http://localhost:6006
```

---

## 九、模型保存

训练结束后（Cell 28-37）：

```python
# 1. 只保存 LoRA 权重（最小，几十 MB）
model.save_lora("grpo_saved_lora")

# 2. 保存合并后的完整模型（16bit，几 GB）
model.save_pretrained_merged("model", tokenizer, save_method="merged_16bit")

# 3. 推送到 HuggingFace Hub（可选）
model.push_to_hub_merged("HF_ACCOUNT/model-name", tokenizer, token="hf_...")
```

---

## 十、关键数据流总结

```
训练步骤 N：

[GRPOTrainer]
  采样 2 个 prompt（如"红色的材质"）
  ↓
  模型生成 4 个补全（每个 prompt）
  补全格式：<think>思考过程</think><code>import bpy\n...</code>
  ↓
[格式奖励函数] ← 本地立即计算
  match_format_exactly:      [3.0, 0.0, 3.0, 0.0, ...]
  match_format_approximately: [2.0, 0.5, 1.5, -0.5, ...]
  ↓
[渲染奖励函数] ← 需要 Blender
  提取 <code> 中的 Python 代码
  打包为 JSON，通过 WebSocket 发送到中转服务器
  ↓
[中转服务器]
  转发给 Blender
  ↓
[Blender + MaterialProcessor]
  AST 安全校验
  执行代码 → 创建材质 → 渲染 PNG
  调用 GPT-4.1-mini 对图片排序（并行两次：accuracy + meaning）
  返回排名结果
  ↓
[中转服务器]
  转发回训练端
  ↓
[训练端 WebSocketClient]
  通过 session_id 匹配响应
  解析 accuracy_rank / meaning_rank / status
  ↓
[奖励函数]
  accuracy_reward: [2.0, 0.0, 1.0, 0.5, ...]  (权重 2)
  meaning_reward:  [1.0, 0.0, 0.5, 0.25, ...] (权重 1)
  error_check:     [2.0, 0.0, 2.0, 2.0, ...]  (权重 2)
  soft_overlong:   [0.0, -0.3, 0.0, 0.0, ...]
  ↓
[DAPO 更新]
  汇总所有奖励 → 计算策略梯度 → 更新 LoRA 权重
  记录 metrics 到 TensorBoard + metrics.jsonl
```

---

## 十一、常见问题

**Q: 训练端发出请求后一直等待，没有返回？**
- 检查 Blender 端插件是否已启动并显示"WebSocket 连接运行中"
- 检查中转服务器是否在运行（`ps aux | grep relay_server`）
- 运行 `python scripts/test_network.py` 诊断链路

**Q: Blender 端收到请求但渲染失败？**
- 确认场景中有摄像机
- 确认场景中有网格对象（优先使用名为"平面"的对象）
- 查看 Blender 控制台的错误输出

**Q: GPT 排名调用失败？**
- 检查 API Key 是否配置（Blender UI 或环境变量 `GMSP_OPENAI_API_KEY`）
- 在 Blender UI 中点击"测试 API 连接"按钮验证

**Q: 训练速度很慢？**
- 渲染奖励函数每步都要等 Blender 渲染 + GPT 调用，这是正常的
- 每步耗时主要取决于：Blender 渲染时间（~5-30s）+ GPT API 延迟（~2-5s）
- 可以通过减少 `num_generations` 来加速（但会降低 DAPO 的采样质量）
