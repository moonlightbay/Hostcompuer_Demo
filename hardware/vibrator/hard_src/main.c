/****************************************Copyright (c)************************************************
**                                      [����ķ�Ƽ�]
**                                        IIKMSIK 
**                            �ٷ����̣�https://acmemcu.taobao.com
**                            �ٷ���̳��http://www.e930bbs.com
**                                   
**--------------File Info-----------------------------------------------------------------------------
** File name         : main.c
** Last modified Date: 2020-9-29        
** Last Version      :		   
** Descriptions      : ʹ�õ�SDK�汾-SDK_17.0.2
**						
**----------------------------------------------------------------------------------------------------
** Created by        : [����ķ]
** Created date      : 2018-12-24
** Version           : 1.0
** Descriptions      : ������ [ʵ��7-3������͸����������-�ж�notify] �Ļ������޸ģ������˵�ط���
**                   ����ط���֪ͨʹ�ܺ�������ѹ����APP��ʱ��ÿ5�����һ�ε�ѹ��������ɺ�ת��Ϊ��ص�������֪ͨ������
**                   ��֪ͨ�رպ�ֹͣ��ѹ����
**---------------------------------------------------------------------------------------------------*/
//���õ�C��ͷ�ļ�
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

#include "nrf_delay.h"
#include "boards.h"
#include "nrf_drv_pwm.h"

//Log��Ҫ���õ�ͷ�ļ�
#include "nrf_log.h"
#include "nrf_log_ctrl.h"
#include "nrf_log_default_backends.h"
//APP��ʱ����Ҫ���õ�ͷ�ļ�
#include "app_timer.h"

#include "bsp_btn_ble.h"
//�㲥��Ҫ���õ�ͷ�ļ�
#include "ble_advdata.h"
#include "ble_advertising.h"
//��Դ������Ҫ���õ�ͷ�ļ�
#include "nrf_pwr_mgmt.h"
//SoftDevice handler configuration��Ҫ���õ�ͷ�ļ�
#include "nrf_sdh.h"
#include "nrf_sdh_soc.h"
#include "nrf_sdh_ble.h"
//����д��ģ����Ҫ���õ�ͷ�ļ�
#include "nrf_ble_qwr.h"
//GATT��Ҫ���õ�ͷ�ļ�
#include "nrf_ble_gatt.h"
//���Ӳ���Э����Ҫ���õ�ͷ�ļ�
#include "ble_conn_params.h"
//����͸����Ҫ���õ�ͷ�ļ�
#include "my_ble_uarts.h"

#if defined (UART_PRESENT)
#include "nrf_uart.h"
#endif
#if defined (UARTE_PRESENT)
#include "nrf_uarte.h"
#endif
#include "app_uart.h"
#include "ble_bas.h"
#include "nrf_drv_saadc.h"


#define DEVICE_NAME                     "vibrator"                      // �豸�����ַ��� 
#define UARTS_SERVICE_UUID_TYPE         BLE_UUID_TYPE_VENDOR_BEGIN         // ����͸������UUID���ͣ������Զ���UUID
#define MIN_CONN_INTERVAL               MSEC_TO_UNITS(100, UNIT_1_25_MS)   // ��С���Ӽ�� (0.1 ��) 
#define MAX_CONN_INTERVAL               MSEC_TO_UNITS(200, UNIT_1_25_MS)   // ������Ӽ�� (0.2 ��) 
#define SLAVE_LATENCY                   0                                  // �ӻ��ӳ� 
#define CONN_SUP_TIMEOUT                MSEC_TO_UNITS(4000, UNIT_10_MS)    // �ල��ʱ(4 ��) 
#define FIRST_CONN_PARAMS_UPDATE_DELAY  APP_TIMER_TICKS(5000)              // �����״ε���sd_ble_gap_conn_param_update()�����������Ӳ����ӳ�ʱ�䣨5�룩
#define NEXT_CONN_PARAMS_UPDATE_DELAY   APP_TIMER_TICKS(30000)             // ����ÿ�ε���sd_ble_gap_conn_param_update()�����������Ӳ����ļ��ʱ�䣨30�룩
#define MAX_CONN_PARAMS_UPDATE_COUNT    3                                  // ����������Ӳ���Э��ǰ�������Ӳ���Э�̵���������3�Σ�

#define APP_ADV_INTERVAL                320                                // �㲥��� (200ms)����λ0.625 ms 
#define APP_ADV_DURATION                0                                  // �㲥����ʱ�䣬��λ��10ms������Ϊ0��ʾ����ʱ 

#define BATTERY_LEVEL_MEAS_INTERVAL     APP_TIMER_TICKS(5000)              // ��ص������Լ����5��

#define APP_BLE_OBSERVER_PRIO           3               //Ӧ�ó���BLE�¼����������ȼ���Ӧ�ó������޸ĸ���ֵ
#define APP_BLE_CONN_CFG_TAG            1               //SoftDevice BLE���ñ�־

#define UART_TX_BUF_SIZE 256                            //���ڷ��ͻ����С���ֽ�����
#define UART_RX_BUF_SIZE 256                            //���ڽ��ջ����С���ֽ�����

//����stack dump�Ĵ�����룬��������ջ����ʱȷ����ջλ��
#define DEAD_BEEF                       0xDEADBEEF

#define ADC_REF_VOLTAGE_IN_MILLIVOLTS   600              //�ο���ѹ����λmV��������SAADC�Ĳο���ѹ����Ϊ0.6V����600mV
#define ADC_PRE_SCALING_COMPENSATION    6                //SAADC����������Ϊ1/6�����Խ��Ҫ����6
#define ADC_RES_10BIT                   1024             //10λADCת���������ֵ

