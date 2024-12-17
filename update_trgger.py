from update_trigger_api import update_triggers, login_zabbix_api
import pandas as pd
import logging

# 设置日志记录格式
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def some_other_function():
    zabbix_api = login_zabbix_api()
    file_path = "C:\\software\\hosts.xlsx"
    trigger_name = "Ping 连续三次不通"
    trigger_value = 0  # 0: 正常, 1: 问题
    trigger_status = 0  # 0: 启用, 1: 禁用


    try:
        df = pd.read_excel(file_path)
        if '主机名称' not in df.columns:
            logging.error(f"Excel 文件 {file_path} 中没有 '主机名称' 列")
            return

        host_names = df['主机名称'].dropna().unique()
        for host_name in host_names:
            logging.info(f"处理主机: {host_name}")
            update_triggers(zabbix_api, host_name=host_name, trigger_name=trigger_name, trigger_value=trigger_value, trigger_status=trigger_status)
    except Exception as e:
        logging.error(f"处理 Excel 文件 {file_path} 时发生错误: {e}")

if __name__ == "__main__":
    some_other_function()