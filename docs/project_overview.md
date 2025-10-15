# 项目整体说明

## 架构概览
- 采用事件驱动架构，基于 `bus.bus.EventBus` 封装的 `pypubsub` 实现模块间通信。
- `hardware` 目录存放硬件模块，每个模块实现 `hardware.iHardware.IHardware` 抽象接口，负责自身线程、资源与状态管理。
- `utils` 目录存放跨模块复用的通用工具（如 UDP 通信）。
- `main.py` 作为演示入口：启动总线、加载配置、实例化硬件模块、发布启动/停止指令。

## 总线主题约定
- 建议为每个硬件模块保留 `command`、`status`、`data` 三类主题，如 `hardware.<module>.command`。
- 控制层主题建议放在 `system.*`，例如 `system.control`、`system.shutdown`。
- 消息 payload 推荐使用关键字参数传递字典，保证订阅端可选字段。

## 新硬件模块接入指南
1. **实现接口**：创建 `hardware/<module>/` 包，并实现 `IHardware` 子类，至少包含以下职责：
   - `attach()` 注册指令监听，初始化资源。
   - `handle_command(action, payload)` 根据命令执行启动/停止/刷新等操作。
   - `detach()/shutdown()` 释放资源，保证可重复启动。
2. **主题规划**：在模块内统一声明主题常量，可参考 `Topics` 类，避免硬编码。
3. **线程与资源管理**：
   - 对外部设备通信应放在独立线程或异步循环中，避免阻塞主线程。
   - 资源释放、异常保护应集中在 `stop()` / `shutdown()` 中，确保主程序关闭时可安全退出。
4. **配置支持**：
   - 提供与 `InsoleConfig` 类似的配置数据类，支持默认值、JSON 读取与覆盖合并。
   - 在 `start()` 阶段允许通过指令 payload 覆盖运行参数，方便测试与 GUI 控制。
5. **数据发布**：
   - 分类广播状态与数据，状态事件应可用于 UI 提示；数据事件建议保持结构化，方便记录与可视化。
6. **记录与调试**：
   - 如需持久化数据，可借鉴 `DataLogger` 的设计，采用后台线程写入，避免阻塞数据通道。

## 主线程编写建议
- 初始化阶段：
  - 创建全局 `EventBus`。
  - 加载配置文件（推荐每个模块提供独立配置）。
  - 实例化所需硬件模块并调用 `attach()`。
- 运行阶段：
  - 通过发布 `command` 主题控制模块，例如定时自动启动、组合动作等。
  - 根据业务需要订阅 `status`/`data` 主题，实现 UI 展示、日志记录、告警等。
- 停止阶段：
  - 捕获 `SIGINT/SIGTERM`，依次调用模块的 `shutdown()`，并发布 `system.shutdown` 等广播。
  - 如果需要自动停止逻辑，可像 `main.py` 一样使用 `threading.Timer` 定时发布 `stop` 指令。

## 目录组织建议
```
hardware/
  iHardware.py            # 抽象接口
  <module_name>/          # 单个模块的配置、核心逻辑、IO 层
    config.py
    core/                 # 与硬件协议、解析、算法相关的纯逻辑代码
    io/                   # 文件、网络、外部服务封装
    module.py             # 对外的 IHardware 实现
utils/
  communication/          # 网络/串口等通信工具
main.py                  # 演示入口或最小可运行示例
``` 
- 每个模块内根据职责拆分 `core` 与 `io` 层，有助于后期单元测试与替换实现。
- 公共常量（如端口、协议字段）集中在模块内的 `constants.py`，避免散落在业务逻辑中。

## 开发流程提示
- 为新模块编写基础集成测试：模拟事件总线消息，确保启动/停止流程可重复执行。
- 保持中文文档更新，说明配置信息、消息主题、关键函数用途。
- 若需 GUI，对应的配置读写可复用模块提供的 `Config` 数据类，将 dataclass 转换为字典后在前端呈现并保存。
