#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""数据库创建脚本，用于初始化数据库和表结构"""

import os
import sys

import mysql.connector
from mysql.connector import Error

# 添加项目根目录到 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import CONFIG


def execute_sql_file(sql_file_path):
    """执行SQL文件中的语句
    
    Args:
        sql_file_path (str): SQL文件路径
        
    Returns:
        bool: 执行是否成功
    """
    connection = None
    try:
        # 连接到MySQL服务器
        connection = mysql.connector.connect(
            host=CONFIG['database']['host'],
            user=CONFIG['database']['user'],
            password=CONFIG['database']['password']
        )

        cursor = connection.cursor()

        # 读取SQL文件
        with open(sql_file_path, 'r', encoding='utf-8') as file:
            sql_script = file.read()

        # 执行SQL脚本
        for statement in sql_script.split(';'):
            if statement.strip():  # 忽略空语句
                try:
                    cursor.execute(statement)
                except Error as e:
                    print("执行语句时出错 (可能会忽略某些非关键错误): %s", str(e))
                    # 对于索引已存在的错误，我们可以忽略
                    if "Duplicate key name" in str(e):
                        print("  忽略重复索引错误")
                    else:
                        # 如果是其他错误，重新抛出
                        raise e

        connection.commit()
        print("成功执行SQL文件: %s", sql_file_path)

    except Error as e:
        print("执行SQL文件时出错: %s", str(e))
        return False
    finally:
        if connection and connection.is_connected():
            cursor.close()
            connection.close()

    return True


def main():
    """主函数"""
    print("开始创建数据库和表...")

    # 获取SQL文件路径
    sql_file_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
        'data', 'init_database.sql'
    )

    # 执行SQL文件
    if not execute_sql_file(sql_file_path):
        print("执行SQL文件失败")
        return

    print("数据库和表创建完成!")


if __name__ == "__main__":
    main()