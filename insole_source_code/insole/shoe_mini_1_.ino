#include <SPI.h>
#include <WiFi.h>
#include "esp32-hal-timer.h"
#include "esp_wifi.h"
#include "driver/temp_sensor.h"
#include <Adafruit_NeoPixel.h>

#define LED_BRIGHTNESS 20
#define LED_COUNT      1
#define LED_PIN 0

#define Battery_PIN 1

//AD7490 寄存器配置参数
#define PM 3
#define WEAK 0
#define RANGE 1
#define CODING 1

#define SPI_MISO   5
#define SPI_MOSI   7
#define SPI_SCLK   6
#define SPI_CS     10
#define SPI_Speed 1000000

Adafruit_NeoPixel strip(LED_COUNT, LED_PIN, NEO_GRB + NEO_KHZ800);
SPIClass spi_bus(FSPI);

const float R1 = 510000.0; // 分压电阻R1
const float R2 = 510000.0; // 分压电阻R2
const float refVoltage = 3.3; // 参考电压

//AD7490
unsigned int ADCS[20];//spi数据接收参数
//UDP
const char *ssid = "rewalk_2.4G";
const char *password = "rewalk123456";
//const char *ssid = "rewalk_iot";
// const char *ssid = "rewalk";
// const char *password = "rewalk123456";
// const char *ssid = "rewalk_KneeExoskeleton";
// const char *password = "rewalk123456";
// 选择设备角色：LEFT 或 RIGHT
#define LEFT 1
//#define RIGHT 1
WiFiUDP Udp;
#if defined(LEFT)
  IPAddress local_IP(192, 168, 0, 170); // 自定义本地固定 IP 地址  左脚130 右脚131
  IPAddress gateway(192, 168, 0, 1);   // 网关地址
  IPAddress subnet(255, 255, 255, 0); // 子网掩码
  IPAddress remote_IP(192,168,0,117);// 自定义远程监听 IP 地址  电脑IP地址
  // 左脚：6060/8080  
  // 右脚：7070/9090
  unsigned int remoteUdpPort = 6060;  // 远程监听端口
  unsigned int localUdpPort = 8080;//本地监听端口

#else if defined(RIGHT)
  IPAddress local_IP(192, 168, 0, 171); // 自定义本地固定 IP 地址  左脚130 右脚131
  IPAddress gateway(192, 168, 0, 1);   // 网关地址
  IPAddress subnet(255, 255, 255, 0); // 子网掩码
  IPAddress remote_IP(192,168,0,117);// 自定义远程监听 IP 地址  电脑IP地址
  // 左脚：6060/8080  
  // 右脚：7070/9090
  unsigned int remoteUdpPort = 7070;  // 远程监听端口
  unsigned int localUdpPort = 9090;//本地监听端口
#endif

float batteryVoltage = 0;
int flag = 0;
char getdata[255];//接受测试数据-+
unsigned char start_flag = 0;
//要传输的数据
unsigned int buffer[34*10];
//鞋垫测试点状态
unsigned char shoe[34] = {5,6,7,8,9,9,10,10,10,10,10,10,9,9,9,8,8,8,7,7,7,7,7,7,7,7,7,7,7,7,7,6,5,4};

// 全局变量
unsigned char num = 0;
unsigned int loca = 0;
unsigned char current_x = 0;
unsigned char current_y = 0;
bool scan_in_progress = false;
hw_timer_t *timer = NULL;

// 滑动平均滤波器配置
const int NUM_CHANNELS = 11;  // ADC通道数量
const int WINDOW_SIZE = 5;    // 滑动窗口大小（建议5-10）

// 存储每个通道的历史数据
int adcHistory[NUM_CHANNELS][WINDOW_SIZE];
// 存储每个通道的当前窗口索引
int historyIndex[NUM_CHANNELS] = {0};
// 存储每个通道的当前窗口总和
long channelSums[NUM_CHANNELS] = {0};
// 存储每个通道的有效数据计数
int dataCount[NUM_CHANNELS] = {0};


