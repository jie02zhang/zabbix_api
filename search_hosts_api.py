import pandas as pd
import logging
from pyzabbix import ZabbixAPI

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_host_info(zapi: ZabbixAPI, host_name: str = None, ip_address: str = None, keyword: str = None, template_name: str = None, group_name: str = None, proxy_name: str = None, return_fields: list = None) -> list:
    """
    获取主机的详细信息，可通过主机名称、IP 地址、关键字、模板名称、组名称、代理名称筛选，并决定返回哪些字段。
    :param zapi: 登录后的 Zabbix API 对象
    :param host_name: 筛选主机名称（可选）
    :param ip_address: 筛选主机 IP 地址（可选）
    :param keyword: 筛选主机关键字（可选）
    :param template_name: 筛选模板名称（可选）
    :param group_name: 筛选组名称（可选）
    :param proxy_name: 筛选代理名称（可选）
    :param return_fields: 返回的字段列表（可选，默认为 ["主机ID", "主机名称", "可见名称", "IP地址", "是否启用", "接口类型", "组信息", "模板信息", "代理信息", "Trigger ID", "Trigger Name", "Trigger 是否启用"）
    :return: 主机信息列表
    """
    logging.info("开始获取主机信息")

    # 定义默认返回字段
    default_return_fields = ["主机ID", "主机名称", "可见名称", "IP地址", "是否启用", "接口类型", "组信息", "模板信息", "代理信息", "Trigger ID", "Trigger Name", "Trigger 是否启用"]
    return_fields = return_fields or default_return_fields

    # 获取代理信息缓存
    proxy_info_cache = {}
    try:
        proxies = zapi.proxy.get(output=["proxyid", "host"])
        proxy_info_cache = {proxy["proxyid"]: {"代理ID": proxy["proxyid"], "代理名称": proxy["host"]} for proxy in proxies}
    except Exception as e:
        logging.exception("获取代理信息失败")
        proxy_info_cache = {"无代理ID": {"代理ID": "无代理ID", "代理名称": "无代理名称"}}

    # 定义筛选条件
    params = {
        "output": ["hostid", "host", "name", "status", "proxy_hostid"],
        "selectInterfaces": ["ip", "type"],
        "selectGroups": "extend",
        "selectParentTemplates": "extend",
        "selectTriggers": "extend"
    }

    if host_name:
        params.setdefault("filter", {})["host"] = host_name
    if ip_address:
        params.setdefault("filter", {}).setdefault("ip", []).append(ip_address)
    if keyword:
        params["search"] = {"host": keyword, "name": keyword}
    if template_name:
        template_ids = [template["templateid"] for template in zapi.template.get(output=["templateid"], search={"name": template_name})]
        params["templateids"] = template_ids
    if group_name:
        group_ids = [group["groupid"] for group in zapi.hostgroup.get(output=["groupid"], search={"name": group_name})]
        params["groupids"] = group_ids
    if proxy_name:
        proxy_ids = [proxy["proxyid"] for proxy in zapi.proxy.get(output=["proxyid"], search={"host": proxy_name})]
        params["proxyids"] = proxy_ids

    # 请求 Zabbix API
    try:
        host_info = zapi.do_request(method="host.get", params=params).get("result", [])
    except Exception as e:
        logging.exception("Zabbix API 请求失败")
        raise Exception("Zabbix API 请求失败: {}".format(str(e)))

    # 结果列表
    all_host_info = []

    for host in host_info:
        # 主机基础信息
        host_id = host.get("hostid", "").strip()
        host_name_actual = host.get("host", "").strip()
        visible_name = host.get("name", "").strip()
        status = "启用" if host.get("status") == "0" else "禁用"

        # 获取主机接口信息
        ip, interface_type = get_host_interface_info(host)

        # 获取主机组信息
        group_info = get_host_group_info(host)

        # 获取主机模板信息
        template_info = get_host_template_info(host)

        # 获取代理信息
        proxy_info = get_host_proxy_info(host, proxy_info_cache)

        # 获取主机触发器信息
        triggers = get_host_trigger_info(host)

        for trigger in triggers:
            # 组合主机信息和触发器信息
            host_data = {
                "主机ID": host_id,
                "主机名称": host_name_actual,
                "可见名称": visible_name,
                "IP地址": ip,
                "是否启用": status,
                "接口类型": interface_type,
                "组信息": group_info,
                "模板信息": template_info,
                "代理信息": proxy_info,
                "Trigger ID": trigger.get("triggerid", "未知Trigger ID"),
                "Trigger Name": trigger.get("description", "未知Trigger Name"),
                "Trigger 是否启用": "启用" if trigger.get("status") == "0" else "禁用",
            }

            # 仅返回需要的字段
            host_data = {field: host_data[field] for field in return_fields if field in host_data}
            all_host_info.append(host_data)

    return all_host_info

