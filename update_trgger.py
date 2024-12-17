from update_trigger_api import update_triggers, login_zabbix_api

def some_other_function():
    zabbix_api = login_zabbix_api()
    host_name = "10.93.203.58"
    trigger_name = "Ping 连续三次不通"
    trigger_status = 1  # 0: 启用, 1: 禁用
    update_triggers(zabbix_api, host_name=host_name, trigger_name=trigger_name, trigger_status=trigger_status)

if __name__ == "__main__":
    some_other_function()