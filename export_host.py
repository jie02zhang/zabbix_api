import pandas as pd
from login_zabbix_api import login_zabbix_api
from search_hosts_api import get_all_hosts, search_hosts_by_name

# 登录 Zabbix API
zabbix_api = login_zabbix_api()

if zabbix_api:
    # 查询所有主机
    all_hosts_info = get_all_hosts(zabbix_api)
    print(f"查询到 {len(all_hosts_info)} 台主机。")

    # # 根据主机名称模糊查询
    # filtered_hosts_info = search_hosts_by_name(zabbix_api, keyword="10.123")
    # print(filtered_hosts_info)

    # 导出为 Excel 文件
    output_file = r"C:\software\应用系统监控管理-Zabbix-01.xlsx"
    df_all = pd.DataFrame(all_hosts_info)
    df_all.to_excel(output_file, index=False, sheet_name="All Hosts")
    print(f"主机信息已成功导出到 '{output_file}'")
else:
    print("登录 Zabbix API 失败，请检查配置或网络连接。")