def get_host_interface_info(host: dict) -> tuple:
    """
    获取主机接口信息。
    :param host: 主机信息字典
    :return: (IP地址, 接口类型)
    """
    ip = "无IP地址"
    interface_type = "无类型"
    for interface in host.get("interfaces", []):
        if interface.get("ip", "").strip():
            ip = interface["ip"]
            interface_type = "Zabbix Agent" if interface.get("type") == "1" else "SNMP"
            break
    return ip, interface_type

def get_host_group_info(host: dict) -> list:
    """
    获取主机组信息。
    :param host: 主机信息字典
    :return: 组信息列表
    """
    return [{"组ID": group.get("groupid", "未知组ID"), "组名称": group.get("name", "未知组名称")} for group in host.get("groups", [])]

def get_host_template_info(host: dict) -> list:
    """
    获取主机模板信息。
    :param host: 主机信息字典
    :return: 模板信息列表
    """
    return [{"模板ID": template.get("templateid", "未知模板ID"), "模板名称": template.get("name", "未知模板名称")} for template in host.get("parentTemplates", [])]

def get_host_proxy_info(host: dict, proxy_info_cache: dict) -> dict:
    """
    获取主机代理信息。
    :param host: 主机信息字典
    :param proxy_info_cache: 代理信息缓存
    :return: 代理信息字典
    """
    proxy_hostid = host.get("proxy_hostid", None)
    return proxy_info_cache.get(proxy_hostid, {"代理ID": "无代理ID", "代理名称": "无代理名称"})

def get_host_trigger_info(host: dict) -> list:
    """
    获取主机触发器信息。
    :param host: 主机信息字典
    :return: 触发器信息列表
    """
    triggers = host.get("triggers", [])
    if not triggers:
        return [{"Trigger ID": "N/A", "Trigger Name": "N/A", "Trigger 是否启用": "N/A"}]
    return triggers

def search_hosts_by_name(zapi: ZabbixAPI, keyword: str, return_fields: list = None) -> list:
    """
    根据主机名称模糊查询所有主机。
    :param zapi: 登录后的 Zabbix API 对象
    :param keyword: 模糊查询的主机关键字
    :param return_fields: 返回的字段列表（可选，默认为 None，使用 get_host_info 的默认字段列表）
    :return: 匹配的主机信息列表
    """
    logging.info(f"根据主机名称模糊查询关键字: {keyword}")
    return get_host_info(zapi, keyword=keyword, return_fields=return_fields)

def get_all_hosts(zapi: ZabbixAPI, return_fields: list = None) -> list:
    """
    默认查询所有主机。
    :param zapi: 登录后的 Zabbix API 对象
    :param return_fields: 返回的字段列表（可选，默认为 None，使用 get_host_info 的默认字段列表）
    :return: 所有主机的信息列表
    """
    logging.info("查询所有主机")
    return get_host_info(zapi, return_fields=return_fields)

def search_hosts_by_template(zapi: ZabbixAPI, template_name: str, return_fields: list = None) -> list:
    """
    根据模板名称查询所有相关的主机。
    :param zapi: 登录后的 Zabbix API 对象
    :param template_name: 模糊查询的模板名称
    :param return_fields: 返回的字段列表（可选，默认为 None，使用 get_host_info 的默认字段列表）
    :return: 匹配的主机信息列表
    """
    logging.info(f"根据模板名称查询关键字: {template_name}")
    return get_host_info(zapi, template_name=template_name, return_fields=return_fields)

def search_hosts_by_group(zapi: ZabbixAPI, group_name: str, return_fields: list = None) -> list:
    """
    根据组名称查询所有相关的主机。
    :param zapi: 登录后的 Zabbix API 对象
    :param group_name: 模糊查询的组名称
    :param return_fields: 返回的字段列表（可选，默认为 None，使用 get_host_info 的默认字段列表）
    :return: 匹配的主机信息列表
    """
    logging.info(f"根据组名称查询关键字: {group_name}")
    return get_host_info(zapi, group_name=group_name, return_fields=return_fields)

def search_hosts_by_proxy(zapi: ZabbixAPI, proxy_name: str, return_fields: list = None) -> list:
    """
    根据代理名称查询所有相关的主机。
    :param zapi: 登录后的 Zabbix API 对象
    :param proxy_name: 模糊查询的代理名称
    :param return_fields: 返回的字段列表（可选，默认为 None，使用 get_host_info 的默认字段列表）
    :return: 匹配的主机信息列表
    """
    logging.info(f"根据代理名称查询关键字: {proxy_name}")
    return get_host_info(zapi, proxy_name=proxy_name, return_fields=return_fields)