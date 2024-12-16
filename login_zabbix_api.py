import pyzabbix
import configparser
import os
import logging
from typing import Optional

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def login_zabbix_server(server_url: str, username: str, password: str) -> Optional[pyzabbix.ZabbixAPI]:
    """
    登录Zabbix服务器，并返回Zabbix API实例。
    :param server_url: Zabbix服务器URL
    :param username: Zabbix用户名
    :param password: Zabbix密码
    :return: 如果登录成功，返回ZabbixAPI实例；否则返回None
    """
    try:
        # 初始化Zabbix API客户端
        zapi = pyzabbix.ZabbixAPI(server_url)
        zapi.login(username, password)
        logging.info("成功登录Zabbix API！")
        return zapi
    except pyzabbix.ZabbixAPIException as e:
        logging.error(f"Failed to login to Zabbix API: {e}")
        return None

def login_zabbix_api(config_file: str = "config.ini", config_section: str = "Zabbix") -> Optional[pyzabbix.ZabbixAPI]:
    """
    从配置文件读取登录参数并登录Zabbix API。
    :param config_file: 配置文件路径，默认为'config.ini'
    :param config_section: 配置文件中Zabbix登录信息所在的节名，默认为'Zabbix'
    :return: 如果登录成功，返回ZabbixAPI实例；否则返回None
    """
    # 从配置文件读取登录参数
    config = configparser.ConfigParser()
    config.read(config_file)

    if config_section not in config:
        logging.error(f"配置文件缺少节：{config_section}")
        return None

    zabbix_server: Optional[str] = config[config_section].get("ServerURL")
    zabbix_username: Optional[str] = config[config_section].get("Username")
    
    if not zabbix_server or not zabbix_username:
        logging.error("配置文件中缺少必要的参数：ServerURL或Username")
        return None

    # 使用环境变量获取密码，而不是硬编码在配置文件中
    zabbix_password: Optional[str] = os.getenv("ZABBIX_PASSWORD") or config[config_section].get("Password")

    if not zabbix_password:
        logging.error("无法获取密码，既没有环境变量也没有配置文件中的密码")
        return None

    if "ZABBIX_PASSWORD" not in os.environ:
        logging.warning("使用配置文件中的密码而不是环境变量。建议使用环境变量提高安全性。")

    return login_zabbix_server(zabbix_server, zabbix_username, zabbix_password)