APP_TIMER_DEF(m_battery_timer_id);                       //��ز���APP��ʱ��

//�ú����ڽ�SAADC����ֵת��Ϊ��ѹ����λmV
#define ADC_RESULT_IN_MILLI_VOLTS(ADC_VALUE)\
        ((((ADC_VALUE) * ADC_REF_VOLTAGE_IN_MILLIVOLTS) / ADC_RES_10BIT) * ADC_PRE_SCALING_COMPENSATION)	
               
BLE_UARTS_DEF(m_uarts, NRF_SDH_BLE_TOTAL_LINK_COUNT);    //��������Ϊm_uarts�Ĵ���͸������ʵ��
BLE_BAS_DEF(m_bas);                                      //��������Ϊm_bas�ĵ�ط���ʵ��
NRF_BLE_GATT_DEF(m_gatt);                                //��������Ϊm_gatt��GATTģ��ʵ��
NRF_BLE_QWR_DEF(m_qwr);                                  //����һ������Ϊm_qwr���Ŷ�д��ʵ��
BLE_ADVERTISING_DEF(m_advertising);                      //��������Ϊm_advertising�Ĺ㲥ģ��ʵ��

// ??LED???GPIO??(P0.13)
#define LED_PIN1 4
#define LED_PIN2 10
#define LED_PIN3 9

//����P0.12���������
#define MOTOR_CONTROL_PIN_A          NRF_GPIO_PIN_MAP(0,18)
#define MOTOR_CONTROL_PIN_B          NRF_GPIO_PIN_MAP(0,20)

//PWM��������ʵ��ID,ID�������Ŷ�Ӧ��0:PWM0 1:PWM1 2:PWM2 3:PWM3
#define PWM_INSTANCE  0 

//��������Ϊm_pwm0��PWM��������ʵ��������Ϊ0��ʾ��ʵ����Ӧ��PWM����ΪPWM0
static nrfx_pwm_t m_pwm0 = NRFX_PWM_INSTANCE(PWM_INSTANCE);

//����PWM���У������б���λ��RAM�У����Ҫ����Ϊstatic���͵�
static nrf_pwm_values_common_t seq0_values[2];


//�ñ������ڱ������Ӿ������ʼֵ����Ϊ������
static uint16_t m_conn_handle = BLE_CONN_HANDLE_INVALID; 
//���͵�������ݳ���
static uint16_t   m_ble_uarts_max_data_len = BLE_GATT_ATT_MTU_DEFAULT - 3;            
static bool uart_enabled = false;

static nrf_saadc_value_t adc_buf[2];

static uint8_t  pwm_duty_cycle   = 50;
static uint16_t pwm_duration_ms = 10;


//����PWM��ʼ�����ýṹ�岢��ʼ������
nrfx_pwm_config_t config0 =
{
		.output_pins =
		{
				MOTOR_CONTROL_PIN_A,  //ͨ��0ӳ�䵽P0.12�������������ģ�飬���������ߵ�ƽ��Ч����˿���״̬����͵�ƽ
				NRFX_PWM_PIN_NOT_USED,              //ͨ��1��ʹ��
				NRFX_PWM_PIN_NOT_USED,              //ͨ��2��ʹ��
				NRFX_PWM_PIN_NOT_USED               //ͨ��3��ʹ��
		},
		.irq_priority = APP_IRQ_PRIORITY_LOWEST,//�ж����ȼ�
		.base_clock   = NRF_PWM_CLK_1MHz,       //PWMʱ��Ƶ������Ϊ1MHz  
		.count_mode   = NRF_PWM_MODE_UP,        //���ϼ���ģʽ
		.top_value    = 10000,                  //������ֵ10000
		.load_mode    = NRF_PWM_LOAD_COMMON,    //ͨ��װ��ģʽ
		.step_mode    = NRF_PWM_STEP_AUTO       //�����е������Զ��ƽ�
};

static void pwm_common_init(void)
{
		//��ʼ��PWM
    APP_ERROR_CHECK(nrfx_pwm_init(&m_pwm0, &config0, NULL));
}

//����PWM
static void pwm_play_adjustable(uint8_t duty_cycle, uint16_t duration_ms)
{
    if (duty_cycle > 100)
    {
        duty_cycle = 100;
    }

    uint16_t compare_ticks = (uint16_t)((config0.top_value * duty_cycle) / 100U);
    seq0_values[0] = compare_ticks;

    nrf_pwm_sequence_t const seq =
    {
        .values.p_common = seq0_values,
        .length          = 1,
        .repeats         = 0,
        .end_delay       = 0
    };

    nrfx_pwm_stop(&m_pwm0, true);

    nrfx_pwm_flag_t flags;
    uint16_t playback_count = 1;

    if (duration_ms == 0)
    {
        flags = NRFX_PWM_FLAG_LOOP;
    }
    else
    {
        flags = NRFX_PWM_FLAG_STOP;
        uint32_t period_us = (uint32_t)(config0.top_value + 1U);
        uint32_t total_us = (uint32_t)duration_ms * 1000U;
        uint32_t cycles = (total_us + period_us - 1U) / period_us;
        if (cycles == 0U)
        {
            cycles = 1U;
        }
        if (cycles > UINT16_MAX)
        {
            cycles = UINT16_MAX;
        }
        playback_count = (uint16_t)cycles;
    }

    nrfx_err_t err = nrfx_pwm_simple_playback(&m_pwm0, &seq, playback_count, flags);
    if (err != NRFX_SUCCESS)
    {
        APP_ERROR_CHECK(err);
    }
}

