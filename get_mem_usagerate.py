import time
from datetime import datetime, timedelta
import pandas as pd
from login_zabbix_api import login_zabbix_api
from concurrent.futures import ThreadPoolExecutor, as_completed

def smooth_spikes(series, window_size=5, threshold=80):
    """
    平滑瞬间异常峰值
    参数：
        series: pd.Series 时间序列数据
        window_size: 前后参考窗口大小（数据点数量）
        threshold: 判定为异常的百分比阈值
    返回：
        平滑后的Series
    """
    smoothed = series.copy()
    n = len(smoothed)
    for i in range(n):
        current = smoothed.iloc[i]
        
        # 计算前向参考窗口
        start_prev = max(0, i - window_size)
        prev_points = smoothed.iloc[start_prev:i]
        
        # 计算后向参考窗口
        end_next = min(n, i + window_size + 1)
        next_points = smoothed.iloc[i+1:end_next]

        # 跳过首尾不足的情况
        if len(prev_points) == 0 or len(next_points) == 0:
            continue

        # 计算前后窗口平均值
        prev_avg = prev_points.mean()
        next_avg = next_points.mean()

        # 异常点判定逻辑
        if abs(current - prev_avg) > threshold and abs(current - next_avg) > threshold:
            # 使用相邻点均值替换
            if i > 0 and i < n-1:
                new_value = (smoothed.iloc[i-1] + smoothed.iloc[i+1]) / 2
            elif i == 0:
                new_value = smoothed.iloc[i+1]
            else:
                new_value = smoothed.iloc[i-1]
            
            smoothed.iloc[i] = new_value
            
    return smoothed

def sliding_window_sum(series, window_size=30):
    """
    滑动窗口计算窗口内CPU使用率总和
    参数：
        series: pd.Series 时间序列数据
        window_size: 窗口大小（分钟）
    返回：
        窗口内CPU使用率总和的Series
    """
    window_sum = series.rolling(window=f'{window_size}T', min_periods=1).sum()
    return window_sum

def process_host(host, start_date_dt, end_date_dt, window_size, threshold):
    """
    处理单个主机的CPU数据
    参数：
        host: 主机信息
        start_date_dt: 开始日期
        end_date_dt: 结束日期
        window_size: 窗口大小
        threshold: 异常阈值
    返回：
        处理后的数据列表
    """
    ip_address = host['host']
    system_type = host['system_type']
    print(f"正在处理主机: {ip_address} ({system_type})")
    
    # 确定监控项key
    key_variants = []
    if system_type == "Linux":
        key_variants = ["vm.memory.utilization"]
    elif system_type == "Windows":
        key_variants = [r"vm.memory.size[pused]"]
    
    itemid = None
    for key in key_variants:
        try:
            items = zapi.item.get(
                output=["itemid", "name", "key_"],
                hostids=host['hostid'],
                search={"key_": key},
                filter={"name": "Memory utilization"}
            )
            if items:
                itemid = items[0]['itemid']
                break
        except Exception as e:
            print(f"监控项查询异常: {str(e)}")
    
    if not itemid:
        print(f"未找到CPU监控项，尝试过的key: {key_variants}")
        return []

    all_data = []
    current_date = start_date_dt
    while current_date <= end_date_dt:
        day_str = current_date.strftime("%Y%m%d")
        print(f"处理日期: {day_str}")
        
        try:
            time_from = int(current_date.timestamp())
            time_till = int((current_date + timedelta(days=1)).timestamp())
            print(f"查询时间范围: {datetime.fromtimestamp(time_from)} 至 {datetime.fromtimestamp(time_till)}")

            max_retries = 3
            for attempt in range(max_retries):
                try:
                    history = zapi.history.get(
                        itemids=itemid,
                        history=0,
                        time_from=time_from,
                        time_till=time_till,
                        output="extend"
                    )
                    if not history:
                        history = zapi.history.get(
                            itemids=itemid,
                            history=3,
                            time_from=time_from,
                            time_till=time_till,
                            output="extend"
                        )
                    break
                except Exception as e:
                    if attempt == max_retries -1:
                        raise
                    print(f"查询重试中 ({attempt+1}/{max_retries})...")
                    time.sleep(2)
            
            print(f"获取到{len(history)}条历史记录")
            
            if history:
                try:
                    df = pd.DataFrame([{
                        'timestamp': datetime.fromtimestamp(int(h['clock'])),
                        'value': float(h['value'])
                    } for h in history])
                    
                    if df.empty:
                        print("数据转换后为空")
                        continue
                        
                    df.sort_values('timestamp', inplace=True)
                    df.set_index('timestamp', inplace=True)
                    
                    print("执行瞬间峰值平滑处理...")
                    df['value'] = smooth_spikes(df['value'], window_size=5, threshold=threshold)
                    
                    df_resampled = df.resample('1T').mean().ffill()
                    print(f"重新采样后数据量: {len(df_resampled)}条 (1分钟粒度)")
                    
                    window_sum = sliding_window_sum(df_resampled['value'], window_size=window_size)
                    
                    peak_window_sum = window_sum.max()
                    peak_window_idx = window_sum.idxmax()
                    peak_window_start = peak_window_idx - timedelta(minutes=window_size)
                    peak_window_end = peak_window_idx + timedelta(minutes=window_size)
                    
                    peak_value = df_resampled.loc[peak_window_start:peak_window_end, 'value'].max()
                    peak_time = df_resampled.loc[df_resampled['value'] == peak_value].index[0]
                    
                    all_data.append({
                        'IP地址': ip_address,
                        '系统类型': system_type,
                        '日期': day_str,
                        '峰值时间': peak_time.strftime("%Y-%m-%d %H:%M:%S"),
                        '峰值利用率(%)': round(peak_value, 2),
                        '窗口总负荷': round(peak_window_sum, 2),
                        '峰值窗口开始时间': peak_window_start.strftime("%Y-%m-%d %H:%M:%S"),
                        '峰值窗口结束时间': peak_window_end.strftime("%Y-%m-%d %H:%M:%S"),
                        '数据点数': len(df_resampled),
                        '窗口大小(分钟)': window_size
                    })
                    print(f"发现峰值: {peak_value}%")
                except Exception as e:
                    print(f"数据处理异常: {str(e)}")
            else:
                print("无历史数据")
            
        except Exception as e:
            print(f"日期处理异常: {str(e)}")
        
        current_date += timedelta(days=1)
    
    return all_data

