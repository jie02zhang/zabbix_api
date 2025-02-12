import csv
from datetime import datetime, timedelta
from pytz import timezone
from login_zabbix_api import login_zabbix_api

# 登录到 Zabbix API
zapi = login_zabbix_api()

# 自定义维护名称前缀，可以根据需要修改
MAINTENANCE_NAME_PREFIX = "自定义维护名称"

def get_host_id_by_ip(ip_address):
    """
    根据 IP 地址获取 Zabbix 中的主机 ID
    :param ip_address: 主机的 IP 地址
    :return: 主机 ID 或 None（如果未找到主机）
    """
    try:
        hosts = zapi.host.get(filter={"ip": ip_address}, output=["hostid"])
        if hosts:
            return hosts[0]['hostid']
        else:
            print(f"No host found with IP address {ip_address}")
            return None
    except Exception as e:
        print(f"Error getting host ID for {ip_address}: {e}")
        return None

def maintenance_exists(maintenance_name):
    """
    检查指定名称的维护是否已经存在
    :param maintenance_name: 维护名称
    :return: True 如果存在，否则 False
    """
    try:
        maintenances = zapi.maintenance.get(filter={"name": maintenance_name})
        return bool(maintenances)
    except Exception as e:
        print(f"Error checking maintenance existence for {maintenance_name}: {e}")
        return False

def create_maintenance(start_time, end_time, host_ids, maintenance_name):
    """
    创建 Zabbix 中的维护模式，如果同名维护已存在，则跳过创建
    :param start_time: 维护开始的本地时间
    :param end_time: 维护结束的本地时间
    :param host_ids: 主机 ID 的列表
    :param maintenance_name: 维护模式的名称
    :return: 维护模式 ID 或 None（如果创建失败）
    """
    try:
        tz = timezone('Asia/Shanghai')
        start_time_unix = int(tz.localize(start_time).timestamp())
        end_time_unix = int(tz.localize(end_time).timestamp())

        # 如果同名维护已经存在，则跳过创建
        if maintenance_exists(maintenance_name):
            print(f"Maintenance '{maintenance_name}' already exists. Skipping creation.")
            return

        maintenance_id = zapi.maintenance.create({
            "name": maintenance_name,
            "active_since": start_time_unix,
            "active_till": end_time_unix,
            "hostids": host_ids,
            "timeperiods": [{
                "timeperiod_type": 0,  # 指定时间范围
                "start_date": start_time_unix,
                "period": end_time_unix - start_time_unix
            }]
        })
        print(f"Created maintenance '{maintenance_name}' with ID: {maintenance_id}")
        return maintenance_id
    except Exception as e:
        print(f"Error creating maintenance '{maintenance_name}': {e}")
        return None

def parse_time(date_str, time_str):
    """
    解析时间，处理 '24:00' 为次日的 '00:00'
    :param date_str: 日期字符串，格式为 'YYYY/MM/DD'
    :param time_str: 时间字符串，格式为 'HH:MM' 或 '24:00'
    :return: 解析后的 datetime 对象
    """
    if time_str == "24:00":
        # 直接返回日期加一天的 00:00
        return datetime.strptime(date_str, '%Y/%m/%d') + timedelta(days=1)
    return datetime.strptime(f"{date_str} {time_str}", '%Y/%m/%d %H:%M')

def read_and_process_csv(file_path):
    """
    读取 CSV 文件，解析数据并创建维护模式
    :param file_path: CSV 文件路径
    """
    try:
        # 用于存储同一时间段下对应的主机 ID 列表，避免重复创建维护
        maintenance_dict = {}

        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            next(reader)  # 跳过表头
            for row in reader:
                ip_address, time_range_str = row[0], row[1]

                # 分离日期和时间范围
                date_str, time_range = time_range_str.split(' ')
                start_time_str, end_time_str = time_range.split('-')

                # 解析开始和结束时间
                start_time = parse_time(date_str, start_time_str)
                end_time = parse_time(date_str, end_time_str)

                # 如果结束时间小于等于开始时间，说明跨天，需要加一天
                if end_time <= start_time:
                    end_time += timedelta(days=1)

                # 在原始时间上提前 30 分钟开始，延后 30 分钟结束
                start_time_adjusted = start_time - timedelta(minutes=30)
                end_time_adjusted = end_time + timedelta(minutes=30)

                # 生成维护名称（自定义前缀 + 时间范围），便于区分
                maintenance_name = f"{MAINTENANCE_NAME_PREFIX}-{start_time_adjusted.strftime('%Y-%m-%d %H:%M')}-{end_time_adjusted.strftime('%Y-%m-%d %H:%M')}"

                # 将相同时间段的主机归为一组
                maintenance_dict.setdefault((start_time_adjusted, end_time_adjusted, maintenance_name), []).append(get_host_id_by_ip(ip_address))

        # 遍历所有时间段，创建维护模式
        for (start_time, end_time, maintenance_name), host_ids in maintenance_dict.items():
            # 过滤掉 None 值
            host_ids = [host_id for host_id in host_ids if host_id is not None]
            if host_ids:
                create_maintenance(start_time, end_time, host_ids, maintenance_name)

    except Exception as e:
        print(f"Error processing CSV file: {e}")

# CSV 文件路径
csv_file_path = r'C:\software\maintenance.csv'

# 读取并处理 CSV 文件
read_and_process_csv(csv_file_path)