// 设置发射功率的自定义函数
void setTXPower(int power_dbm) {
  // 转换单位 (dBm -> 0.25dBm)
  int8_t power = power_dbm * 4; 
  
  // 检查有效范围 (8-84 对应 2-21 dBm)
  if (power < 8 || power > 84) {
    Serial.printf("错误：功率值 %d dBm 超出范围 (2-21 dBm)\n", power_dbm);
    return;
  }
  // 设置功率
  esp_err_t result = esp_wifi_set_max_tx_power(power);
  if (result == ESP_OK) {
    Serial.printf("发射功率设置为: %d dBm\n", power_dbm);
  } else {
    Serial.printf("设置失败，错误代码: %d\n", result);
  }
}

// 设置发射功率的自定义函数
int8_t getTXPower(void) {
  int8_t current_power;
  esp_wifi_get_max_tx_power(&current_power);
  Serial.printf("验证功率: %.2f dBm\n", current_power * 0.25);
  return current_power;
}

// 定时器中断处理函数必须使用IRAM_ATTR，确保它存储在RAM中而不是Flash
void IRAM_ATTR timer_interrupt_handler()
{
    if (start_flag == 1 && scan_in_progress == false)
    {
        scan_in_progress = true;
    }
}

// 初始化定时器函数 - ESP32-C3专用
void init_timer(void)
{
    // 创建一个硬件定时器
    // 参数分别是：定时器号(0-3)，预分频值，上升沿计数模式
    timer = timerBegin(0, 80, true);  // 80MHz时钟预分频80 = 1MHz基准频率
    
    // 将定时器附加到中断函数
    // 参数：定时器，回调函数，边缘触发
    timerAttachInterrupt(timer, &timer_interrupt_handler, true);
    
    // 设置定时器的计数值，触发中断
    // 参数：定时器，计数值(1MHz / 50Hz = 20000)，自动重载
    timerAlarmWrite(timer, 20000, true);  // 20000μs = 20ms = 50Hz
    
    // 启用定时器中断
    timerAlarmEnable(timer);
}

// 滑动平均滤波函数
int movingAverage(int channel, int newValue) {
  // 计算被替换的旧值（当窗口填满后）
  int oldestValue = 0;
  if (dataCount[channel] >= WINDOW_SIZE) {
    oldestValue = adcHistory[channel][historyIndex[channel]];
  }
  // 更新数据：用新值替换窗口中最旧的值
  adcHistory[channel][historyIndex[channel]] = newValue;
  // 更新总和：减去旧值，加上新值
  channelSums[channel] = channelSums[channel] - oldestValue + newValue;
  // 更新窗口索引（循环缓冲区）
  historyIndex[channel] = (historyIndex[channel] + 1) % WINDOW_SIZE;
  // 更新有效数据计数（不超过窗口大小）
  if (dataCount[channel] < WINDOW_SIZE) {
    dataCount[channel]++;
  }
  // 计算并返回平均值
  return (int)(channelSums[channel] / dataCount[channel]);
}

int AD7490Read(byte ch) { //spi
  digitalWrite(SPI_CS, LOW);
  spi_bus.beginTransaction(SPISettings(SPI_Speed, MSBFIRST, SPI_MODE0));
  word Control = 0x0000;
  Control |= ((1 << 11) | (ch << 6) | (PM << 4) | (WEAK << 2) | (RANGE << 1) | (CODING)) << 4;  //all control data = 16bit
  spi_bus.transfer16(Control);
  digitalWrite(SPI_CS, HIGH);
  delayMicroseconds(5);
  digitalWrite(SPI_CS, LOW);
  unsigned int Data = spi_bus.transfer16(0);
  spi_bus.endTransaction();
  digitalWrite(SPI_CS, HIGH);
  if ((Data >> 12) == ch)
    Data &= 0x0FFF;
  else
    Data = 0xF000;
  return (Data);
}

void ChangeSheet(unsigned char local)//片选【74HC138】
{
  switch(local)
    {
      case 0:digitalWrite(19, LOW);digitalWrite(18, LOW);digitalWrite(8, LOW);break;
      case 1:digitalWrite(19, HIGH);digitalWrite(18, LOW);digitalWrite(8, LOW);break;
      case 2:digitalWrite(19, LOW);digitalWrite(18, HIGH);digitalWrite(8,LOW);break;
      case 3:digitalWrite(19, HIGH);digitalWrite(18, HIGH);digitalWrite(8, LOW);break;
      case 4:digitalWrite(19, LOW);digitalWrite(18, LOW);digitalWrite(8, HIGH);break;
      default:break;
    }
}

