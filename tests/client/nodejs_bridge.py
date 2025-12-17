#!/usr/bin/env python3
"""
Node.js E2B CLI 桥接器

通过 Python 调用 Node.js E2B CLI 执行沙箱命令
用于绕过 Python SDK 与旧版 envd 的兼容性问题

前提: 需要安装 Node.js 和 @e2b/cli
  npm install -g @e2b/cli@1.4.1
"""

import subprocess
import json
import time
import sys
import os
from typing import Dict, Any, Optional

# 导入彩色日志
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import get_logger

logger = get_logger(__name__)


class CommandResult:
    """命令执行结果"""
    def __init__(self, exit_code: int, stdout: str, stderr: str):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


class NodeCLISandbox:
    """
    使用 Node.js CLI 的 Sandbox 包装器
    提供与 Python SDK 类似的接口
    """

    def __init__(self, sandbox_id: str):
        self.sandbox_id = sandbox_id

    @classmethod
    def create(cls, template: Optional[str] = None):
        """
        创建 Sandbox

        Args:
            template: 模板名称(可选)

        Returns:
            NodeCLISandbox 实例
        """
        cmd = ["e2b", "sandbox", "create"]

        if template:
            cmd.extend(["--template", template])

        # 添加 JSON 输出
        cmd.append("--json")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode == 0:
                # 解析 JSON 输出获取 sandbox ID
                try:
                    data = json.loads(result.stdout)
                    sandbox_id = data.get("sandboxId") or data.get("id") or data.get("sandboxID")

                    if not sandbox_id:
                        # 如果 JSON 中没有 ID,尝试从文本输出提取
                        lines = result.stdout.strip().split('\n')
                        for line in lines:
                            if 'sandbox' in line.lower() or 'id' in line.lower():
                                # 简单提取
                                parts = line.split()
                                for part in parts:
                                    if len(part) > 10 and 'i' in part:
                                        sandbox_id = part
                                        break

                    if sandbox_id:
                        return cls(sandbox_id)
                    else:
                        raise Exception(f"无法从输出中获取 sandbox ID: {result.stdout}")

                except json.JSONDecodeError:
                    # JSON 解析失败,尝试从文本输出提取
                    raise Exception(f"无法解析 CLI 输出: {result.stdout}")
            else:
                raise Exception(f"创建失败: {result.stderr}")

        except subprocess.TimeoutExpired:
            raise Exception("创建超时 (60秒)")

    def run(self, cmd: str, timeout: int = 120) -> CommandResult:
        """
        在 sandbox 中执行命令

        Args:
            cmd: 要执行的命令
            timeout: 超时时间(秒)

        Returns:
            CommandResult 对象
        """
        result = subprocess.run(
            ["e2b", "sandbox", "exec", self.sandbox_id, cmd],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        return CommandResult(
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr
        )

    def kill(self):
        """关闭 Sandbox"""
        try:
            subprocess.run(
                ["e2b", "sandbox", "kill", self.sandbox_id],
                capture_output=True,
                timeout=30
            )
        except Exception:
            # 忽略关闭错误
            pass


# 模拟 Python SDK 的接口
class commands:
    """模拟 Python SDK 的 commands 接口"""

    def __init__(self, sandbox):
        self.sandbox = sandbox

    def run(self, cmd: str) -> CommandResult:
        return self.sandbox.run(cmd)


# 为了兼容性,给 NodeCLISandbox 添加 commands 属性
NodeCLISandbox.commands = property(lambda self: commands(self))


def check_cli_available() -> bool:
    """检查 e2b CLI 是否可用"""
    try:
        result = subprocess.run(
            ["e2b", "--version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# 测试函数
if __name__ == "__main__":
    import os

    logger.info("="*60)
    logger.info("Node.js CLI 桥接器测试")
    logger.info("="*60)
    logger.info()

    # 检查 CLI
    logger.info("1. 检查 e2b CLI...")
    if not check_cli_available():
        logger.error("   ✗ e2b CLI 不可用")
        logger.info()
        logger.info("请安装:")
        logger.info("  npm install -g @e2b/cli@1.4.1")
        logger.info()
        logger.info("如果 Node.js 版本 < 18:")
        logger.info("  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -")
        logger.info("  sudo apt install -y nodejs")
        sys.exit(1)

    logger.info("   ✓ e2b CLI 可用")
    logger.info()

    # 测试创建和执行
    template = os.getenv('E2B_TEMPLATE_NAME', 'next_agent_sandbox_aws_test_new')

    logger.info(f"2. 创建 Sandbox (模板: {template})...")
    try:
        sandbox = NodeCLISandbox(template)
        logger.info(f"   ✓ 创建成功: {sandbox.sandbox_id}")
        logger.info()

        logger.info("3. 测试命令执行...")

        # 测试1: 简单命令
        logger.info("   测试1: echo hello")
        result = sandbox.commands.run("echo 'Hello from Node CLI bridge'")
        logger.info(f"   ✓ exit_code: {result.exit_code}")
        logger.info(f"   ✓ stdout: {result.stdout.strip()}")
        logger.info()

        # 测试2: Python 版本
        logger.info("   测试2: python3 --version")
        result = sandbox.run("python3 --version")
        logger.info(f"   ✓ {result.stdout.strip()}")
        logger.info()

        # 清理
        logger.info("4. 关闭 Sandbox...")
        sandbox.kill()
        logger.info("   ✓ 已关闭")
        logger.info()

        logger.info("="*60)
        logger.info("🎉 Node CLI 桥接测试成功!")
        logger.info("="*60)
        logger.info()
        logger.info("可以使用此方案进行沙箱内性能测试")

    except Exception as e:
        logger.error(f"   ✗ 失败: {e}")
        sys.exit(1)
