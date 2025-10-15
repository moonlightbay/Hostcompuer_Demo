# Insole 模块说明

## 模块职责
- 通过 UDP 与左右脚鞋垫硬件通信，发送 `start`/`stop` 指令并接收实时数据。
- 使用校准 CSV 将原始 AD 数值转换为压力矩阵，仅对外广播校准后的压力结果。
- 将采集过程写入 JSONL 会话文件，保留配置、帧摘要等信息，便于调试与离线分析。

## 硬件交互格式
- **控制指令**：模块向鞋垫硬件的下行端口发送 UTF-8 文本 `start` 或 `stop`。
- **数据帧**：硬件通过 UDP 文本回传，格式为：
  - 包头 `AA` 与包尾 `BB`；
  - 中间包含 34×10=340 个以逗号分隔的整数（按行展开的 AD 矩阵）。
  - 示例：`AA,123,456,...,789,BB`。
- **端口映射**：监听端口与下行控制端口由 `InsoleConfig` 指定（默认左脚监听 6060，下行 8080；右脚监听 7070，下行 9090）。

## 事件总线消息格式
- **指令主题** `hardware.insole.command`
  - 消息字段：`action=str`，可选 `payload` / `overrides=dict`。
  - 支持的 `action`：
    - `start`：启动采集；`payload` 可覆盖配置项（端口、`auto_stop_seconds`、校准路径等）。
    - `stop`：停止采集并关闭资源。
    - `reload_calibration`：运行时重新加载校准文件。
- **状态主题** `hardware.insole.status`
  - 字段：`event=str`, 可选 `payload=dict`。
  - 常见事件：
    - `ready`：模块完成初始化，等待指令。
    - `starting`：附带会话元信息，包含当前配置与校准点数量。
    - `connected`：`payload={"port": <int>}` 表示首次接收到数据的端口。
    - `connection_timeout`、`stopped`、`receiver_error`：用于异常告警与收尾提示。
- **数据主题** `hardware.insole.data`
  - 字段：`frame={
      "frame_index": int,
      "timestamp": float,
      "side": "left" | "right",
      "port": int,
      "stats": {"nonzero": int, "max": float, "total_pressure": float},
      "pressure": List[List[float]]  # 34×10 压力矩阵
    }`
  - 原始 AD 数组不再发布，总线上仅共享压力矩阵及其统计信息。

## 数据落盘格式
- 位置：默认 `hardware/insole/records/`，文件名 `session_YYYYMMDD-HHMMSS.jsonl`。
- 行类型：
  1. `session_meta`：记录矩阵尺寸、开始时间及 `meta` 字段，其中 `meta` 包含当前配置、校准文件路径、`calibration_points`（左右脚成功加载的校准点数量）。
  2. `frame`：每帧写入 `frame_index`、`frame_ts`、`side`、`pressure`（34×10 浮点数组）和与总线一致的统计字段。
  3. `session_end`：结束摘要，记录帧数、最后时间戳等信息。
- 调用 `stop_session(save=False)` 可丢弃会话；默认持久化完整 JSONL 以供回放。

## 配置说明
- 配置文件默认位于 `hardware/insole/config.json`，未找到时使用 `constants.py` 默认值。
- `left_csv`、`right_csv`、`record_dir` 支持：
  - 绝对路径；
  - 相对于配置文件所在目录；
  - 相对于项目根目录的相对路径（模块会自动尝试多级匹配）。
- 若路径无法解析，模块会在启动时输出警告，并忽略对应校准文件。
- 配置优先级：常量默认值 < 配置文件值 < `start` 指令 overrides < 运行时 `reload_calibration`。

## 运行与调试
- `main.py` 演示入口会在启动后立即发布 `start`，并设置 50 秒的自动 `stop` 定时器（亦可通过配置或指令覆盖 `auto_stop_seconds`）。
- 订阅 `hardware.insole.status` 可实时观察生命周期；`starting` 事件中的 `calibration_points` 有助于确认校准是否生效。
- 订阅 `hardware.insole.data` 可获取压力帧摘要（有效点数量、最大值、总压力）。
- 可使用 `scripts/read_session.py` 等工具解析 JSONL 输出，进行可视化或离线对比测试。
