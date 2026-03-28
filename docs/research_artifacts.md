# GMSP Research Artifacts

## Best Practice

把实验记录拆成两层：

1. 版本控制里的默认配置  
   文件：`configs/default.json`  
   用来保存可复现的默认超参数、执行超时、路径约定、profile。

2. 本地机器覆盖配置  
   文件：`configs/local.json`  
   用来保存私有 IP、API key 相关路径、机器特定目录，不进 git。

## 每次训练必须保留

每个训练 run 都应该保留一个独立目录：`runs/<run_id>/`

最低要求：

- `manifest.json`
  - run id
  - profile 名称
  - 创建时间
  - git commit / branch / dirty 状态
- `config.profile.json`
  - 当前训练真正使用的 profile
- `rl_recipe.json`
  - 当前 RL 算法名称
  - DAPO / GRPO 等关键 loss 配置
  - clip 区间
  - overlong 处理方式
  - 实际启用的 reward 函数列表
- `config.full.json`
  - 合并后的完整配置
- `environment.json`
  - Python 版本
  - 平台信息
  - 关键环境变量
- `dataset_summary.json`
  - 数据集大小
  - 列名
  - 关键过滤说明
- `metrics.jsonl`
  - 每步训练日志
  - 平均 reward
  - 重要 reward 分项
- `reward_events.jsonl`
  - reward 请求 payload
  - Blender / ranking 返回
  - 最终 reward 分数
- `checkpoints.jsonl`
  - 保存时间
  - step
  - checkpoint 路径
- `notes.md`
  - 本次实验目的
  - 改动点
  - 失败案例
  - checkpoint 选择理由

## 论文阶段额外建议保留

- 固定评测集和其版本快照
- 训练时使用的 prompt 模板
- reward 函数源码版本
- RL 算法配方版本
- 典型成功 / 失败样例
- 不同 checkpoint 的人工评测表
- 最终图表生成脚本
- 论文里引用的图片原始路径与生成脚本

## 不建议继续散落保存的内容

- 只保存在 notebook 输出里的关键指标
- 只靠肉眼记住的 checkpoint 选择理由
- 没有 run id 的临时图片和代码
- 把机器私有地址直接硬编码在 notebook 里
