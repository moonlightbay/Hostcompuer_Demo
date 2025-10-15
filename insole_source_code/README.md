# Insole UDP Processing (Python)

最小可运行示例（聚焦三项核心能力）：
- 与硬件通信：UDP 左右脚监听（默认端口 6060/7070）；
- 接收并解析数据：解析 AA..BB -> 34x10 AD 矩阵（<120 置 0）；
- 校准并计算：从 CSV 拟合 A/B，并将 AD 转换为压力矩阵。

## 安装依赖

在本目录执行：

```powershell
python -m venv .venv ; .\.venv\Scripts\Activate.ps1 ; pip install -r requirements.txt
```

## 运行

```powershell
# 如有左右脚各自 CSV 校准文件，可指定；可覆盖左右脚设备 IP（默认 LEFT_IP=192.168.0.170, RIGHT_IP=192.168.0.171）
python runner.py --left-csv path\to\left.csv --right-csv path\to\right.csv --left-port 6060 --right-port 7070 --left-ip 192.168.0.170 --right-ip 192.168.0.171
```

启动流程：
- 程序启动后，开启 UDP 监听（左 6060 / 右 7070，可配置）。
- 立即分别向左/右设备发送字符串 `start`（UDP，目标为各自 IP+端口）。
- 等待 10 秒后，分别发送 `stop`，对方应停止发送数据。
- 程序继续保持监听，按 Ctrl+C 退出。

## CSV 格式
- 至少4列（示例：时间, 点位, AD值, N值），实际读取字段：
	- 第2列 点位标识（如 `3-5` 或 `左脚3-5`/`右脚3-5`）
	- 第3列 AD 数值
	- 第4列 重量/力（单位自定，保持与拟合输出一致）
- 首行跳过；同一点位需至少2个样本点才可拟合。

## API 速览
- `src/parser.py: parse_frame_to_matrix(frame)` -> 34x10 `np.ndarray[int]`
- `src/parser.py: subtract_baseline(ad, baseline)` -> 逐点 max(0, ad-baseline)
- `src/calibration.py: fit_calibration_from_csv(csv_path)` -> `{key: (A,B)}`
- `src/calibration.py: try_get_params(is_left, r, c, left_params, right_params)` -> `(A,B)|None`
- `src/pressure.py: compute_pressure_matrix(ad_matrix, is_left, left_params, right_params)` -> 34x10 `np.ndarray[float]`

## 备注
- 仅绘图时需要镜像左脚；计算过程中不做镜像。
- 若 AA/BB 缺失或不足，解析返回全零矩阵。
- 本示例不包含数据录制与回放逻辑（不解析 GG..HH）。

## 项目文件列表
constants.py：常量 Rows=34, Cols=10, MIN_VALID_AD=120, 端口号。
parser.py：解析与基线计算（已去掉录制/回放相关 GG..HH 解析）。
calibration.py：线性拟合与参数匹配。
pressure.py：压力矩阵计算。
udp_receiver.py：UDP 接收器（线程）。
runner.py：示例运行脚本（加载 CSV、启动 UDP、打印左右脚压力总和和非零点数）。
requirements.txt：仅需 numpy。
README.md：使用说明（已更新为无录制/回放版本）