//���崮��͸������UUID�б�
static ble_uuid_t m_adv_uuids[]          =                                          
{
    {BLE_UUID_UARTS_SERVICE, UARTS_SERVICE_UUID_TYPE}
};

//SAADC�¼����������ú����н���ѹת��Ϊ��ص�����������������֪ͨ
void saadc_event_handler(nrf_drv_saadc_evt_t const * p_event)
{
		//printf("ADC\r\n");
    if (p_event->type == NRF_DRV_SAADC_EVT_DONE)
    {
			  nrf_saadc_value_t adc_result;
        uint16_t          batt_lvl_in_milli_volts;
        uint8_t           percentage_batt_lvl;
        uint32_t          err_code;
        //��ȡ����ֵ
        adc_result = p_event->data.done.p_buffer[0];
 
        //���úû��棬Ϊ��һ�β���׼��
        err_code = nrf_drv_saadc_buffer_convert(p_event->data.done.p_buffer, 1);
        APP_ERROR_CHECK(err_code);
        //������ֵת��Ϊ��ѹ����λmV
        batt_lvl_in_milli_volts = ADC_RESULT_IN_MILLI_VOLTS(adc_result);
				//printf("mV:%d\r\n", batt_lvl_in_milli_volts);
			  //��ѹת��Ϊ����
        percentage_batt_lvl = battery_level_in_percent(batt_lvl_in_milli_volts);
			  
			  //����֪ͨ
        err_code = ble_bas_battery_level_update(&m_bas, percentage_batt_lvl, BLE_CONN_HANDLE_ALL);
        if ((err_code != NRF_SUCCESS) &&
            (err_code != NRF_ERROR_INVALID_STATE) &&
            (err_code != NRF_ERROR_RESOURCES) &&
            (err_code != NRF_ERROR_BUSY) &&
            (err_code != BLE_ERROR_GATTS_SYS_ATTR_MISSING)
           )
        {
            APP_ERROR_HANDLER(err_code);
        }
    }
}
//SAADC��ʼ��
static void adc_configure(void)
{
    ret_code_t err_code = nrf_drv_saadc_init(NULL, saadc_event_handler);
    APP_ERROR_CHECK(err_code);

    nrf_saadc_channel_config_t config =
        NRF_DRV_SAADC_DEFAULT_CHANNEL_CONFIG_SE(NRF_SAADC_INPUT_AIN0);
    err_code = nrf_drv_saadc_channel_init(0, &config);
    APP_ERROR_CHECK(err_code);

    err_code = nrf_drv_saadc_buffer_convert(&adc_buf[0], 1);
    APP_ERROR_CHECK(err_code);

    err_code = nrf_drv_saadc_buffer_convert(&adc_buf[1], 1);
    APP_ERROR_CHECK(err_code);
}
//�豸��������  �������ƣ�����ķ����͸��
const char device_name[21] = {0xE8,0x89,0xBE,0xE5,0x85,0x8B,0xE5,0xA7,0x86,0xE4,0xB8,0xB2,0xE5,0x8F,0xA3,0xE9,0x80,0x8F,0xE4,0xBC,0xA0};

//GAP������ʼ�����ú���������Ҫ��GAP�����������豸���ƣ������������ѡ���Ӳ���
static void gap_params_init(void)
{
    ret_code_t              err_code;
	  //�������Ӳ����ṹ�����
    ble_gap_conn_params_t   gap_conn_params;
    ble_gap_conn_sec_mode_t sec_mode;
    //����GAP�İ�ȫģʽ
    BLE_GAP_CONN_SEC_MODE_SET_OPEN(&sec_mode);
		ble_gap_addr_t addr;
    err_code = sd_ble_gap_addr_get(&addr);
    if (err_code != NRF_SUCCESS)
    {
        NRF_LOG_ERROR("Failed to get BLE address, error code: %d", err_code);
        return;
    }
    printf("BLE Address: %02X:%02X:%02X:%02X:%02X:%02X\r\n",
                 addr.addr[5], addr.addr[4], addr.addr[3],
                 addr.addr[2], addr.addr[1], addr.addr[0]);
    //����GAP�豸���ƣ�ʹ��Ӣ���豸����
		char name[20];
		sprintf(name, "%s%02X%02X%02X%02X",DEVICE_NAME,addr.addr[3],
                 addr.addr[2], addr.addr[1], addr.addr[0]);
		printf("%s\r\n",name);
    err_code = sd_ble_gap_device_name_set(&sec_mode,
                                              (const uint8_t *)name,
                                              strlen(name));
	
	  //����GAP�豸���ƣ�����ʹ���������豸����
//    err_code = sd_ble_gap_device_name_set(&sec_mode,
//                                          (const uint8_t *)device_name,
//                                          sizeof(device_name));
																					
    //��麯�����صĴ������
		APP_ERROR_CHECK(err_code);
																				
    //������ѡ���Ӳ���������ǰ������gap_conn_params
    memset(&gap_conn_params, 0, sizeof(gap_conn_params));

    gap_conn_params.min_conn_interval = MIN_CONN_INTERVAL;//��С���Ӽ��
    gap_conn_params.max_conn_interval = MAX_CONN_INTERVAL;//��С���Ӽ��
    gap_conn_params.slave_latency     = SLAVE_LATENCY;    //�ӻ��ӳ�
    gap_conn_params.conn_sup_timeout  = CONN_SUP_TIMEOUT; //�ල��ʱ
    //����Э��ջAPI sd_ble_gap_ppcp_set����GAP����
    err_code = sd_ble_gap_ppcp_set(&gap_conn_params);
    APP_ERROR_CHECK(err_code);
																					
}
//GATT�¼����������ú����д���MTU�����¼�
void gatt_evt_handler(nrf_ble_gatt_t * p_gatt, nrf_ble_gatt_evt_t const * p_evt)
{
    //�����MTU�����¼�
	  if ((m_conn_handle == p_evt->conn_handle) && (p_evt->evt_id == NRF_BLE_GATT_EVT_ATT_MTU_UPDATED))
    {
        //���ô���͸���������Ч���ݳ��ȣ�MTU-opcode-handle��
			  m_ble_uarts_max_data_len = p_evt->params.att_mtu_effective - OPCODE_LENGTH - HANDLE_LENGTH;
        NRF_LOG_INFO("Data len is set to 0x%X(%d)", m_ble_uarts_max_data_len, m_ble_uarts_max_data_len);
    }
    NRF_LOG_DEBUG("ATT MTU exchange completed. central 0x%x peripheral 0x%x",
                  p_gatt->att_mtu_desired_central,
                  p_gatt->att_mtu_desired_periph);
}
//��ʼ��GATT����ģ��
static void gatt_init(void)
{
    //��ʼ��GATT����ģ��
	  ret_code_t err_code = nrf_ble_gatt_init(&m_gatt, gatt_evt_handler);
	  //��麯�����صĴ������
    APP_ERROR_CHECK(err_code);
	  //����ATT MTU�Ĵ�С,�������õ�ֵΪ247
	  err_code = nrf_ble_gatt_att_mtu_periph_set(&m_gatt, NRF_SDH_BLE_GATT_MAX_MTU_SIZE);
    APP_ERROR_CHECK(err_code);
}

