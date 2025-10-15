from typing import Dict, Tuple, Optional
import os
import time
import json
import numpy as np

from src.constants import *
from src.parser import parse_frame_to_matrix
from src.calibration import fit_calibration_from_csv
from src.pressure import compute_pressure_matrix, matrix_info
from src.logger import DataLogger
from src.udp_receiver import UdpReceiver
from src.udp_sender import UdpSender


class InsoleProcessor:
    def __init__(self, left_csv: Optional[str] = None, right_csv: Optional[str] = None, ad_threshold: int = MIN_VALID_AD, logger: Optional[DataLogger] = None):
        self.left_params: Dict[str, Tuple[float, float]] = {}
        self.right_params: Dict[str, Tuple[float, float]] = {}
        if left_csv and os.path.exists(left_csv):
            print(f"Loading left calibration from '{left_csv}'")
            self.left_params = fit_calibration_from_csv(left_csv)
        if right_csv and os.path.exists(right_csv):
            print(f"Loading right calibration from '{right_csv}'")
            self.right_params = fit_calibration_from_csv(right_csv)
        # AD 噪声阈值：小于该阈值的 AD 置零
        self.ad_threshold: int = int(ad_threshold)
        # 运行时注入的监听端口（用于 on_frame 判断左右），默认使用常量
        self._left_listen_port: int = LEFT_PORT
        self._right_listen_port: int = RIGHT_PORT
        # 数据记录器，可选
        self.logger: Optional[DataLogger] = logger

    def on_frame(self, frame: str, port: int):
        # 注意：左右判断基于运行时传入的左端口配置，由 main 中注册回调时闭包提供
        is_left = (port == self._left_listen_port)
        ad = parse_frame_to_matrix(frame)
        print(matrix_info(ad))
        # 第一步：按阈值过滤噪声（小于阈值置零）
        if isinstance(ad, np.ndarray):
            ad = ad.copy()
            ad[ad < self.ad_threshold] = 0
        # 压力计算
        pm = compute_pressure_matrix(
            ad,
            is_left=is_left,
            left_params=self.left_params,
            right_params=self.right_params,
        )
        total = float(pm.sum())
        nonzero = int((pm > 0).sum())
        side = 'Left' if is_left else 'Right'
        print(f"[{side}] total={total:.2f} nonzero={nonzero} max={pm.max():.2f} ")
        # 记录到数据记录器
        if self.logger and self.logger.active:
            self.logger.append(is_left, pm)


def main():
    """
    从配置文件加载参数并运行。默认读取项目根目录下的 config.json；
    也可通过环境变量 INSOLE_CONFIG 指定路径。
    配置示例见 config.example.json。
    """
    cfg_path = os.environ.get("INSOLE_CONFIG", os.path.join(os.path.dirname(__file__), "config.json"))
    cfg = {}
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            print(f"Failed to read config '{cfg_path}', using defaults. Error: {e}")
    else:
        print(f"Config file '{cfg_path}' not found, using defaults from src.constants.")

    left_csv = cfg.get("left_csv")
    right_csv = cfg.get("right_csv")
    left_port = int(cfg.get("left_port", LEFT_PORT))
    right_port = int(cfg.get("right_port", RIGHT_PORT))
    left_remote_port = int(cfg.get("left_remote_port", LEFT_REMOTE_PORT))
    right_remote_port = int(cfg.get("right_remote_port", RIGHT_REMOTE_PORT))
    left_ip = cfg.get("left_ip", LEFT_IP)
    right_ip = cfg.get("right_ip", RIGHT_IP)
    bind_ip = cfg.get("bind_ip", "0.0.0.0")
    ad_threshold = int(cfg.get("ad_threshold", MIN_VALID_AD))
    auto_stop_seconds = float(cfg.get("auto_stop_seconds", 10.0))

    # 初始化数据记录器
    # 保存目录可从环境变量 RECORD_OUT_DIR 覆盖，或在 config.json 的 record_out_dir 指定
    out_dir = os.environ.get("RECORD_OUT_DIR", cfg.get("record_out_dir", "records"))
    logger = DataLogger(out_dir=out_dir)

    proc = InsoleProcessor(left_csv, right_csv, ad_threshold=ad_threshold, logger=logger)
    # 将运行时监听端口注入处理器用于左右判断
    proc._left_listen_port = left_port
    proc._right_listen_port = right_port

    left = UdpReceiver(left_port, proc.on_frame, bind_ip)
    right = UdpReceiver(right_port, proc.on_frame, bind_ip)

    print(f"Listening on {bind_ip}: left={left_port}, right={right_port}")
    left.start()
    right.start()

    # 准备向对方发送控制命令：在运行时发送 'start'，auto_stop_seconds 秒后发送 'stop'
    sender_left = UdpSender(left_ip, left_remote_port)
    sender_right = UdpSender(right_ip, right_remote_port)

    try:
        # 启动会话记录
        logger.start_session(meta={
            "left_csv": left_csv,
            "right_csv": right_csv,
            "left_port": left_port,
            "right_port": right_port,
            "left_ip": left_ip,
            "right_ip": right_ip,
            "ad_threshold": ad_threshold,
        })
        print(f"Sending 'start' to L:{left_ip}:{left_remote_port}  R:{right_ip}:{right_remote_port}")
        sender_left.send("start")
        sender_right.send("start")

        # 运行一段时间后发送 stop
        time.sleep(auto_stop_seconds)
        print(f"Sending 'stop' to L:{left_ip}:{left_remote_port}  R:{right_ip}:{right_remote_port}")
        sender_left.send("stop")
        sender_right.send("stop")
        # 停止会话并保存
        saved = logger.stop_session(save=True)
        if saved:
            print(f"Saved session to: {saved}")

        # 继续保持监听，直至 Ctrl+C
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("Stopping...")
    finally:
        # 关闭收发
        sender_left.close()
        sender_right.close()
        left.stop()
        right.stop()


if __name__ == "__main__":
    main()
 