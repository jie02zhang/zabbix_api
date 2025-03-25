import json
from login_zabbix_api import login_zabbix_api

def get_hostgroup_info(group_name):
    # 登录 Zabbix API
    zapi = login_zabbix_api()

    # 获取主机组信息
    groups = zapi.hostgroup.get(filter={"name": group_name}, output=["groupid", "name"])

    if groups:  # 如果找到符合条件的主机组信息
        group_info = {
            "group_id": groups[0]["groupid"],
            "name": groups[0]["name"]
        }
        return json.dumps(group_info)  # 返回主机组信息的 JSON 格式字符串
    else:
        return json.dumps({})  # 如果未找到符合条件的主机组信息，则返回空的 JSON 对象

# # 调用函数并打印结果
# group_name = "硬件_Dell"  # 传入群组的名称
# group_info_json = get_hostgroup_info(group_name)
# print(group_info_json)