void ChangeRaw(unsigned char local)//片选后，片上八通道单选【4051】
{
  switch(local)
    {
      case 0:digitalWrite(2, LOW);digitalWrite(3, LOW);digitalWrite(4, LOW);break;
      case 1:digitalWrite(2, HIGH);digitalWrite(3, LOW);digitalWrite(4, LOW);break;
      case 2:digitalWrite(2, LOW);digitalWrite(3, HIGH);digitalWrite(4, LOW);break;
      case 3:digitalWrite(2, HIGH);digitalWrite(3, HIGH);digitalWrite(4, LOW);break;
      case 4:digitalWrite(2, LOW);digitalWrite(3, LOW);digitalWrite(4, HIGH);break;
      case 5:digitalWrite(2, HIGH);digitalWrite(3, LOW);digitalWrite(4, HIGH);break;
      case 6:digitalWrite(2, LOW);digitalWrite(3, HIGH);digitalWrite(4, HIGH);break;
      case 7:digitalWrite(2, HIGH);digitalWrite(3, HIGH);digitalWrite(4, HIGH);break;
      default:break;
    }
}

float Read_electric_quantity(void)
{
  int rawValue = analogRead(Battery_PIN);
  float voltage = (rawValue * refVoltage) / 4095.0;
  
  // 计算实际电池电压 (考虑分压比)
  batteryVoltage = voltage * (R1 + R2) / R2;
  batteryVoltage = batteryVoltage - 0.3;
  //对ADC应用滑动平均滤波
  int filteredValues = movingAverage(0, batteryVoltage);
  
  // 估算电池电量 (3.7V锂电池)
  float percentage = 0;
  if (filteredValues > 4.2) percentage = 100;
  else if (filteredValues < 3.5) percentage = 0;
  else percentage = (filteredValues - 3.5) * 100 / (4.2 - 3.5);
  
  //Serial.printf("ADC: %d , Battery: %.2fV (%.0f%%)\n", rawValue, batteryVoltage, percentage);
  return  percentage;
}


void setup() {
  strip.begin();           // INITIALIZE NeoPixel strip object (REQUIRED)
  strip.show();            // Turn OFF all pixels ASAP
  strip.setBrightness(LED_BRIGHTNESS); // Set BRIGHTNESS to about 1/5 (max = 255)

  strip.setPixelColor(0, strip.Color(255, 0, 0));         //  Set pixel's color (in RAM)
  strip.show();

  // put your setup code here, to run once:
  Serial.begin(115200);

  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  // 设置校准参数（可选）
  temp_sensor_config_t temp_sensor = {
      .dac_offset = TSENS_DAC_L2,  // L2 = -2°C, L4 = -4°C, etc
      .clk_div = 6
  };
  // temp_sensor_set_config(temp_sensor);
  // temp_sensor_start();

  init_timer();
  //analogSetCycles(32);       // 每个样本的采样周期数（默认8）

  //SPI
  pinMode(SPI_CS, OUTPUT);
  pinMode(2, OUTPUT);pinMode(3, OUTPUT);pinMode(4, OUTPUT);pinMode(8, OUTPUT);pinMode(18, OUTPUT);pinMode(19, OUTPUT);//control pin,1,2,3 are to change raw,4,5,6 are to change sheet
  delay(10);
  spi_bus.begin(SPI_SCLK, SPI_MISO, SPI_MOSI, SPI_CS);
  
  digitalWrite(10, HIGH);//CS put high
  //UDP
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false); //关闭STA模式下wifi休眠，提高响应速度

  // 设置静态 IP 地址
  if (!WiFi.config(local_IP, gateway, subnet)) {
    Serial.println("Failed to configure Static IP");
  }

  // 设置初始发射功率
  //WiFi.setTxPower(WIFI_POWER_8_5dBm);
  // 设置天线发射功率
  setTXPower(2);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED)
  {
    delay(200);
    Serial.print(".");
  }
  Serial.print("Connected, IP Address: ");
  Serial.println(WiFi.localIP());

  strip.setPixelColor(0, strip.Color(0, 255, 0));         //  Set pixel's color (in RAM)
  strip.show();

  int8_t TXPower =  getTXPower();

   if(Udp.begin(localUdpPort)){//启动Udp监听服务
    Serial.printf("Connect to IP:%s, Port:%d\n successfully!", WiFi.localIP().toString().c_str(), localUdpPort);
  }else{
    Serial.println("Connect failed");
  }
  delay(3000);
  String str_ok = "CONNECTED";
  Udp.beginPacket(remote_IP, remoteUdpPort);//配置远端ip地址和端口
  Udp.print(str_ok);
  Udp.endPacket();//发送数据
}

