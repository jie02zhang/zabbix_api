import pandas as pd
import re
from datetime import datetime
import logging
from tqdm import tqdm
from search_hosts_api import search_hosts_by_template
from login_zabbix_api import login_zabbix_api

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_daily_disk_peak(zapi, start_date_str, end_date_str, output_file):
    try:
        start_date = datetime.strptime(start_date_str, "%Y%m%d")
        end_date = datetime.strptime(end_date_str + " 23:59:59", "%Y%m%d %H:%M:%S")
        start_ts, end_ts = int(start_date.timestamp()), int(end_date.timestamp())
    except ValueError as e:
        logging.error(f"日期格式错误: {e}")
        return False

    templates = [
        "Envision_Temp_ZBX_Windows_Baseline",
        "Envision_Temp_ZBX_Linux_Baseline",
        "Envision_Temp_ZBX_Windows_Baseline_active"
    ]
    
    host_map = {}
    logging.info("获取模板主机列表...")
    for template in templates:
        try:
            hosts = search_hosts_by_template(zapi, template)
            for host in hosts:
                host_id = host['主机ID']
                if host_id not in host_map:
                    host_map[host_id] = {'ip': host['IP地址'], 'items': {}, 'total': {}}
        except Exception as e:
            logging.error(f"获取模板 {template} 主机失败: {e}")

    logging.info(f"获取磁盘监控项，共 {len(host_map)} 台主机...")
    for host_id, host_info in tqdm(host_map.items(), desc="获取监控项"):
        try:
            items = zapi.item.get(hostids=host_id, search={"key_": "vfs.fs.size"}, output=["itemid", "key_", "name"])
            for item in items:
                match = re.match(r'vfs\.fs\.size\[(.*?),(pused|total)\]', item['key_'])
                if match:
                    mount_point, metric = match.groups()
                    if metric == "pused":
                        host_info['items'][mount_point] = item['itemid']
                    elif metric == "total":
                        host_info['total'][mount_point] = item['itemid']
        except Exception as e:
            logging.error(f"获取主机 {host_info['ip']} 监控项失败: {e}")

    results = []
    logging.info(f"获取历史数据，共 {sum(len(h['items']) for h in host_map.values())} 项...")
    
    with tqdm(total=len(host_map), desc="处理进度") as pbar:
        for host_id, host_info in host_map.items():
            for mount_point, item_id in host_info['items'].items():
                pbar.update(1)
                pbar.set_postfix_str(f"当前主机: {host_info['ip']}")
                try:
                    history = zapi.history.get(itemids=item_id, time_from=start_ts, time_till=end_ts,
                                               output=['clock', 'value'], history=0, sortfield='clock', sortorder='ASC')
                    total_size = None
                    if mount_point in host_info['total']:
                        total_history = zapi.history.get(itemids=host_info['total'][mount_point], time_from=start_ts,
                                                         time_till=end_ts, output=['clock', 'value'], history=3,
                                                         sortfield='clock', sortorder='DESC', limit=1)
                        if total_history:
                            total_size = round(float(total_history[0]['value']) / (1024 ** 3), 2)  # 转换为 GB
                except Exception as e:
                    logging.error(f"获取 {mount_point} 历史数据失败: {e}")
                    continue
                
                if not history:
                    continue
                
                df = pd.DataFrame(history)
                df['clock'], df['value'] = pd.to_numeric(df['clock']), pd.to_numeric(df['value'])
                df['date'] = pd.to_datetime(df['clock'], unit='s').dt.strftime('%Y%m%d')
                daily_max = df.groupby('date')['value'].max().reset_index()
                
                for _, row in daily_max.iterrows():
                    results.append({
                        "IP地址": host_info['ip'],
                        "日期": row['date'],
                        "目录名称": mount_point,
                        "磁盘使用率峰值(%)": round(row['value'], 2),
                        "目录磁盘大小(GB)": total_size if total_size else "N/A"
                    })
    
    if results:
        try:
            df = pd.DataFrame(results).sort_values(by=['IP地址', '日期', '目录名称'])
            df.drop_duplicates(inplace=True)
            df.to_excel(output_file, index=False)
            logging.info(f"报告生成成功，共 {len(df)} 条记录，保存至: {output_file}")
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
            start_date_str="20250323",
            end_date_str="20250324",
            output_file=r"C:\\software\\daily_disk_peak.xlsx"
        )
        print("操作成功完成" if success else "操作未完成，请检查日志")
    except Exception as e:
        logging.error(f"程序初始化失败: {e}")