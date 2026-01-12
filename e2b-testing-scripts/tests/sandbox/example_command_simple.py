#!/usr/bin/env python3
"""
E2B SDK 命令执行简化示例
只包含经过验证的核心功能
"""

import os
import sys
import time

# 禁用 SSL 证书验证
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

from e2b import Sandbox

# 从环境变量获取配置
E2B_API_KEY = os.environ.get('E2B_API_KEY')
E2B_DOMAIN = os.environ.get('E2B_DOMAIN')

if not E2B_API_KEY:
    print("错误: 请设置 E2B_API_KEY 环境变量")
    sys.exit(1)

print("=" * 60)
print("E2B SDK 命令执行简化示例")
print("=" * 60)
print(f"E2B 域名: {E2B_DOMAIN}")
print(f"API Key: {E2B_API_KEY[:20]}...")
print("=" * 60)

# 示例1: 基本命令执行
print("\n【示例1】基本命令执行")
print("-" * 60)
with Sandbox(api_key=E2B_API_KEY, timeout=300) as sandbox:
    print(f"✓ 沙箱已创建: {sandbox.sandbox_id}")

    # 简单命令
    result = sandbox.commands.run("echo 'Hello from E2B!'")
    print(f"✓ 输出: {result.stdout.strip()}")
    print(f"✓ 退出码: {result.exit_code}")

    # 获取系统信息
    result = sandbox.commands.run("uname -a")
    print(f"✓ 系统信息: {result.stdout.strip()}")

    # 当前目录
    result = sandbox.commands.run("pwd")
    print(f"✓ 当前目录: {result.stdout.strip()}")

# 示例2: 带环境变量
print("\n【示例2】带环境变量的沙箱")
print("-" * 60)
with Sandbox(
    api_key=E2B_API_KEY,
    timeout=300,
    envs={"MY_VAR": "Hello from environment!", "TEST_VAR": "12345"}
) as sandbox:
    print(f"✓ 沙箱已创建: {sandbox.sandbox_id}")

    result = sandbox.commands.run("echo $MY_VAR")
    print(f"✓ MY_VAR = {result.stdout.strip()}")

    result = sandbox.commands.run("echo $TEST_VAR")
    print(f"✓ TEST_VAR = {result.stdout.strip()}")

# 示例3: 带超时的命令执行
print("\n【示例3】带超时的命令执行")
print("-" * 60)
with Sandbox(api_key=E2B_API_KEY, timeout=300) as sandbox:
    print(f"✓ 沙箱已创建: {sandbox.sandbox_id}")

    # 执行一个命令，设置超时时间
    print("  执行命令: 生成1-10的数字")
    result = sandbox.commands.run(
        "for i in {1..10}; do echo $i; done",
        timeout=10  # 设置命令超时时间
    )
    print(f"✓ 命令完成，输出行数: {len(result.stdout.strip().split())}")
    print(f"✓ 退出码: {result.exit_code}")

# 示例4: 实时输出监控（使用回调函数）
print("\n【示例4】实时输出监控")
print("-" * 60)
with Sandbox(api_key=E2B_API_KEY, timeout=300) as sandbox:
    print(f"✓ 沙箱已创建: {sandbox.sandbox_id}")

    # 定义回调函数
    outputs = []
    def on_stdout(output):
        line = output.strip()
        if line:
            outputs.append(line)
            print(f"  [实时输出] {line}")

    # 运行会产生多行输出的命令，使用回调函数
    result = sandbox.commands.run(
        "for i in 1 2 3; do echo \"输出行 $i\"; sleep 0.3; done",
        on_stdout=on_stdout,
        timeout=10
    )
    print(f"✓ 命令完成，共捕获 {len(outputs)} 行输出")
    print(f"✓ 退出码: {result.exit_code}")