//�Ŷ�д���¼������������ڴ����Ŷ�д��ģ��Ĵ���
static void nrf_qwr_error_handler(uint32_t nrf_error)
{
    //���������
	  APP_ERROR_HANDLER(nrf_error);
}
//�����¼��ص����������ڳ�ʼ��ʱע�ᣬ�ú������ж��¼����Ͳ����д���
//�����յ����ݳ��ȴﵽ�趨�����ֵ���߽��յ����з�������Ϊһ�����ݽ�����ɣ�֮�󽫽��յ����ݷ��͸�����
void uart_event_handle(app_uart_evt_t * p_event)
{
    static uint8_t data_array[BLE_UARTS_MAX_DATA_LEN];
    static uint8_t index = 0;
    uint32_t       err_code;
    //�ж��¼�����
    switch (p_event->evt_type)
    {
        case APP_UART_DATA_READY://���ڽ����¼�
            UNUSED_VARIABLE(app_uart_get(&data_array[index]));
            index++;
            //���մ������ݣ������յ����ݳ��ȴﵽm_ble_uarts_max_data_len���߽��յ����з�����Ϊһ�����ݽ������
            if ((data_array[index - 1] == '\n') ||
                (data_array[index - 1] == '\r') ||
                (index >= m_ble_uarts_max_data_len))
            {
                if (index > 1)
                {
                    NRF_LOG_DEBUG("Ready to send data over BLE NUS");
                    NRF_LOG_HEXDUMP_DEBUG(data_array, index);
                    //���ڽ��յ�����ʹ��notify���͸�BLE����
                    do
                    {
                        uint16_t length = (uint16_t)index;
                        err_code = ble_uarts_data_send(&m_uarts, data_array, &length, m_conn_handle);
                        if ((err_code != NRF_ERROR_INVALID_STATE) &&
                            (err_code != NRF_ERROR_RESOURCES) &&
                            (err_code != NRF_ERROR_NOT_FOUND))
                        {
                            APP_ERROR_CHECK(err_code);
                        }
                    } while (err_code == NRF_ERROR_RESOURCES);
                }

                index = 0;
            }
            break;
        //ͨѶ�����¼������������
        case APP_UART_COMMUNICATION_ERROR:
            APP_ERROR_HANDLER(p_event->data.error_communication);
            break;
        //FIFO�����¼������������
        case APP_UART_FIFO_ERROR:
            APP_ERROR_HANDLER(p_event->data.error_code);
            break;

        default:
            break;
    }
}
//��������
void uart_config(void)
{
	uint32_t err_code;
	
	//���崮��ͨѶ�������ýṹ�岢��ʼ��
  const app_uart_comm_params_t comm_params =
  {
    RX_PIN_NUMBER,//����uart��������
    TX_PIN_NUMBER,//����uart��������
    RTS_PIN_NUMBER,//����uart RTS���ţ����عرպ���Ȼ������RTS��CTS���ţ����������������ԣ������������������ţ����������Կ���ΪIOʹ��
    CTS_PIN_NUMBER,//����uart CTS����
    APP_UART_FLOW_CONTROL_DISABLED,//�ر�uartӲ������
    false,//��ֹ��ż����
    NRF_UART_BAUDRATE_115200//uart����������Ϊ115200bps
  };
  //��ʼ�����ڣ�ע�ᴮ���¼��ص�����
  APP_UART_FIFO_INIT(&comm_params,
                         UART_RX_BUF_SIZE,
                         UART_TX_BUF_SIZE,
                         uart_event_handle,
                         APP_IRQ_PRIORITY_LOWEST,
                         err_code);

  APP_ERROR_CHECK(err_code);
	
}
static void uart_reconfig(void)
{
	if(uart_enabled == false)//��ʼ������
	{
		uart_config();
		uart_enabled = true;
	}
	else
	{
		app_uart_close();//����ʼ������
		uart_enabled = false;
	}
}
//����͸���¼��ص�����������͸�������ʼ��ʱע��
static void uarts_data_handler(ble_uarts_evt_t * p_evt)
{
	  //֪ͨʹ�ܺ�ų�ʼ������
	  if (p_evt->type == BLE_NUS_EVT_COMM_STARTED)
		{
			uart_reconfig();
		}
		//֪ͨ�رպ󣬹رմ���
		else if(p_evt->type == BLE_NUS_EVT_COMM_STOPPED)
		{
		  uart_reconfig();
		}
	  //�ж��¼�����:���յ��������¼�
    if (p_evt->type == BLE_UARTS_EVT_RX_DATA)
    {
        uint32_t err_code;
        const uint8_t * p_data = p_evt->params.rx_data.p_data;
        uint16_t        data_len = p_evt->params.rx_data.length;
        static uint8_t  frame_buffer[6];
        static uint8_t  frame_index = 0;

        //���ڴ�ӡ�����յ����ݣ��������Զ���Э��֡
        for (uint16_t i = 0; i < data_len; i++)
        {
            uint8_t byte = p_data[i];

            do
            {
                err_code = app_uart_put(byte);
                if ((err_code != NRF_SUCCESS) && (err_code != NRF_ERROR_BUSY))
                {
                    NRF_LOG_ERROR("Failed receiving NUS message. Error 0x%x. ", err_code);
                    APP_ERROR_CHECK(err_code);
                }
            } while (err_code == NRF_ERROR_BUSY);

            if (frame_index == 0)
            {
                if (byte != 0x55)
                {
                    continue;
                }
            }

            frame_buffer[frame_index++] = byte;

            if (frame_index == sizeof(frame_buffer))
            {
                uint8_t command        = frame_buffer[1];
                uint8_t intensity      = frame_buffer[2];
                uint8_t duration_raw   = frame_buffer[3];
                uint8_t checksum       = frame_buffer[4];
                uint8_t frame_tail     = frame_buffer[5];
                uint8_t expected_sum   = (uint8_t)(command + intensity + duration_raw);

                frame_index = 0;

                if (frame_tail != 0xAA)
                {
                    NRF_LOG_WARNING("Invalid frame tail: 0x%02X", frame_tail);
                    continue;
                }

                if (checksum != expected_sum)
                {
                    NRF_LOG_WARNING("Checksum mismatch: expected 0x%02X got 0x%02X", expected_sum, checksum);
                    continue;
                }

                printf("RX\r\n");

                if (command == 0x01)
                {
                    printf("data\r\n");

                    if (intensity > 100)
                    {
                        intensity = 100;
                    }
                    pwm_duty_cycle = intensity;

                    if (duration_raw == 0)
                    {
                        pwm_duration_ms = 0;
                    }
                    else
                    {
                        uint32_t requested_ms = (uint32_t)duration_raw * 50U;
                        pwm_duration_ms = (uint16_t)requested_ms;
                    }

                    pwm_play_adjustable(pwm_duty_cycle, pwm_duration_ms);
                }
                else if (command == 0x00)
                {
                    nrfx_pwm_stop(&m_pwm0, true);
                }
                else
                {
                    NRF_LOG_WARNING("Unknown command: 0x%02X", command);
                }
            }
        }
        if (p_evt->params.rx_data.p_data[p_evt->params.rx_data.length - 1] == '\r')
        {
            while (app_uart_put('\n') == NRF_ERROR_BUSY);
        }
    }
		//�ж��¼�����:���;����¼������¼��ں����������õ�����ǰ�����ڸ��¼��з�תָʾ��D4��״̬��ָʾ���¼��Ĳ���
    if (p_evt->type == BLE_UARTS_EVT_TX_RDY)
    {
			nrf_gpio_pin_toggle(LED_PIN1);
		}
}
//��ط����¼�������
static void on_bas_evt(ble_bas_t * p_bas, ble_bas_evt_t * p_evt)
{
    ret_code_t err_code;

    switch (p_evt->evt_type)
    {
        //��ط���֪ͨʹ���¼�
			  case BLE_BAS_EVT_NOTIFICATION_ENABLED:
            //������ص�ѹ����APP��ʱ��
            err_code = app_timer_start(m_battery_timer_id, BATTERY_LEVEL_MEAS_INTERVAL, NULL);
            APP_ERROR_CHECK(err_code);
            break; 
        //��ط���֪ͨ�ر��¼�
        case BLE_BAS_EVT_NOTIFICATION_DISABLED:
            //ֹͣ��ص�ѹ����APP��ʱ��
				    err_code = app_timer_stop(m_battery_timer_id);
            APP_ERROR_CHECK(err_code);
            break; 

        default:
            break;
    }
}
//��ط����ʼ��
static void bas_init(void)
{
    ret_code_t     err_code;
    ble_bas_init_t bas_init_obj; //�����ط����ʼ���ṹ��

    memset(&bas_init_obj, 0, sizeof(bas_init_obj));//������͸�������ʼ���ṹ��

    bas_init_obj.evt_handler          = on_bas_evt;//���õ�ط����¼��ص�����
    bas_init_obj.support_notification = true;      //����notify
    bas_init_obj.p_report_ref         = NULL;
    bas_init_obj.initial_batt_level   = 100;       //������ʼֵ����Ϊ100%

    bas_init_obj.bl_rd_sec        = SEC_OPEN;//���ö�����ֵ�İ�ȫ�����ް�ȫ��
    bas_init_obj.bl_cccd_wr_sec   = SEC_OPEN;//����дCCCD�İ�ȫ�����ް�ȫ��
    bas_init_obj.bl_report_rd_sec = SEC_OPEN;//���ö������������İ�ȫ�����ް�ȫ��
    //��ʼ����ط���
    err_code = ble_bas_init(&m_bas, &bas_init_obj);
	  //��麯������ֵ
    APP_ERROR_CHECK(err_code);
}
//��ʼ���Ŷ�д��ģ��
static void qwr_init(void)
{
    ret_code_t         err_code;
    nrf_ble_qwr_init_t qwr_init = {0};

    //�����Ŷ�д���ʼ���ṹ�����
    qwr_init.error_handler = nrf_qwr_error_handler;
    //��ʼ���Ŷ�д��ģ��
    err_code = nrf_ble_qwr_init(&m_qwr, &qwr_init);
		//��麯������ֵ
    APP_ERROR_CHECK(err_code);
}
//��ʼ���Ŷ�д��ģ��
static void uarts_init(void)
{
    ret_code_t         err_code;
    //���崮��͸����ʼ���ṹ��
	  ble_uarts_init_t     uarts_init;
	  //���㴮��͸�������ʼ���ṹ��
		memset(&uarts_init, 0, sizeof(uarts_init));
		//���ô���͸���¼��ص�����
    uarts_init.data_handler = uarts_data_handler;
    //��ʼ������͸������
    err_code = ble_uarts_init(&m_uarts, &uarts_init);
    APP_ERROR_CHECK(err_code);
}
//�����ʼ��
static void services_init(void)
{
		qwr_init();   //�Ŷ�д��ģ���ʼ��
	  uarts_init(); //����͸�������ʼ��
		bas_init();   //��ط����ʼ��
}