void loop() {
  //UDP下位机接受消息
  int packetSize = Udp.parsePacket();//获得解析包
  if (packetSize)//解析包不为空
  {
    String str_get;
    //收到Udp数据包
    //Udp.remoteIP().toString().c_str()用于将获取的远端IP地址转化为字符串
    //Serial.printf("收到来自远程IP：%s（远程端口：%d）的数据包字节数：%d\n", Udp.remoteIP().toString().c_str(), Udp.remotePort(), packetSize);
    // 读取Udp数据包并存放在incomingPacket
    int len = Udp.read(getdata, 10);//返回数据包字节数
    if (len > 0)
    { 
      getdata[len] = 0;//清空缓存
    }
    for(unsigned char i = 0; i<len;i++)
    {
      String get_buffer(getdata[i]);
      str_get += get_buffer;
    }

    if(str_get.compareTo("start") == 0)
    {
      start_flag = 1;
      Serial.printf("open\n");
    }
    else if(str_get.compareTo("stop") == 0)
    {
      start_flag = 0;
      Serial.printf("close\n");
    }
    //向串口打印信息
    //Serial.printf("%s",str_get);
  }

  float percentage = Read_electric_quantity();

  long rssi = WiFi.RSSI();

  // WiFi.disconnect(true);  // 关闭Wi-Fi
  // delay(100);
  // float temperature = 0;
  // temp_sensor_read_celsius(&temperature);
  // Serial.printf("芯片温度: %.2f °C\n", temperature);
  // WiFi.begin(ssid, password);  // 重新连接

  if(percentage > 0 && percentage < 20)
  {
    strip.setPixelColor(0, strip.Color(255, 0, 0));
    strip.show();
  }
  else if(percentage == 0)
  {
    strip.setPixelColor(0, strip.Color(0, 0, 255));
    strip.show();
  }
  
  for(unsigned char x = 0;x < 5;x ++)
  { 
    ChangeSheet(x);
    for(unsigned char y = 0;y < 8;y ++)
    {
      if(x == 4 && y >= 2){break;}
      ChangeRaw(y);
      for(unsigned char i = 0;i < 10;i ++)
      {
        //if(i>(shoe[num]-1)){break;}//去掉多余的
        ADCS[i] = AD7490Read(i);
        buffer[loca] = ADCS[i];
        loca++;
        //Serial.printf("AD:%4d;", ADCS[i]);
      }
      //num++;
      //Serial.printf("---SW%d\n",num);//delay(100);

      // 对每个通道应用滑动平均滤波
      // int filteredValues[NUM_CHANNELS];
      // for (int ch = 0; ch < NUM_CHANNELS; ch++) {
      //   filteredValues[ch] = movingAverage(ch, ADCS[ch]);
      // }
    }
  }
  //num = 0;
  loca = 0;

  if (scan_in_progress == true) {
    flag ++;
    if(flag == 10000)
    {
      flag = 0;
    }

    //向udp上位机发送消息
    Udp.beginPacket(remote_IP, remoteUdpPort);//配置远端ip地址和端口
    String str_cnt;
    str_cnt += "AA";
    for(unsigned int z = 0;z < (34*10);z ++)
    {
      String buffer_(buffer[z]);
      str_cnt += buffer_;
      if(z<=(34*10-1)){str_cnt += ",";}
    }
    str_cnt += "BB";
    String Battery = String(batteryVoltage,2);
    str_cnt += Battery;
    str_cnt += "CC";
    String Battery_percentage = String(percentage,2);
    str_cnt += Battery_percentage;
    str_cnt += "DD";
    str_cnt += rssi;
    str_cnt += "EE";
    String frame = String(flag);
    str_cnt += frame;
    str_cnt += "FF";
    Udp.print(str_cnt);//把数据写入发送缓冲区==========一次传输（34*10*12）+（（34*10-1）*4）= 5436bit数据
    Udp.endPacket();//发送数据

    scan_in_progress = false;
  }
}