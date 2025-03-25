"""
Zabbix 主机自动创建脚本（优化版）

根据Excel中的系统类型动态创建主机，支持多模板及智能主机名生成。
"""

import json
import pandas as pd
import requests
from login_zabbix_api import login_zabbix_api
from get_hostgroup_info import get_hostgroup_info
from get_templateid import get_template_info
from get_proxy_info import get_proxy_info

# 接口类型常量
INTERFACE_AGENT = 1
INTERFACE_SNMP = 2

# 配置参数（根据实际修改）
CONFIG = {
    "excel_columns": {  
        "host_ip": "IP地址",
        "proxy_name": "Proxy代理主机",
        "brand": "品牌",
        "model": "型号",
        "system_type": "系统类型"
    },
    "interface_ports": {  
        "agent": "10050",
        "snmp": "161"
    },
    "snmp_community": "{$SNMP_COMMUNITY}",  
}

def read_host_info_from_excel(file_path):
    """读取并验证Excel数据"""
    try:
        df = pd.read_excel(file_path)
        required_cols = [
            CONFIG["excel_columns"][col] 
            for col in ["host_ip", "proxy_name", "system_type", "brand"]
        ]
        missing = [col for col in required_cols if col not in df.columns]
        if missing:
            raise ValueError(f"缺少必要列: {', '.join(missing)}")
        return df.where(pd.notnull(df), None)  # 转换NaN为None
    except Exception as e:
        raise RuntimeError(f"读取Excel失败: {e}")

def build_host_interface(host_type, host_ip):
    """构建监控接口配置"""
    interface = {
        "type": INTERFACE_AGENT if host_type == "agent" else INTERFACE_SNMP,
        "main": 1,
        "useip": 1,
        "ip": host_ip,
        "dns": "",
        "port": CONFIG["interface_ports"][host_type]
    }
    if host_type == "snmp":
        interface["details"] = {
            "version": 2,
            "bulk": 1,
            "community": CONFIG["snmp_community"]
        }
    return interface

def create_host_params(row, host_type, template_id, group_id, zapi_auth):
    """构造主机创建请求参数（修复参数错误）"""
    try:
        host_ip = row[CONFIG["excel_columns"]["host_ip"]]
        if not host_ip:
            raise ValueError("IP地址不能为空")
    except KeyError:
        raise ValueError("Excel数据格式错误，缺少IP地址列")
    
    proxy_name = row.get(CONFIG["excel_columns"]["proxy_name"], None)
    
    # 生成主机可见名称
    brand = row.get(CONFIG["excel_columns"]["brand"], "Unknown") or "Unknown"
    model = row.get(CONFIG["excel_columns"]["model"], "") or ""
    visible_name = f"{host_ip}_{brand}_{model}" if model else f"{host_ip}_{brand}"
    
    # 获取代理ID（修复参数错误）
    proxy_id = None
    if proxy_name:
        try:
            # 修复：移除多余的zapi参数
            proxy_info = json.loads(get_proxy_info(proxy_name))
            if 'proxy_id' not in proxy_info:
                raise ValueError(f"代理{proxy_name}不存在")
            proxy_id = proxy_info["proxy_id"]
        except Exception as e:
            raise ValueError(f"获取代理ID失败: {e}")
    
    # 构建请求体
    params = {
        "jsonrpc": "2.0",
        "method": "host.create",
        "params": {
            "host": host_ip,
            "name": visible_name,
            "interfaces": [build_host_interface(host_type, host_ip)],
            "groups": [{"groupid": group_id}],
            "templates": [{"templateid": template_id}],
            "status": 0
        },
        "auth": zapi_auth,
        "id": 1
    }
    if proxy_id:
        params["params"]["proxy_hostid"] = proxy_id  # 修正Zabbix API参数名
    
    return params

def create_hosts(file_path, group_name, snmp_template, agent_template):
    """批量创建主入口函数（增强异常处理）"""
    # 初始化API连接
    try:
        zapi = login_zabbix_api()
    except Exception as e:
        return [{"status": "error", "message": f"API登录失败: {e}"}]
    
    # 验证依赖项
    try:
        group_info = json.loads(get_hostgroup_info(group_name))
        group_id = group_info["group_id"]
        snmp_info = json.loads(get_template_info(snmp_template))
        snmp_tid = snmp_info["template_id"]
        agent_info = json.loads(get_template_info(agent_template))
        agent_tid = agent_info["template_id"]
    except Exception as e:
        return [{"status": "error", "message": f"配置验证失败: {e}"}]
    
    # 读取数据
    try:
        df = read_host_info_from_excel(file_path)
    except Exception as e:
        return [{"status": "error", "message": str(e)}]
    
    results = []
    for index, row in df.iterrows():
        host_ip = row.get(CONFIG["excel_columns"]["host_ip"], "未知主机")
        try:
            # 确定监控类型
            sys_type_raw = row[CONFIG["excel_columns"]["system_type"]]
            sys_type = sys_type_raw.strip().lower() if sys_type_raw else None
            if sys_type not in ["snmp", "agent"]:
                raise ValueError(f"无效监控类型: {sys_type_raw}")
            
            # 选择模板
            template_id = snmp_tid if sys_type == "snmp" else agent_tid
            
            # 构建请求参数
            params = create_host_params(
                row, sys_type, template_id, group_id, zapi.auth
            )
            
            # 发送请求
            resp = requests.post(
                zapi.url, 
                headers={"Content-Type": "application/json-rpc"},
                json=params,
                timeout=10
            ).json()
            
            if "error" in resp:
                error_msg = f"{resp['error']['code']}: {resp['error']['data']}"
                results.append({"status": "error", "host": host_ip, "message": error_msg})
            else:
                results.append({
                    "status": "success",
                    "host": host_ip,
                    "hostid": resp["result"]["hostids"][0]
                })
        except Exception as e:
            results.append({
                "status": "error",
                "host": host_ip,
                "message": f"第{index+2}行处理失败: {str(e)}"
            })
    return results

if __name__ == "__main__":
    
    results = create_hosts(
        file_path="C:\\software\\host_info-20240325.xlsx",
        group_name="Poly话机",
        snmp_template="Template_Envision_SNMPGeneral",
        agent_template="Envision_Temp_ICMPPing_Baseline"
    )
    
    print("\n创建结果:")
    for res in results:
        status_icon = "✅" if res["status"] == "success" else "❌"
        print(f"{status_icon} {res['host']}: {res.get('message', '创建成功')}")