//���Ӳ���Э��ģ���¼�������
static void on_conn_params_evt(ble_conn_params_evt_t * p_evt)
{
    ret_code_t err_code;
    //�ж��¼����ͣ������¼�����ִ�ж���
	  //���Ӳ���Э��ʧ�ܣ��Ͽ���ǰ����
    if (p_evt->evt_type == BLE_CONN_PARAMS_EVT_FAILED)
    {
        err_code = sd_ble_gap_disconnect(m_conn_handle, BLE_HCI_CONN_INTERVAL_UNACCEPTABLE);
        APP_ERROR_CHECK(err_code);
    }
		//���Ӳ���Э�̳ɹ�
		if (p_evt->evt_type == BLE_CONN_PARAMS_EVT_SUCCEEDED)
    {
       //���ܴ���;
    }
}

//���Ӳ���Э��ģ��������¼�������nrf_error�����˴�����룬ͨ��nrf_error���Է���������Ϣ
static void conn_params_error_handler(uint32_t nrf_error)
{
    //���������
	  APP_ERROR_HANDLER(nrf_error);
}


//���Ӳ���Э��ģ���ʼ��
static void conn_params_init(void)
{
    ret_code_t             err_code;
	  //�������Ӳ���Э��ģ���ʼ���ṹ��
    ble_conn_params_init_t cp_init;
    //����֮ǰ������
    memset(&cp_init, 0, sizeof(cp_init));
    //����ΪNULL����������ȡ���Ӳ���
    cp_init.p_conn_params                  = NULL;
	  //���ӻ�����֪ͨ���״η������Ӳ�����������֮���ʱ������Ϊ5��
    cp_init.first_conn_params_update_delay = FIRST_CONN_PARAMS_UPDATE_DELAY;
	  //ÿ�ε���sd_ble_gap_conn_param_update()�����������Ӳ������������֮��ļ��ʱ������Ϊ��30��
    cp_init.next_conn_params_update_delay  = NEXT_CONN_PARAMS_UPDATE_DELAY;
	  //�������Ӳ���Э��ǰ�������Ӳ���Э�̵�����������Ϊ��3��
    cp_init.max_conn_params_update_count   = MAX_CONN_PARAMS_UPDATE_COUNT;
	  //���Ӳ������´������¼���ʼ��ʱ
    cp_init.start_on_notify_cccd_handle    = BLE_GATT_HANDLE_INVALID;
	  //���Ӳ�������ʧ�ܲ��Ͽ�����
    cp_init.disconnect_on_fail             = false;
	  //ע�����Ӳ��������¼����
    cp_init.evt_handler                    = on_conn_params_evt;
	  //ע�����Ӳ������´����¼����
    cp_init.error_handler                  = conn_params_error_handler;
    //���ÿ⺯���������Ӳ������³�ʼ���ṹ��Ϊ�����������ʼ�����Ӳ���Э��ģ��
    err_code = ble_conn_params_init(&cp_init);
    APP_ERROR_CHECK(err_code);
}