def get_cpu_peak_data(start_date, end_date, output_file, window_size=30, threshold=80):
    """
    获取并处理CPU峰值数据，结果保存到Excel文件。
    参数:
        start_date: string 开始日期，格式为"%Y%m%d"
        end_date: string 结束日期，格式为"%Y%m%d"
        output_file: string 输出Excel文件路径
        window_size: int 滑动窗口大小（分钟），默认为30。
        threshold: int 异常峰值判定阈值，默认为80。
    """
    global zapi
    try:
        zapi = login_zabbix_api()
        print("Zabbix API连接成功")
    except Exception as e:
        print(f"API连接失败: {str(e)}")
        return

    try:
        start_date_dt = datetime.strptime(start_date, "%Y%m%d").replace(hour=0, minute=0, second=0)
        end_date_dt = datetime.strptime(end_date, "%Y%m%d").replace(hour=23, minute=59, second=59)
        print(f"日期范围: {start_date_dt} 至 {end_date_dt}")
    except ValueError as e:
        print(f"日期格式错误: {str(e)}")
        return

    host_templates = {
        "windows": "Envision_Temp_ZBX_Windows_Baseline",
        "linux": "Envision_Temp_ZBX_Linux_Baseline"
    }
    
    try:
        hosts = zapi.host.get(
            output=["hostid", "host", "status"],
            selectParentTemplates=["templateid", "name"],
            filter={"status": "0"}
        )
        print(f"获取到{len(hosts)}台主机")
        
        valid_hosts = []
        for host in hosts:
            templates = [t['name'] for t in host['parentTemplates']]
            system_type = None
            if host_templates["linux"] in templates:
                system_type = "Linux"
            elif host_templates["windows"] in templates:
                system_type = "Windows"
            
            if system_type:
                host['system_type'] = system_type
                valid_hosts.append(host)
                print(f"有效主机: {host['host']} (系统类型: {system_type}, 模板: {', '.join(templates)})")
        
        print(f"符合条件的主机数量: {len(valid_hosts)}")
        if not valid_hosts:
            print("未找到符合模板条件的主机")
            return
    except Exception as e:
        print(f"主机查询失败: {str(e)}")
        return

    all_data = []
    
    # 使用多线程并行处理主机数据
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_host, host, start_date_dt, end_date_dt, window_size, threshold) for host in valid_hosts]
        for future in as_completed(futures):
            try:
                result = future.result()
                all_data.extend(result)
            except Exception as e:
                print(f"处理主机数据异常: {str(e)}")
    
    if all_data:
        df_result = pd.DataFrame(all_data)
        if not df_result.empty:
            df_result['数据质量'] = pd.cut(df_result['数据点数'],
                                     bins=[0, 100, 200, float('inf')],
                                     labels=['低', '中', '高'])
            
            columns_order = ['IP地址', '系统类型', '日期', '峰值时间', '峰值利用率(%)',
                            '窗口总负荷', '峰值窗口开始时间', '峰值窗口结束时间', '数据点数', '窗口大小(分钟)', '数据质量']
            df_result = df_result[columns_order]
            
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                df_result.to_excel(writer, index=False, sheet_name='峰值数据')
                
                pd.DataFrame({
                    '参数': ['开始日期', '结束日期', '总主机数', '有效数据条目', '窗口大小(分钟)', '异常阈值'],
                    '值': [start_date, end_date, len(valid_hosts), len(df_result), window_size, threshold]
                }).to_excel(writer, index=False, sheet_name='执行摘要')
                
            print(f"\n成功生成报告: {output_file}")
            print(f"总记录数: {len(df_result)}")
            print(f"数据质量分布:\n{df_result['数据质量'].value_counts()}")
        else:
            print("有效数据列表为空")
    else:
        print("\n未找到有效数据，可能原因：")
        print("1. 监控项未正确配置")
        print("2. 指定时间段无历史数据")
        print("3. 所有主机的CPU利用率均低于基准线")

if __name__ == "__main__":
    get_cpu_peak_data(
        start_date="20250301",
        end_date="20250302",
        output_file=r"C:\software\daily_mem_peak.xlsx",
        window_size=15,
        threshold=90
    )