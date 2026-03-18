"""聊天记录清理守护进程，用于定期清理过期的聊天记录"""

import logging
import os
import sys
import time

import mysql.connector
from mysql.connector import Error

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import CONFIG
from src.logging_config import setup_logging


def get_connection():
    """获取数据库连接
    
    Returns:
        mysql.connector.connection.MySQLConnection: 数据库连接对象，连接失败时返回None
    """
    try:
        connection = mysql.connector.connect(
            host=CONFIG['database']['host'],
            user=CONFIG['database']['user'],
            password=CONFIG['database']['password'],
            database=CONFIG['database']['database'],
            charset='utf8mb4'
        )
        return connection
    except Error as e:
        logging.error("数据库连接失败: %s", str(e))
        return None


def get_chat_count(connection):
    """获取聊天记录总数
    
    Args:
        connection (mysql.connector.connection.MySQLConnection): 数据库连接对象
        
    Returns:
        int: 聊天记录总数
    """
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM chat_history")
        count = cursor.fetchone()[0]
        return count
    except Error as e:
        logging.error(f"获取聊天记录数量失败: {e}")
        return 0


def cleanup_chat_records(connection, cleanup_batch=100):
    """修改：当记录超过阈值后，删除最早的 cleanup_batch 条数据
    
    Args:
        connection (mysql.connector.connection.MySQLConnection): 数据库连接对象
        cleanup_batch (int): 要清理的记录数量，默认为100
    """
    try:
        cursor = connection.cursor()
        # 查询最早的 cleanup_batch 条记录 ID
        cursor.execute(
            "SELECT id FROM chat_history ORDER BY id ASC LIMIT %s", (cleanup_batch,)
        )
        ids_to_delete = [row[0] for row in cursor.fetchall()]
        if ids_to_delete:
            id_list = ",".join(str(i) for i in ids_to_delete)
            cursor.execute(f"DELETE FROM chat_history WHERE id IN ({id_list})")
            connection.commit()
            logging.info(f"已删除最早 {cleanup_batch} 条聊天记录，共删除 {cursor.rowcount} 条。")
        else:
            logging.info("无可删除的聊天记录。")
    except Error as e:
        logging.error(f"清理聊天记录失败: {e}")


def main():
    """主函数"""
    setup_logging()
    max_records = 200
    check_interval = 60  # 每隔多少秒检查一次

    logging.info("聊天记录清理守护进程已启动...")

    while True:
        connection = get_connection()
        if connection:
            try:
                chat_count = get_chat_count(connection)
                logging.info(f"当前聊天记录数量: {chat_count} 条")

                if chat_count > max_records:
                    # 超过阈值时，删除最老的 100 条
                    cleanup_chat_records(connection)
                else:
                    logging.info(f"未超过 {max_records} 条，无需清理。")
            finally:
                connection.close()
        else:
            logging.warning("无法连接数据库，跳过本次检查。")

        # 等待指定时间后再次检查
        logging.info(f"等待 {check_interval} 秒后再次检查...")
        time.sleep(check_interval)


if __name__ == "__main__":
    main()