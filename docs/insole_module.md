# Insole 模块说明

面向开发者的运行、扩展、调试指南，涵盖鞋垫模块在事件总线与硬件之间桥接时需要掌握的关键接口、协议和数据格式。

## 开发者快速接入
- 引导示例位于 `test_scripts/test_insole.py`，展示如何挂载模块、订阅主题并通过事件总线驱动一次采集。
- 常用步骤：
  1. `from bus.bus import EventBus` 并创建共享总线；
  2. 使用 `hardware.insole.runtime.load_config()` 与 `InsoleModule(bus, config)` 初始化模块；
  3. 调用 `module.attach()` 注册监听；
  4. 通过 `bus.publish("hardware.insole.command", action="start")` 启动采集；
  5. 结束时发布 `stop` 或在进程退出前调用 `module.detach()`/`module.shutdown()`。
- 推荐在脚本入口调用 `utils.runtime.setup_basic_logging()`，保证模块输出融入统一日志格式。

```python
bus = EventBus()
config = runtime.load_config()
module = InsoleModule(bus=bus, config=config)
module.attach()

bus.publish("hardware.insole.command", action="start", overrides={"auto_stop_seconds": 5})
```

## 模块职责
- 通过 UDP 与左右脚鞋垫硬件通信，发送 `start`/`stop` 指令并接收实时数据。
- 使用校准 CSV 将原始 AD 数值转换为压力矩阵，仅对外广播校准后的压力结果。
- 将采集过程写入 JSONL 会话文件，保留配置、帧摘要等信息，便于调试与离线分析。

## 运行时协议与数据格式

### 硬件指令与回传格式
- 控制指令：模块向硬件下行端口发送 UTF-8 文本 `start` 或 `stop`。
- 数据帧：硬件通过 UDP 文本回传，格式为 `AA,<340 个逗号分隔整数>,BB`，对应 34×10 的 AD 矩阵。
- 端口映射：由 `InsoleConfig` 指定监听端口与下行端口（默认左脚监听 6060/下行 8080，右脚监听 7070/下行 9090）。

### 事件总线主题
- 指令主题 `hardware.insole.command`
  - 字段：`action=str`，可选 `payload` / `overrides=dict`。
  - 支持 `start`（启动采集并允许覆盖端口、校准路径、`auto_stop_seconds` 等）、`stop`、`reload_calibration`。
- 状态主题 `hardware.insole.status`
  - 字段：`event=str`, 可选 `payload=dict`。
  - 常见事件：`ready`、`starting`（含配置摘要与 `calibration_points`）、`connected`（首次接收端口）、`connection_timeout`、`stopped`、`receiver_error`。
- 数据主题 `hardware.insole.data`
  - 字段 `frame`：
    ```python
    {
        "frame_index": int,
        "timestamp": float,
        "side": "left" | "right",
        "port": int,
        "stats": {"nonzero": int, "max": float, "total_pressure": float},
        "pressure": List[List[float]]  # 34×10 压力矩阵
    }
    ```
  - 原始 AD 数组不再广播，总线仅共享校准后的压力矩阵及统计信息。

### JSONL 会话结构
- 默认位置：`hardware/insole/records/`，文件名 `session_YYYYMMDD-HHMMSS.jsonl`。
- 行类型：
  1. `session_meta`：记录矩阵尺寸、开始时间及 `meta` 字段（包含当前配置、校准文件路径、`calibration_points`）。
  2. `frame`：写入 `frame_index`、`frame_ts`、`side`、`pressure`（34×10 浮点数组）与统计信息。
  3. `session_end`：收尾摘要，记录帧数、结束时间戳等。
- 调用 `stop_session(save=False)` 可在终止时丢弃会话。

## 配置管理
- 默认配置位于 `hardware/insole/config.json`，缺失时退回 `hardware/insole/src/constants.py` 的默认值。
- 支持的路径类型：
  - 绝对路径；
  - 相对于配置文件目录的路径；
  - 相对于项目根目录的相对路径（模块会自动多级解析）。
- 优先级顺序：常量默认值 < 配置文件 < `start` 指令 overrides < 运行期 `reload_calibration`。
- 解析失败时会输出警告，并忽略对应校准文件或记录目录。

## 调试与诊断
- 订阅 `hardware.insole.status`：观测生命周期事件，确认端口绑定与校准是否生效。
- 订阅 `hardware.insole.data`：获取压力帧摘要，可在脚本中做实时监控或转发。
- 使用 `test_scripts/test_insole.py`：快速验证硬件连通性，脚本内含自动停止定时器示例。
- 使用 `scripts/read_session.py`：分析 JSONL 会话，便于可视化或离线对比测试。
- 若需要自定义日志名称，可通过 `runtime.make_status_logger("custom")` 等辅助函数创建模块内一致的日志器。
