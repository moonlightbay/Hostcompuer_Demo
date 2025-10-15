"""鞋垫模块使用的默认常量配置。"""

ROWS = 34  # 鞋垫传感器矩阵的行数
COLS = 10  # 鞋垫传感器矩阵的列数
MIN_VALID_AD = 120  # 低于该阈值的 AD 视为噪声
LEFT_PORT = 6060  # 左脚默认监听端口
RIGHT_PORT = 7070  # 右脚默认监听端口
LEFT_REMOTE_PORT = 8080  # 向左脚下行控制指令的端口
RIGHT_REMOTE_PORT = 9090  # 向右脚下行控制指令的端口
LEFT_IP = "192.168.0.170"  # 左脚设备的默认 IP
RIGHT_IP = "192.168.0.171"  # 右脚设备的默认 IP
DEFAULT_BIND_IP = "0.0.0.0"  # UDP 监听默认绑定地址
DEFAULT_CONNECT_TIMEOUT = 3.0  # 启动后等待硬件响应的超时时间（秒）