//�㲥�¼�������
static void on_adv_evt(ble_adv_evt_t ble_adv_evt)
{
    ret_code_t err_code;
    //�жϹ㲥�¼�����
    switch (ble_adv_evt)
    {
        //���ٹ㲥�����¼������ٹ㲥�������������¼�
			  case BLE_ADV_EVT_FAST:
            NRF_LOG_INFO("Fast advertising.");
			      //���ù㲥ָʾ��Ϊ���ڹ㲥��D1ָʾ����˸��
            err_code = bsp_indication_set(BSP_INDICATE_ADVERTISING);
            APP_ERROR_CHECK(err_code);
            break;
        //�㲥IDLE�¼����㲥��ʱ���������¼�
        case BLE_ADV_EVT_IDLE:
					  //���ù㲥ָʾ��Ϊ�㲥ֹͣ��D1ָʾ��Ϩ��
            err_code = bsp_indication_set(BSP_INDICATE_IDLE);
            APP_ERROR_CHECK(err_code);
            break;

        default:
            break;
    }
}
//�㲥��ʼ��
static void advertising_init(void)
{
    ret_code_t             err_code;
	  //����㲥��ʼ�����ýṹ�����
    ble_advertising_init_t init;
    //����֮ǰ������
    memset(&init, 0, sizeof(init));
    //�豸�������ͣ�ȫ��
    init.advdata.name_type               = BLE_ADVDATA_FULL_NAME;
	  //�Ƿ������ۣ�����
    init.advdata.include_appearance      = false;
	  //Flag:һ��ɷ���ģʽ����֧��BR/EDR
    init.advdata.flags                   = BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE;
	  //UUID�ŵ�ɨ����Ӧ����
	  init.srdata.uuids_complete.uuid_cnt = sizeof(m_adv_uuids) / sizeof(m_adv_uuids[0]);
    init.srdata.uuids_complete.p_uuids  = m_adv_uuids;
	
    //���ù㲥ģʽΪ���ٹ㲥
    init.config.ble_adv_fast_enabled  = true;
	  //���ù㲥����͹㲥����ʱ��
    init.config.ble_adv_fast_interval = APP_ADV_INTERVAL;
    init.config.ble_adv_fast_timeout  = APP_ADV_DURATION;
    //�㲥�¼��ص�����
    init.evt_handler = on_adv_evt;
    //��ʼ���㲥
    err_code = ble_advertising_init(&m_advertising, &init);
    APP_ERROR_CHECK(err_code);
    //���ù㲥���ñ�ǡ�APP_BLE_CONN_CFG_TAG�����ڸ��ٹ㲥���õı�ǣ�����Ϊδ��Ԥ����һ���������ڽ�����SoftDevice�汾�У�
		//����ʹ��sd_ble_gap_adv_set_configure()�����µĹ㲥����
		//��ǰSoftDevice�汾��S132 V7.2.0�汾��֧�ֵ����㲥������Ϊ1�����APP_BLE_CONN_CFG_TAGֻ��д1��
    ble_advertising_conn_cfg_tag_set(&m_advertising, APP_BLE_CONN_CFG_TAG);
}