# 示例5: 命令级别的环境变量和工作目录
print("\n【示例5】命令级别的环境变量和工作目录")
print("-" * 60)
with Sandbox(api_key=E2B_API_KEY, timeout=300) as sandbox:
    print(f"✓ 沙箱已创建: {sandbox.sandbox_id}")

    # 使用命令级别的环境变量
    result = sandbox.commands.run(
        "echo $CMD_VAR",
        envs={"CMD_VAR": "这是命令级别的环境变量"}
    )
    print(f"✓ 命令环境变量: {result.stdout.strip()}")

    # 创建目录并在其中执行命令
    sandbox.commands.run("mkdir -p /tmp/testdir")
    result = sandbox.commands.run(
        "pwd && echo 'test content' > file.txt && ls -la",
        cwd="/tmp/testdir"
    )
    print(f"✓ 在指定目录执行:\n{result.stdout}")

    # 以 root 用户执行命令
    result = sandbox.commands.run("whoami", user="root")
    print(f"✓ 当前用户: {result.stdout.strip()}")

# 示例6: 文件操作
print("\n【示例6】文件操作")
print("-" * 60)
with Sandbox(api_key=E2B_API_KEY, timeout=300) as sandbox:
    print(f"✓ 沙箱已创建: {sandbox.sandbox_id}")

    # 写入文件
    test_content = "这是测试内容\nLine 2\nLine 3\n"
    sandbox.files.write("/tmp/test.txt", test_content)
    print("✓ 文件已写入: /tmp/test.txt")

    # 读取文件
    content = sandbox.files.read("/tmp/test.txt")
    print(f"✓ 文件内容:\n{content}")

    # 使用命令验证
    result = sandbox.commands.run("cat /tmp/test.txt")
    print(f"✓ 通过命令读取:\n{result.stdout}")

    # 列出目录
    result = sandbox.commands.run("ls -lh /tmp/test.txt")
    print(f"✓ 文件信息: {result.stdout.strip()}")

# 示例7: 组合使用 - 创建并执行脚本
print("\n【示例7】组合使用 - 创建并执行脚本")
print("-" * 60)
with Sandbox(api_key=E2B_API_KEY, timeout=300) as sandbox:
    print(f"✓ 沙箱已创建: {sandbox.sandbox_id}")

    # 创建一个 shell 脚本
    script_content = """#!/bin/bash
echo "=== 系统信息 ==="
hostname
uptime
echo ""
echo "=== CPU 信息 ==="
cat /proc/cpuinfo | grep "model name" | head -1
echo ""
echo "=== 内存信息 ==="
free -h
"""

    sandbox.files.write("/tmp/sysinfo.sh", script_content)
    print("✓ 脚本已创建: /tmp/sysinfo.sh")

    # 添加执行权限
    sandbox.commands.run("chmod +x /tmp/sysinfo.sh")
    print("✓ 执行权限已添加")

    # 执行脚本
    print("✓ 执行脚本输出:")
    result = sandbox.commands.run("/tmp/sysinfo.sh")
    print(result.stdout)

# 示例8: Python 代码执行
print("\n【示例8】Python 代码执行")
print("-" * 60)
with Sandbox(api_key=E2B_API_KEY, timeout=300) as sandbox:
    print(f"✓ 沙箱已创建: {sandbox.sandbox_id}")

    # 创建 Python 脚本
    python_code = """#!/usr/bin/env python3
import sys
import os

print("Python 版本:", sys.version)
print("当前用户:", os.getenv('USER', 'unknown'))
print("当前目录:", os.getcwd())

# 简单计算
numbers = [1, 2, 3, 4, 5]
print(f"数字列表: {numbers}")
print(f"总和: {sum(numbers)}")
print(f"平均值: {sum(numbers) / len(numbers)}")
"""

    sandbox.files.write("/tmp/test.py", python_code)
    print("✓ Python 脚本已创建")

    # 执行 Python 脚本
    print("✓ 执行结果:")
    result = sandbox.commands.run("python3 /tmp/test.py")
    print(result.stdout)

print("\n" + "=" * 60)
print("✅ 所有示例执行完成!")
print("=" * 60)
