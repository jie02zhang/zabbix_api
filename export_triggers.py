import pandas as pd
import logging
from pyzabbix import ZabbixAPI  # 导入 ZabbixAPI 类
from login_zabbix_api import login_zabbix_api
from search_hosts_api import get_host_info  # 假设代码1保存为 search_hosts_api.py

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def export_to_file(data: list, file_path: str, file_format: str = "csv"):
    """
    将数据导出到指定文件。
    :param data: 待导出的数据列表
    :param file_path: 文件路径
    :param file_format: 文件格式（支持 "csv" 或 "xlsx"）
    """
    try:
        df = pd.DataFrame(data)
        if file_format.lower() == "csv":
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
        elif file_format.lower() == "xlsx":
            df.to_excel(file_path, index=False, engine='openpyxl')
        else:
            raise ValueError("不支持的文件格式，仅支持 'csv' 和 'xlsx'")
        logging.info(f"数据成功导出到 {file_path}")
    except Exception as e:
        logging.exception(f"导出文件失败: {e}")
        raise

def search_and_export_by_trigger_and_template(
    zapi: ZabbixAPI, trigger_keyword: str, template_list: list, file_path: str, file_format: str = "csv"
):
    """
    根据触发器名称关键字和模板名称列表查询主机信息，并导出到文件。
    :param zapi: 已登录的 Zabbix API 对象
    :param trigger_keyword: 触发器名称关键字
    :param template_list: 模板名称列表
    :param file_path: 导出文件路径
    :param file_format: 导出文件格式（支持 'csv' 和 'xlsx'）
    """
    logging.info(f"开始查询主机，触发器关键字: {trigger_keyword}, 模板列表: {template_list}")
    all_data = []

    # 定义需要返回的字段列表
    return_fields = ["主机ID", "主机名称", "IP地址", "是否启用", "Trigger ID", "Trigger Name", "Trigger 是否启用"]

    for template_name in template_list:
        logging.info(f"查询模板名称: {template_name}")
        host_data = get_host_info(zapi, template_name=template_name, return_fields=return_fields)
        filtered_data = [host for host in host_data if trigger_keyword in host.get("Trigger Name", "")]
        all_data.extend(filtered_data)

    if not all_data:
        logging.warning("未查询到匹配的主机信息")
        return

    export_to_file(all_data, file_path, file_format)

if __name__ == "__main__":
    try:
        # 登录 Zabbix API
        zapi = login_zabbix_api()

        # 配置查询参数
        trigger_keyword = "Ping"
        template_list = ["Envision_Temp_ZBX_Linux_Baseline", "Envision_Temp_ZBX_Windows_Baseline"]
        file_path = "C:\\software\\all_triggers_Ping_info.xlsx"
        file_format = "xlsx"  # 可选 "csv" 或 "xlsx"

        # 查询并导出
        search_and_export_by_trigger_and_template(
            zapi, trigger_keyword, template_list, file_path, file_format
        )
    except Exception as e:
        logging.exception(f"脚本执行失败: {e}")