//BLE�¼�������
static void ble_evt_handler(ble_evt_t const * p_ble_evt, void * p_context)
{
    ret_code_t err_code = NRF_SUCCESS;
    //�ж�BLE�¼����ͣ������¼�����ִ����Ӧ����
    switch (p_ble_evt->header.evt_id)
    {
        //�Ͽ������¼�
			  case BLE_GAP_EVT_DISCONNECTED:
            m_conn_handle = BLE_CONN_HANDLE_INVALID;
				    
				    //��ӡ��ʾ��Ϣ
				    NRF_LOG_INFO("Disconnected.");
				    uart_reconfig();
            break;
				
        //�����¼�
        case BLE_GAP_EVT_CONNECTED:
            NRF_LOG_INFO("Connected.");
				    //����ָʾ��״̬Ϊ����״̬����ָʾ��D1����
            err_code = bsp_indication_set(BSP_INDICATE_CONNECTED);
            APP_ERROR_CHECK(err_code);
				    //�������Ӿ��
            m_conn_handle = p_ble_evt->evt.gap_evt.conn_handle;
				    //�����Ӿ��������Ŷ�д��ʵ����������Ŷ�д��ʵ���͸����ӹ��������������ж�����ӵ�ʱ��ͨ��������ͬ���Ŷ�д��ʵ�����ܷ��㵥�������������
            err_code = nrf_ble_qwr_conn_handle_assign(&m_qwr, m_conn_handle);
            APP_ERROR_CHECK(err_code);
            break;
				
        //PHY�����¼�
        case BLE_GAP_EVT_PHY_UPDATE_REQUEST:
        {
            NRF_LOG_DEBUG("PHY update request.");
            ble_gap_phys_t const phys =
            {
                .rx_phys = BLE_GAP_PHY_AUTO,
                .tx_phys = BLE_GAP_PHY_AUTO,
            };
						//��ӦPHY���¹��
            err_code = sd_ble_gap_phy_update(p_ble_evt->evt.gap_evt.conn_handle, &phys);
            APP_ERROR_CHECK(err_code);
        } break;
				//��ȫ���������¼�
				case BLE_GAP_EVT_SEC_PARAMS_REQUEST:
            //��֧�����
            err_code = sd_ble_gap_sec_params_reply(m_conn_handle, BLE_GAP_SEC_STATUS_PAIRING_NOT_SUPP, NULL, NULL);
            APP_ERROR_CHECK(err_code);
				 
				//ϵͳ���Է������ڵȴ���
				case BLE_GATTS_EVT_SYS_ATTR_MISSING:
            //ϵͳ����û�д洢������ϵͳ����
            err_code = sd_ble_gatts_sys_attr_set(m_conn_handle, NULL, 0, 0);
            APP_ERROR_CHECK(err_code);
            break;
        //GATT�ͻ��˳�ʱ�¼�
        case BLE_GATTC_EVT_TIMEOUT:
            NRF_LOG_DEBUG("GATT Client Timeout.");
				    //�Ͽ���ǰ����
            err_code = sd_ble_gap_disconnect(p_ble_evt->evt.gattc_evt.conn_handle,
                                             BLE_HCI_REMOTE_USER_TERMINATED_CONNECTION);
            APP_ERROR_CHECK(err_code);
            break;
				
        //GATT��������ʱ�¼�
        case BLE_GATTS_EVT_TIMEOUT:
            NRF_LOG_DEBUG("GATT Server Timeout.");
				    //�Ͽ���ǰ����
            err_code = sd_ble_gap_disconnect(p_ble_evt->evt.gatts_evt.conn_handle,
                                             BLE_HCI_REMOTE_USER_TERMINATED_CONNECTION);
            APP_ERROR_CHECK(err_code);
            break;

        default:
            break;
    }
}

