#!/usr/bin/env python3
"""
清理所有 E2B 沙箱

使用方法:
  source .e2b_env
  python3 cleanup_sandboxes.py
"""

import os
import sys
import ssl
import subprocess
import re

# ========== 禁用 SSL 证书验证 ==========
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['SSL_CERT_FILE'] = ''
os.environ['SSL_CERT_DIR'] = ''
os.environ['REQUESTS_VERIFY'] = 'false'

ssl._create_default_https_context = ssl._create_unverified_context

# 导入彩色日志
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import get_logger

logger = get_logger(__name__)

# 检查必需的环境变量
required_env_vars = ['E2B_DOMAIN', 'E2B_API_KEY']
missing_vars = [var for var in required_env_vars if var not in os.environ]
if missing_vars:
    logger.error(f"错误: 缺少必需的环境变量: {', '.join(missing_vars)}")
    logger.info("请先配置 .e2b_env 文件并运行: source .e2b_env")
    sys.exit(1)

E2B_DOMAIN = os.environ['E2B_DOMAIN']
E2B_API_KEY = os.environ['E2B_API_KEY']

def get_sandbox_ids():
    """获取所有沙箱 ID"""
    try:
        env = os.environ.copy()
        env['E2B_DOMAIN'] = E2B_DOMAIN
        env['E2B_API_KEY'] = E2B_API_KEY

        result = subprocess.run(
            ['e2b', 'sbx', 'list'],
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )

        if result.returncode != 0:
            logger.error(f"获取沙箱列表失败: {result.stderr}")
            return []

        # 移除 ANSI 颜色代码
        output = re.sub(r'\x1b\[[0-9;]*m', '', result.stdout)

        sandbox_ids = []
        lines = output.strip().split('\n')

        for line in lines:
            line = line.strip()
            # 跳过标题行和分隔线
            if not line or line.startswith('-') or 'Sandbox' in line:
                continue

            # 提取沙箱 ID (格式: ixxxxxx-xxxxxxxx)
            parts = line.split()
            if parts:
                sandbox_id = parts[0]
                # 验证是否是有效的沙箱 ID 格式
                if re.match(r'^i[a-z0-9]+-[a-z0-9]+$', sandbox_id):
                    sandbox_ids.append(sandbox_id)

        return sandbox_ids

    except Exception as e:
        logger.info(f"获取沙箱列表时出错: {e}")
        return []

def kill_sandbox(sandbox_id):
    """删除单个沙箱"""
    try:
        env = os.environ.copy()
        env['E2B_DOMAIN'] = E2B_DOMAIN
        env['E2B_API_KEY'] = E2B_API_KEY

        result = subprocess.run(
            ['e2b', 'sbx', 'kill', sandbox_id],
            capture_output=True,
            text=True,
            timeout=10,
            env=env
        )

        return result.returncode == 0

    except Exception:
        return False

def main():
    logger.info("=" * 60)
    logger.info("E2B 沙箱清理工具")
    logger.info("=" * 60)
    logger.info(f"E2B 域名: {E2B_DOMAIN}")
    logger.info("=" * 60)

    # 获取所有沙箱 ID
    logger.info("\n正在获取沙箱列表...")
    sandbox_ids = get_sandbox_ids()

    if not sandbox_ids:
        logger.error("没有找到沙箱或获取失败")
        return

    logger.info(f"找到 {len(sandbox_ids)} 个沙箱")

    # 确认删除
    response = input(f"\n确认要删除所有 {len(sandbox_ids)} 个沙箱吗? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        logger.info("操作已取消")
        return

    # 删除沙箱
    logger.info("\n开始删除沙箱...")
    success = 0
    failed = 0

    for i, sandbox_id in enumerate(sandbox_ids, 1):
        logger.info(f"[{i}/{len(sandbox_ids)}] 删除沙箱 {sandbox_id}...")

        if kill_sandbox(sandbox_id):
            logger.info("✓")
            success += 1
        else:
            logger.error("✗")
            failed += 1

    logger.info("\n" + "=" * 60)
    logger.error(f"清理完成: {success} 成功, {failed} 失败")
    logger.info("=" * 60)

if __name__ == '__main__':
    main()
