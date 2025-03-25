from login_zabbix_api import login_zabbix_api
import json

def get_proxy_info(agent_name):
    # 登录 Zabbix API
    zapi = login_zabbix_api()

    # 获取指定名称的代理服务器信息
    proxies = zapi.proxy.get(filter={"host": agent_name}, output=["proxyid", "host"])

    if proxies:  # 如果找到符合条件的代理服务器信息
        proxy_info = {
            "agent_name": agent_name,
            "proxy_id": proxies[0]["proxyid"],
            "host": proxies[0]["host"]
        }
        return json.dumps(proxy_info)  # 返回代理服务器信息的JSON格式
    else:
        return json.dumps({})  # 如果未找到符合条件的代理服务器信息，则返回空的JSON对象

# # 调用函数并打印结果
# agent_name = "Proxy_JY_RD001"  # 传入代理 Agent 名称
# proxy_info_json = get_proxy_info(agent_name)
# print(proxy_info_json)