//��ʼ��BLEЭ��ջ
static void ble_stack_init(void)
{
    ret_code_t err_code;
    //����ʹ��SoftDevice���ú����л����sdk_config.h�ļ��е�Ƶʱ�ӵ����������õ�Ƶʱ��
    err_code = nrf_sdh_enable_request();
    APP_ERROR_CHECK(err_code);
    
    //���屣��Ӧ�ó���RAM��ʼ��ַ�ı���
    uint32_t ram_start = 0;
	  //ʹ��sdk_config.h�ļ���Ĭ�ϲ�������Э��ջ����ȡӦ�ó���RAM��ʼ��ַ�����浽����ram_start
    err_code = nrf_sdh_ble_default_cfg_set(APP_BLE_CONN_CFG_TAG, &ram_start);
    APP_ERROR_CHECK(err_code);

    //ʹ��BLEЭ��ջ
    err_code = nrf_sdh_ble_enable(&ram_start);
    APP_ERROR_CHECK(err_code);

    //ע��BLE�¼��ص�����
    NRF_SDH_BLE_OBSERVER(m_ble_observer, APP_BLE_OBSERVER_PRIO, ble_evt_handler, NULL);
}
//��ʼ����Դ����ģ��
static void power_management_init(void)
{
    ret_code_t err_code;
	  //��ʼ����Դ����
    err_code = nrf_pwr_mgmt_init();
	  //��麯�����صĴ������
    APP_ERROR_CHECK(err_code);
}

//��ʼ��ָʾ��
static void leds_init(void)
{
//    NRF_P0->DIRSET = (1 << LED_PIN1);  // DIRSET????4??1,?????
//		NRF_P0->DIRSET = (1 << LED_PIN2);  // DIRSET????10??1,?????
//		NRF_P0->DIRSET = (1 << LED_PIN3);  // DIRSET????9??1,?????
//		NRF_P0->OUTCLR = (1 << LED_PIN1);
//		NRF_P0->OUTSET = (1 << LED_PIN2);
//		NRF_P0->OUTSET = (1 << LED_PIN3);
		nrf_gpio_cfg_output(LED_PIN1);
		nrf_gpio_cfg_output(LED_PIN2);
		nrf_gpio_cfg_output(LED_PIN3);
		nrf_gpio_pin_clear(LED_PIN1);
		nrf_gpio_pin_set(LED_PIN2);
		nrf_gpio_pin_set(LED_PIN3);
		printf("led OK!\r\n");
		NRF_LOG_INFO("led red");	
}
//APP��ʱ���¼����������ú���������SAADC����
static void battery_level_meas_timeout_handler(void * p_context)
{
    UNUSED_PARAMETER(p_context);

    ret_code_t err_code;
    err_code = nrf_drv_saadc_sample();
    APP_ERROR_CHECK(err_code);
}
//��ʼ��APP��ʱ��ģ��
static void timers_init(void)
{
    //��ʼ��APP��ʱ��ģ��
    ret_code_t err_code = app_timer_init();
	  //��鷵��ֵ
    APP_ERROR_CHECK(err_code);

    //������ز���APP��ʱ��
    err_code = app_timer_create(&m_battery_timer_id,
                                APP_TIMER_MODE_REPEATED,
                                battery_level_meas_timeout_handler);
    APP_ERROR_CHECK(err_code);  

}
static void log_init(void)
{
    //��ʼ��log����ģ��
	  ret_code_t err_code = NRF_LOG_INIT(NULL);
    APP_ERROR_CHECK(err_code);
    //����log����նˣ�����sdk_config.h�е�������������ն�ΪUART����RTT��
    NRF_LOG_DEFAULT_BACKENDS_INIT();
}

//����״̬�����������û�й������־��������˯��ֱ����һ���¼���������ϵͳ
static void idle_state_handle(void)
{
    //��������log
	  if (NRF_LOG_PROCESS() == false)
    {
        //���е�Դ�����ú�����Ҫ�ŵ���ѭ������ִ��
			  nrf_pwr_mgmt_run();
    }
}
//�����㲥���ú������õ�ģʽ����͹㲥��ʼ�������õĹ㲥ģʽһ��
static void advertising_start(void)
{
   //ʹ�ù㲥��ʼ�������õĹ㲥ģʽ�����㲥
	 ret_code_t err_code = ble_advertising_start(&m_advertising, BLE_ADV_MODE_FAST);
	 //��麯�����صĴ������
   APP_ERROR_CHECK(err_code);
}


//������
int main(void)
{
	//��ʼ��log����ģ��
	log_init();
	//��ʼ������
	uart_config();
	printf("uart init!\r\n");
	//��ʼ��APP��ʱ��
	timers_init();
	//???led
	leds_init();
	//��ʼ����Դ����
	power_management_init();
	//��ʼ��Э��ջ
	ble_stack_init();
	//��ʼ��SAADC
	adc_configure();
	//����GAP����
	gap_params_init();
	//��ʼ��GATT
	gatt_init();
	//��ʼ������
	services_init();
	//��ʼ���㲥
	advertising_init();	
	//���Ӳ���Э�̳�ʼ��
  conn_params_init();
	printf("BLE OK!\r\n");
	
  NRF_LOG_INFO("BLE Template example started.");  
	//�����㲥
	advertising_start();
	pwm_common_init();
	
//  pwm_play_adjustable(50, 5);
//	pwm_play();
  //��ѭ��
	while(true)
	{
//		nrf_drv_saadc_sample();
//		nrf_delay_ms(1000);
		//��������LOG�����е�Դ����
		idle_state_handle();
	}
}

