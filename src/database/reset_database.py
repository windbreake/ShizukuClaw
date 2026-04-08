"""数据库重置工具，用于管理和清理聊天记录"""

import logging
import os
import subprocess
import sys
from mysql.connector import Error

# 添加项目根目录到 sys.path
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.database.database import get_connection, table_exists
from src.utils.logging_config import setup_logging


def reset_chat_history(connection):
    """清空 chat_history 表
    
    Args:
        connection (mysql.connector.connection.MySQLConnection): 数据库连接对象
    """
    try:
        cursor = connection.cursor()
        if table_exists(cursor, 'chat_history'):
            cursor.execute("DELETE FROM chat_history")
            connection.commit()
            logging.info("chat_history 表已清空。")
    except Error as e:
        logging.error("清空 chat_history 表失败: %s", e)


def list_records(connection, limit, offset):
    """列出记录
    
    Args:
        connection (mysql.connector.connection.MySQLConnection): 数据库连接对象
        limit (int): 限制记录数
        offset (int): 偏移量
        
    Returns:
        list: 记录列表
    """
    try:
        cursor = connection.cursor()
        if table_exists(cursor, 'chat_history'):
            cursor.execute("SELECT * FROM chat_history ORDER BY id ASC LIMIT %s OFFSET %s", (limit, offset))
            return cursor.fetchall()
        return []
    except Error as e:
        logging.error("列出记录失败: %s", e)
        return []


def delete_record(connection, record_id):
    """删除指定记录
    
    Args:
        connection (mysql.connector.connection.MySQLConnection): 数据库连接对象
        record_id (int): 要删除的记录ID
    """
    try:
        cursor = connection.cursor()
        if not table_exists(cursor, 'chat_history'):
            print("记录表不存在。")
            return
            
        cursor.execute("SELECT * FROM chat_history WHERE id=%s", (record_id,))
        rec = cursor.fetchone()
        if not rec:
            print("记录不存在。")
            return
        print("将删除记录：", rec)
        confirm = input("确认删除？(y/n): ").strip().lower()
        if confirm == 'y':
            cursor.execute("DELETE FROM chat_history WHERE id=%s", (record_id,))
            connection.commit()
            print("已删除。")
        else:
            print("已取消。")
    except Error as e:
        logging.error("删除指定记录失败: %s", e)


def paginate_and_manage_records(connection, page_size=200):
    """分页管理和展示记录
    
    Args:
        connection (mysql.connector.connection.MySQLConnection): 数据库连接对象
        page_size (int): 每页记录数，默认为200
    """
    page = 0
    while True:
        os.system('cls')  # 清屏
        records = list_records(connection, page_size, page * page_size)
        if not records:
            print("无更多记录。")
            break
        for idx, row in enumerate(records, start=1 + page * page_size):
            print(f"{idx}. {row}")
        cmd = input("[N] 下一页  [P] 上一页  [R] 刷新  [Q] 返回菜单: ").strip().lower()
        if cmd == 'n':
            page += 1
        elif cmd == 'p' and page > 0:
            page -= 1
        elif cmd == 'r':
            continue
        elif cmd == 'q':
            break
        else:
            print("无效输入。")


def delete_first_n_records(connection):
    """删除前N条记录
    
    Args:
        connection (mysql.connector.connection.MySQLConnection): 数据库连接对象
    """
    try:
        n = input("请输入要删除的前 N 条记录的数量: ").strip()
        if not n.isdigit():
            print("请输入有效数字。")
            return
        n = int(n)
        cursor = connection.cursor()
        if not table_exists(cursor, 'chat_history'):
            print("记录表不存在。")
            return
            
        cursor.execute("SELECT id FROM chat_history ORDER BY id ASC LIMIT %s", (n,))
        ids = [r[0] for r in cursor.fetchall()]
        if not ids:
            print("无可删除的记录。")
            return
        print("将删除以下 ID:", ids)
        confirm = input("确认删除？(y/n): ").strip().lower()
        if confirm == 'y':
            # 使用参数化查询避免SQL注入
            format_strings = ','.join(['%s'] * len(ids))
            query = f"DELETE FROM chat_history WHERE id IN ({format_strings})"
            cursor.execute(query, tuple(ids))
            connection.commit()
            print(f"已删除 {cursor.rowcount} 条记录。")
        else:
            print("已取消。")
    except Error as e:
        logging.error("删除前N条记录失败: %s", e)


def main():
    """主函数"""
    setup_logging()
    db_conn = get_connection()
    if not db_conn:
        print("无法连接数据库。")
        return
    try:
        while True:
            os.system('cls')  # 每次刷新前清屏
            print("\n1. 清空所有聊天记录\n2. 展示聊天记录\n3. 删除指定记录\n4. 删除前 N 条记录\n5. 退出")
            choice = input("请输入选项 [1-5]: ").strip()
            if choice == '1':
                confirm = input("警告：此操作将清空所有聊天记录，是否继续？(y/n): ").strip().lower()
                if confirm == 'y':
                    reset_chat_history(db_conn)
                else:
                    print("已取消清空操作。")
            elif choice == '2':
                # 在新窗口仅展示记录
                script = os.path.abspath(__file__)
                subprocess.Popen(f'start cmd /k python "{script}" --show', shell=True)
            elif choice == '3':
                rid = input("请输入要删除的记录 ID: ").strip()
                if rid.isdigit():
                    delete_record(db_conn, int(rid))
                else:
                    print("无效 ID。")
            elif choice == '4':
                delete_first_n_records(db_conn)
            elif choice == '5':
                break
            else:
                print("无效选项。")
    finally:
        db_conn.close()


if __name__ == "__main__":
    if "--show" in sys.argv:
        conn = get_connection()
        if conn:
            try:
                paginate_and_manage_records(conn)
            finally:
                conn.close()
        sys.exit()
    main()
