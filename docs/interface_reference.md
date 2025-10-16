# 模块接口说明

本文档列举项目中主要模块的职责、对外接口以及消息/文件格式，帮助开发者快速了解如何复用与扩展现有能力。

## 事件总线 `bus.bus`
- **Topics**：集中定义的主题常量，当前包含：
  - `hardware.insole.command/status/data`
  - `system.control`、`system.shutdown`
- **EventBus**：对 `pypubsub` 的轻量封装。
  - `subscribe(topic, listener)`：注册监听，返回 `Subscription`。
  - `publish(topic, **message)`：广播消息。
  - `unsubscribe(subscription)`：取消订阅。
  - `has_listeners(topic)`：调试时查询是否存在监听者。
- **Subscription**：记录 `topic` 与回调，可调用 `unsubscribe()` 主动解除。

## 硬件抽象 `hardware.iHardware`
- 抽象类 `IHardware` 约束硬件模块生命周期：
  - `attach()`：申请资源、注册监听。
  - `detach()`：释放资源、撤销监听。
  - `handle_command(action, payload)`：统一处理指令。
  - `shutdown()`：进程退出前的最终清理。
  - `publish(topic, **message)`：向总线发送消息的便捷方法。
- 所有硬件模块应继承 `IHardware` 并遵循上述约定。

## 鞋垫模块 `hardware.insole`
### 导出接口
- `InsoleModule`：`IHardware` 实现，负责 UDP 收发、数据处理、状态广播。
- `InsoleConfig` / `EndpointConfig`：配置数据类，支持 `from_file()`、`merged()` 等方法。
- `InsoleProcessor` / `ProcessedFrame`：核心解析与压力矩阵计算。
- `DataLogger`：异步 JSONL 记录器。
- `runtime` 辅助函数`default_config_path()`、`load_config()`、`make_status_logger()`、`make_data_logger()`：脚本初始化所需的常用入口。

> **延伸阅读**：关于指令协议、配置优先级、会话文件格式等运行期细节，请参见 `docs/insole_module.md` 中的“运行时协议与数据格式”。

## 通信工具 `utils.communication.udp`
- `UdpSender(remote_ip, remote_port)`
  - `send(message: str)`：发送 UTF-8 字符串。
  - `close()`：关闭 socket。
- `UdpReceiver(local_port, on_frame, bind_ip="0.0.0.0")`
  - `start()`：启动后台监听线程。
  - `stop()`：停止线程。
  - 回调签名 `on_frame(frame: str, port: int)`。

## 运行期工具 `utils.runtime`
- `setup_basic_logging(level=logging.INFO, fmt=None)`：配置统一的日志格式，供脚本与主程序调用。

## 脚本与示例
- `main.py`：正式入口，占位提示，供业务扩展。
- `test_scripts/test_insole.py`：鞋垫模块调试脚本，演示如何启动/订阅/自动停止。
- `script_framework.py`：脚本结构模板，包含模块挂载、订阅注册、统一关闭的示例。

开发者可依据本文档快速定位所需组件，组合出适合业务需求的运行脚本或服务。