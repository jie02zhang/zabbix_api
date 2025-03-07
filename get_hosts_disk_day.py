import pandas as pd
import re
from datetime import datetime
import logging
from tqdm import tqdm  # 添加进度条库
from search_hosts_api import search_hosts_by_template
from login_zabbix_api import login_zabbix_api

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_daily_disk_peak(zapi, start_date_str, end_date_str, output_file):
    """
    获取指定时间段内所有使用Windows或Linux模板主机的磁盘使用率峰值
    
    :param zapi: Zabbix API连接对象
    :param start_date_str: 起始日期(格式: YYYYMMDD)
    :param end_date_str: 结束日期(格式: YYYYMMDD)
    :param output_file: 输出文件路径
    """
    # 时间格式转换
    try:
        start_date = datetime.strptime(start_date_str, "%Y%m%d")
        end_date = datetime.strptime(end_date_str + " 23:59:59", "%Y%m%d %H:%M:%S")
        start_ts = int(start_date.timestamp())
        end_ts = int(end_date.timestamp())
    except ValueError as e:
        logging.error(f"日期格式错误: {e}")
        return False

    # 获取目标主机列表
    templates = [
        "Envision_Temp_ZBX_Windows_Baseline",
        "Envision_Temp_ZBX_Linux_Baseline"
    ]
    
    host_map = {}
    logging.info("开始获取模板主机列表...")
    for template in templates:
        try:
            hosts = search_hosts_by_template(zapi, template)
            logging.info(f"模板 {template} 找到 {len(hosts)} 台主机")
            for host in hosts:
                host_id = host['主机ID']
                if host_id not in host_map:
                    host_map[host_id] = {
                        'ip': host['IP地址'],
                        'items': []
                    }
        except Exception as e:
            logging.error(f"获取模板 {template} 主机失败: {e}")

    # 获取各主机的磁盘监控项
    total_hosts = len(host_map)
    logging.info(f"开始获取磁盘监控项，共 {total_hosts} 台主机需要处理...")
    for idx, (host_id, host_info) in enumerate(tqdm(host_map.items(), desc="获取监控项"), 1):
        try:
            items = zapi.item.get(
                hostids=host_id,
                search={"key_": "pused"},
                output=["itemid", "key_", "name"]
            )
            valid_items = [item for item in items if 'vfs.fs.size' in item['key_']]
            host_info['items'] = valid_items
            logging.debug(f"主机 {host_info['ip']} 找到 {len(valid_items)} 个磁盘监控项")
        except Exception as e:
            logging.error(f"获取主机 {host_info['ip']} 监控项失败: {e}")

    # 获取历史数据并处理
    results = []
    total_items = sum(len(host['items']) for host in host_map.values())
    logging.info(f"开始获取历史数据，共 {total_items} 个监控项需要处理...")
    
    with tqdm(total=total_items, desc="处理进度") as pbar:
        for host_id, host_info in host_map.items():
            if not host_info['items']:
                continue

            for item in host_info['items']:
                # 更新进度条
                pbar.update(1)
                pbar.set_postfix_str(f"当前主机: {host_info['ip']}")
                
                # 解析目录名称
                match = re.match(r'vfs\.fs\.size\[(.*?),pused\]', item['key_'])
                if not match:
                    continue
                mount_point = match.group(1)

                # 获取历史数据
                try:
                    history = zapi.history.get(
                        itemids=item['itemid'],
                        time_from=start_ts,
                        time_till=end_ts,
                        output=['clock', 'value'],
                        history=0,
                        sortfield='clock',
                        sortorder='ASC'
                    )
                except Exception as e:
                    logging.error(f"获取 {item['key_']} 历史数据失败: {e}")
                    continue

                if not history:
                    logging.debug(f"{host_info['ip']} 的 {mount_point} 无历史数据")
                    continue

                # 处理数据
                try:
                    df = pd.DataFrame(history)
                    df['clock'] = pd.to_numeric(df['clock'])
                    df['value'] = pd.to_numeric(df['value'])
                    df['date'] = pd.to_datetime(df['clock'], unit='s').dt.strftime('%Y%m%d')
                    daily_max = df.groupby('date')['value'].max().reset_index()

                    for _, row in daily_max.iterrows():
                        results.append({
                            "IP地址": host_info['ip'],
                            "日期": row['date'],
                            "目录名称": mount_point,
                            "磁盘使用率峰值(%)": round(row['value'], 2)
                        })
                except Exception as e:
                    logging.error(f"数据处理失败: {e}")
                    continue

    # 生成报告
    if results:
        try:
            df = pd.DataFrame(results)
            df.sort_values(by=['IP地址', '日期', '目录名称'], inplace=True)
            
            # 添加数据去重
            initial_count = len(df)
            df.drop_duplicates(inplace=True)
            if initial_count != len(df):
                logging.warning(f"移除 {initial_count - len(df)} 条重复记录")
                
            df.to_excel(output_file, index=False)
            logging.info(f"成功生成报告，共 {len(df)} 条记录，保存至: {output_file}")
            return True
        except Exception as e:
            logging.error(f"生成报告失败: {e}")
            return False
    else:
        logging.warning("未找到符合条件的监控数据")
        return False

if __name__ == "__main__":
    try:
        zapi = login_zabbix_api()
        logging.info("Zabbix API 登录成功")
        
        success = get_daily_disk_peak(
            zapi=zapi,
            start_date_str="20250301",
            end_date_str="20250307",
            output_file=r"C:\software\daily_disk_peak.xlsx"
        )

        if success:
            print("操作成功完成")
        else:
            print("操作未完成，请检查日志")
    except Exception as e:
        logging.error(f"程序初始化失败: {e}")