from update_trigger_api import update_triggers, login_zabbix_api
import pandas as pd
import logging

# 设置日志记录格式
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def process_triggers_from_excel(file_path, trigger_name=None, monitor_key=None, monitor_item_value=None, trigger_status=None):
    """
    从 Excel 文件中读取主机名称，调用 update_triggers 函数处理触发器信息。

    :param file_path: Excel 文件路径
    :param trigger_name: 触发器名称，用于筛选（可选）
    :param monitor_key: 监控项键名，用于筛选（可选）
    :param monitor_item_value: 监控项值，用于筛选（可选）
    :param trigger_status: 触发器状态（0: 启用, 1: 禁用）
    """
    try:
        # 加载 Excel 文件
        df = pd.read_excel(file_path)
        if '主机名称' not in df.columns:
            logging.error(f"Excel 文件 {file_path} 中缺少 '主机名称' 列")
            return

        # 获取唯一主机名
        host_names = df['主机名称'].dropna().unique()

        # 初始化 Zabbix API 会话
        zabbix_api = login_zabbix_api()

        # 遍历主机名并处理触发器
        for host_name in host_names:
            logging.info(f"开始处理主机: {host_name}")
            triggers = update_triggers(
                zabbix_api=zabbix_api,
                host_name=host_name,
                trigger_name=trigger_name,
                monitor_key=monitor_key,
                monitor_item_value=monitor_item_value,
                get_triggers_only=True  # 获取触发器信息而不执行更新
            )

            if not triggers:
                logging.info(f"主机 {host_name} 未找到符合条件的触发器")
                continue

            for trigger in triggers:
                current_status = trigger.get("Trigger Enabled")
                if str(current_status) == str(trigger_status):
                    logging.info(f"触发器 {trigger['Trigger Name']} 状态已为目标状态，跳过更新")
                    continue

                logging.info(f"更新触发器 {trigger['Trigger Name']} 状态为 {trigger_status}")
                update_triggers(
                    zabbix_api=zabbix_api,
                    host_name=host_name,
                    trigger_name=trigger_name,
                    monitor_key=monitor_key,
                    monitor_item_value=monitor_item_value,
                    trigger_status=trigger_status
                )

        logging.info("所有主机处理完成！")

    except FileNotFoundError:
        logging.error(f"指定的 Excel 文件 {file_path} 不存在")
    except Exception as e:
        logging.error(f"处理 Excel 文件 {file_path} 时发生错误: {e}")

if __name__ == "__main__":
    # 配置参数
    FILE_PATH = "C:\\software\\hosts.xlsx"
    TRIGGER_NAME = "cmdb-agent"  # 触发器名称（可选）
    # MONITOR_KEY = 'proc.num[,,,"/usr/sbin/ntpd"]'  # 默认监控项键
    MONITOR_ITEM_VALUE = None  # 筛选监控项值（如需关闭筛选，则设置为 None）
    TRIGGER_STATUS = 1  # 触发器状态（0: 启用, 1: 禁用）

    # 调用函数处理触发器
    process_triggers_from_excel(
        file_path=FILE_PATH,
        trigger_name=TRIGGER_NAME,
        # monitor_key=MONITOR_KEY,
        monitor_item_value=MONITOR_ITEM_VALUE,
        trigger_status=TRIGGER_STATUS
    )
