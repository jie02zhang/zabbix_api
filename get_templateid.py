import json
from login_zabbix_api import login_zabbix_api

def get_template_info(template_name, zapi=None):
    """
    根据模板名称查询模板信息

    Args:
        template_name (str): 模板名称
        zapi (ZabbixAPI, optional): Zabbix API 的连接对象。如果未提供，则会自动登录 Zabbix API。

    Returns:
        str: 包含模板信息的 JSON 格式字符串
    """
    try:
        if zapi is None:
            # 登录 Zabbix API
            zapi = login_zabbix_api()
        
        # 获取模板信息
        templates = zapi.template.get(filter={"host": template_name}, output=["templateid", "name"])

        if templates:  # 如果找到符合条件的模板信息
            template_info = {
                "template_id": templates[0]["templateid"],
                "name": templates[0]["name"]
            }
            return json.dumps(template_info)  # 返回模板信息的 JSON 格式字符串
        else:
            return json.dumps({})  # 如果未找到符合条件的模板信息，则返回空的 JSON 对象
    except Exception as e:
        print(f"Failed to get template info: {e}")
        return json.dumps({})  # 返回空的 JSON 对象

# # # # # 查询名为 "Envision_Temp_web_status_A00006_Baseline" 的模板信息
# template_name = "Template_Envision_ICMPPing_Standard"
# template_info_json = get_template_info(template_name)
# print(f"Template Info: {template_info_json}")


