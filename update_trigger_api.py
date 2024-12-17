import logging
import pandas as pd
import json
import argparse
from login_zabbix_api import login_zabbix_api

# 设置日志记录格式
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

STATUS_MAP = {"0": "正常", "1": "问题"}
VALUE_MAP = {"0": "启用", "1": "禁用"}

def get_host_id_by_name(zabbix_api, host_name):
    try:
        host_info = zabbix_api.host.get(filter={"host": host_name}, output=["hostid", "name", "host"])
        logging.debug(f"通过主机名 {host_name} 获取到的主机信息: {host_info}")
        if not host_info:
            logging.warning(f"主机名 {host_name} 的主机未找到")
            return None, None, None
        return host_info[0].get("hostid"), host_info[0].get("name", "未知Host Name"), host_info[0].get("host", "未知Host IP")
    except Exception as e:
        logging.error(f"通过主机名获取主机ID时发生错误: {e}")
        return None, None, None

def get_trigger_info(zabbix_api, host_id, host_name, host_ip, trigger_name=None):
    try:
        search_params = {"description": trigger_name} if trigger_name else {}
        triggers = zabbix_api.trigger.get(hostids=host_id, search=search_params, output=["triggerid", "description", "value", "status", "tags"])
        logging.debug(f"从 Zabbix API 获取到的触发器信息: {triggers}")

        trigger_info_list = []
        for trigger in triggers:
            tags = trigger.get("tags", [])
            tag_info = {
                "Host Name": host_name,
                "Host IP": host_ip,
                "Trigger ID": trigger.get("triggerid", "未知Trigger ID"),
                "Trigger Name": trigger.get("description", "未知Trigger Name"),
                "Trigger Status": STATUS_MAP.get(trigger.get("value"), "未知"),
                "Trigger Enabled": VALUE_MAP.get(trigger.get("status"), "未知"),
            }
            for tag in tags:
                tag_name = tag.get('tag')
                tag_value = tag.get('value')
                if tag_name in tag_info:
                    existing_value = tag_info[tag_name]
                    if isinstance(existing_value, list):
                        tag_info[tag_name].append(tag_value)
                    else:
                        tag_info[tag_name] = [existing_value, tag_value]
                else:
                    tag_info[tag_name] = tag_value

            trigger_info_list.append(tag_info)
        return trigger_info_list
    except Exception as e:
        logging.error(f"从 Zabbix API 获取触发器信息时发生错误: {e}")
        return []

def process_hosts_from_excel(file_path, zabbix_api, trigger_name=None):
    try:
        df = pd.read_excel(file_path)
        if 'Host Name' not in df.columns:
            logging.error("Excel 文件中没有 'Host Name' 列")
            return []

        host_names = df['Host Name'].dropna().unique()
        all_trigger_info = []

        for host_name in host_names:
            host_id, host_name_resolved, host_ip = get_host_id_by_name(zabbix_api, host_name)
            if host_id:
                trigger_info = get_trigger_info(zabbix_api, host_id, host_name_resolved, host_ip, trigger_name)
                all_trigger_info.extend(trigger_info)

        return all_trigger_info
    except Exception as e:
        logging.error(f"处理 Excel 文件时发生错误: {e}")
        return []

def update_trigger_status(zabbix_api, trigger_id, status):
    try:
        result = zabbix_api.trigger.update({
            'triggerid': trigger_id,
            'status': status
        })
        if 'error' in result:
            logging.error(f"更新触发器 ID: {trigger_id} 状态为 {status} 时发生错误: {result['error']}")
        else:
            logging.info(f"成功更新触发器 ID: {trigger_id} 状态为 {status}, 更新结果: {result}")
    except Exception as e:
        logging.error(f"更新触发器 ID: {trigger_id} 状态为 {status} 时发生错误: {e}")

def update_triggers(zabbix_api, host_name=None, file_path=None, trigger_name=None, trigger_status=None):
    if host_name and file_path:
        logging.error("请仅输入主机名或 Excel 文件路径，不能同时输入两者")
        return

    if not host_name and not file_path:
        logging.error("请输入主机名或 Excel 文件路径")
        return

    if file_path:
        trigger_info = process_hosts_from_excel(file_path, zabbix_api, trigger_name)
    elif host_name:
        host_id, host_name_resolved, host_ip = get_host_id_by_name(zabbix_api, host_name)
        if host_id:
            trigger_info = get_trigger_info(zabbix_api, host_id, host_name_resolved, host_ip, trigger_name)
        else:
            trigger_info = []

    if trigger_info:
        for index, info in enumerate(trigger_info):
            print(f"{index + 1}: {json.dumps(info, ensure_ascii=False, indent=4)}")

        if trigger_status is not None:
            for info in trigger_info:
                trigger_id = info.get("Trigger ID")
                if trigger_id:
                    update_trigger_status(zabbix_api, trigger_id, trigger_status)
    else:
        logging.info("未找到任何触发器信息")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zabbix API Trigger Information Exporter and Controller")
    parser.add_argument('--host-name', type=str, help='输入主机名 (可空)')
    parser.add_argument('--file-path', type=str, help='输入 Excel 文件路径 (如果输入主机名则不需要)')
    parser.add_argument('--trigger-name', type=str, help='输入触发器名称 (可空)')
    parser.add_argument('--trigger-status', type=int, choices=[0, 1], help='设置触发器状态 (0: 启用, 1: 禁用)')

    args = parser.parse_args()
    zabbix_api = login_zabbix_api()

    update_triggers(zabbix_api, args.host_name, args.file_path, args.trigger_name, args.trigger_status)