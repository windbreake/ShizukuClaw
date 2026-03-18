"""日志配置模块，用于设置应用程序的日志记录"""

import logging


def setup_logging():
    """设置通用日志配置"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
