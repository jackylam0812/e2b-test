#!/usr/bin/env python3
"""
通用的彩色日志配置模块

使用方法:
    from utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("信息")
    logger.warning("警告")
    logger.error("错误")
"""

import logging

# 尝试导入colorlog
try:
    import colorlog

    def get_logger(name: str = __name__, level: int = logging.INFO):
        """
        获取配置好的彩色logger

        Args:
            name: logger名称，通常使用 __name__
            level: 日志级别，默认INFO

        Returns:
            配置好的logger实例
        """
        # 创建logger
        logger = colorlog.getLogger(name)

        # 如果已经有handler，直接返回
        if logger.handlers:
            return logger

        logger.setLevel(level)

        # 创建彩色formatter
        formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            },
            secondary_log_colors={},
            style='%'
        )

        # 配置handler
        handler = colorlog.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

except ImportError:
    # 如果没有colorlog，使用标准日志 + ANSI颜色
    class ColoredFormatter(logging.Formatter):
        """自定义彩色formatter"""

        COLORS = {
            'DEBUG': '\033[36m',      # 青色
            'INFO': '\033[32m',       # 绿色
            'WARNING': '\033[33m',    # 黄色
            'ERROR': '\033[31m',      # 红色
            'CRITICAL': '\033[41m',   # 红色背景
        }
        RESET = '\033[0m'

        def format(self, record):
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
                record.msg = f"{self.COLORS[levelname]}{record.msg}{self.RESET}"
            return super().format(record)

    def get_logger(name: str = __name__, level: int = logging.INFO):
        """
        获取配置好的logger（无colorlog版本）

        Args:
            name: logger名称，通常使用 __name__
            level: 日志级别，默认INFO

        Returns:
            配置好的logger实例
        """
        logger = logging.getLogger(name)

        # 如果已经有handler，直接返回
        if logger.handlers:
            return logger

        logger.setLevel(level)

        handler = logging.StreamHandler()
        handler.setFormatter(ColoredFormatter(
            '%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))

        logger.addHandler(handler)

        return logger


# 提供一个默认的logger实例
default_logger = get_logger('e2b_tests')
