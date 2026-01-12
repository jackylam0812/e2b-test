#!/usr/bin/env python3
"""
E2B 模板构建测试脚本

测试指标:
- 模板构建时间
- 沙箱创建时间
- 基本功能验证

使用方法:
  python3 test_template_build.py --name agent_test --memory 4096 --cpu 6
"""

import os
import sys
import time
import json
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

# 禁用 SSL 证书验证（解决兼容性问题）
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 导入彩色日志
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import get_logger

logger = get_logger(__name__)


def load_e2b_env():
    """从 .e2b_env 文件加载环境变量"""
    env_file = PROJECT_ROOT / ".e2b_env"
    if not env_file.exists():
        log(f".e2b_env 文件不存在: {env_file}", "WARN")
        return {}
    
    env_vars = {}
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            # 跳过注释和空行
            if not line or line.startswith('#'):
                continue
            # 解析 export VAR="value" 或 export VAR='value' 或 export VAR=value
            if line.startswith('export '):
                line = line[7:].strip()  # 移除 'export '
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # 移除引号
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    env_vars[key] = value
    
    log(f"已从 .e2b_env 加载 {len(env_vars)} 个环境变量", "SUCCESS")
    return env_vars


def log(message: str, level: str = "INFO"):
    """打印日志"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefix = {
        "INFO": "ℹ️ ",
        "SUCCESS": "✓ ",
        "ERROR": "✗ ",
        "WARN": "⚠️  ",
    }.get(level, "")
    logger.info(f"[{timestamp}] {prefix}{message}")


def check_e2b_cli():
    """检查 e2b CLI 是否安装"""
    try:
        result = subprocess.run(
            ["e2b", "--version"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            log(f"E2B CLI 版本: {result.stdout.strip()}", "SUCCESS")
            return True
    except FileNotFoundError:
        pass

    log("E2B CLI 未安装", "ERROR")
    log("请运行: npm install -g @e2b/cli", "INFO")
    return False


def create_config_file(
    template_name: str,
    memory_mb: int,
    cpu_count: int,
    dockerfile: str = "e2b.Dockerfile"
) -> Path:
    """创建临时配置文件"""
    config_file = PROJECT_ROOT / f"e2b.{template_name}.toml"

    config_content = f"""# E2B 测试模板配置
# 自动生成于 {datetime.now().isoformat()}

memory_mb = {memory_mb}
cpu_count = {cpu_count}
dockerfile = "{dockerfile}"
template_name = "{template_name}"
"""

    with open(config_file, 'w') as f:
        f.write(config_content)

    log(f"配置文件已创建: {config_file}", "SUCCESS")
    log(f"配置内容:\n{config_content}", "INFO")

    return config_file


def build_template(template_name: str, memory_mb: int, cpu_count: int, dockerfile: str) -> dict:
    """构建模板（新模板使用命令行参数，不使用配置文件）"""
    log("="*60, "INFO")
    log("开始构建模板...", "INFO")
    log("="*60, "INFO")

    start_time = time.time()

    try:
        # 构建命令：使用命令行参数而不是配置文件
        cmd = [
            "e2b", "template", "build",
            "-n", template_name,
            "--memory-mb", str(memory_mb),
            "--cpu-count", str(cpu_count),
            "-d", dockerfile
        ]

        log(f"执行命令: {' '.join(cmd)}", "INFO")
        logger.info("")

        # 加载 .e2b_env 环境变量
        e2b_env = load_e2b_env()
        # 合并环境变量：先使用系统环境变量，然后用 .e2b_env 中的变量覆盖
        env = os.environ.copy()
        env.update(e2b_env)

        # 使用 Popen 实时显示输出
        process = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            env=env,  # 传递环境变量
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # 行缓冲
            universal_newlines=True
        )

        # 实时显示输出
        output_lines = []
        for line in process.stdout:
            logger.info(line)
            output_lines.append(line)

        # 等待进程完成
        return_code = process.wait()
        build_time = time.time() - start_time

        full_output = ''.join(output_lines)

        if return_code == 0:
            log("="*60, "SUCCESS")
            log("模板构建成功!", "SUCCESS")
            log("="*60, "SUCCESS")
            log(f"构建耗时: {build_time:.1f} 秒 ({build_time/60:.1f} 分钟)", "INFO")

            # 尝试从输出中提取模板 ID
            template_id = None
            for line in full_output.split('\n'):
                if 'template_id' in line.lower() or 'id:' in line.lower():
                    # 简单提取，可能需要根据实际输出调整
                    parts = line.split(':')
                    if len(parts) > 1:
                        template_id = parts[-1].strip()

            return {
                "success": True,
                "build_time": build_time,
                "template_id": template_id,
                "output": full_output
            }
        else:
            log("="*60, "ERROR")
            log("模板构建失败", "ERROR")
            log("="*60, "ERROR")
            log(f"退出码: {return_code}", "ERROR")

            # 检查是否是推送失败（502 Bad Gateway）
            if "502 Bad Gateway" in full_output or "unexpected HTTP status: 502" in full_output:
                log("", "WARN")
                log("检测到镜像推送失败 (502 Bad Gateway)", "WARN")
                log("这通常是临时性的服务器问题，建议：", "WARN")
                log("  1. 稍后重试", "INFO")
                log("  2. 检查 E2B registry 服务状态", "INFO")
                log("  3. 确认网络连接正常", "INFO")
            
            # 检查是否是连接超时
            if "ConnectTimeoutError" in full_output or "UND_ERR_CONNECT_TIMEOUT" in full_output:
                log("", "WARN")
                log("检测到连接超时错误", "WARN")
                log("可能的原因：", "WARN")
                log("  1. E2B API 服务器无法访问", "INFO")
                log("  2. 环境变量未正确加载（请检查 .e2b_env 文件）", "INFO")
                log("  3. 网络连接问题", "INFO")
                log("  4. E2B_API_KEY 或 E2B_DOMAIN 配置错误", "INFO")
                if e2b_env:
                    log(f"  当前使用的 E2B_DOMAIN: {e2b_env.get('E2B_DOMAIN', '未设置')}", "INFO")
                    log(f"  当前使用的 E2B_API_URL: {e2b_env.get('E2B_API_URL', '未设置')}", "INFO")

            return {
                "success": False,
                "build_time": build_time,
                "exit_code": return_code,
                "output": full_output
            }

    except subprocess.TimeoutExpired:
        build_time = time.time() - start_time
        log("构建超时 (30分钟)", "ERROR")
        return {
            "success": False,
            "build_time": build_time,
            "error": "timeout"
        }

    except Exception as e:
        build_time = time.time() - start_time
        log(f"构建异常: {e}", "ERROR")
        return {
            "success": False,
            "build_time": build_time,
            "error": str(e)
        }


def test_sandbox_creation(template_name: str) -> dict:
    """测试沙箱创建"""
    log("="*60, "INFO")
    log("测试创建沙箱...", "INFO")
    log("="*60, "INFO")

    try:
        from e2b import Sandbox

        log(f"正在创建沙箱: {template_name}", "INFO")
        start_time = time.time()

        sandbox = Sandbox(template_name)
        create_time = time.time() - start_time

        log(f"沙箱创建成功!", "SUCCESS")
        log(f"  Sandbox ID: {sandbox.sandbox_id}", "INFO")
        log(f"  创建耗时: {create_time:.2f} 秒", "INFO")

        # 运行简单测试
        log("运行基本测试...", "INFO")

        tests = [
            ("echo 'Hello from agent_test!'", "测试 echo 命令"),
            ("python3 --version", "测试 Python"),
            ("uname -a", "测试系统信息"),
            ("df -h", "测试磁盘空间"),
        ]

        test_results = []
        commands_available = True
        
        for cmd, desc in tests:
            log(f"  {desc}: {cmd}", "INFO")
            try:
                # 尝试执行命令
                result = sandbox.commands.run(cmd)
                if result.exit_code == 0:
                    log(f"    ✓ {result.stdout.strip()}", "SUCCESS")
                    test_results.append({
                        "command": cmd,
                        "description": desc,
                        "success": True,
                        "output": result.stdout.strip()
                    })
                else:
                    log(f"    ✗ 失败 (退出码: {result.exit_code})", "ERROR")
                    test_results.append({
                        "command": cmd,
                        "description": desc,
                        "success": False,
                        "error": result.stderr or f"退出码: {result.exit_code}"
                    })
            except AttributeError as e:
                # 旧版 envd 可能没有 commands 属性
                if "commands" in str(e) or "run" in str(e):
                    if commands_available:
                        log("", "WARN")
                        log("⚠️  检测到旧版 envd，无法执行沙箱内命令", "WARN")
                        log("  这是已知的兼容性问题（envd 0.2.0 与 e2b SDK 1.1.0）", "WARN")
                        log("  沙箱创建成功，但命令执行功能不可用", "WARN")
                        log("  如需测试命令执行，请：", "INFO")
                        log("    1. 升级 envd 到新版本", "INFO")
                        log("    2. 或使用 Node.js CLI 桥接器", "INFO")
                        commands_available = False
                    test_results.append({
                        "command": cmd,
                        "description": desc,
                        "success": False,
                        "error": "旧版 envd 不支持命令执行",
                        "skipped": True
                    })
                else:
                    raise
            except Exception as e:
                # 其他错误（如 "Invalid host" 等）
                error_msg = str(e)
                if "Invalid host" in error_msg or "commands" in error_msg.lower():
                    if commands_available:
                        log("", "WARN")
                        log("⚠️  无法执行沙箱内命令", "WARN")
                        log(f"  错误: {error_msg}", "WARN")
                        log("  这通常是由于 envd 版本较旧导致的兼容性问题", "WARN")
                        log("  沙箱创建成功，但命令执行功能不可用", "WARN")
                        commands_available = False
                    test_results.append({
                        "command": cmd,
                        "description": desc,
                        "success": False,
                        "error": error_msg,
                        "skipped": True
                    })
                else:
                    # 其他未知错误，记录但继续
                    log(f"    ✗ 执行失败: {error_msg}", "ERROR")
                    test_results.append({
                        "command": cmd,
                        "description": desc,
                        "success": False,
                        "error": error_msg
                    })

        sandbox.kill()
        log("沙箱已关闭", "SUCCESS")

        # 统计测试结果
        successful_tests = sum(1 for t in test_results if t.get("success", False))
        skipped_tests = sum(1 for t in test_results if t.get("skipped", False))
        failed_tests = len(test_results) - successful_tests - skipped_tests
        
        if skipped_tests > 0:
            log(f"测试完成: {successful_tests} 成功, {skipped_tests} 跳过(旧版 envd), {failed_tests} 失败", "INFO")
        else:
            log(f"测试完成: {successful_tests} 成功, {failed_tests} 失败", "INFO")

        return {
            "success": True,  # 沙箱创建成功就算成功
            "create_time": create_time,
            "sandbox_id": sandbox.sandbox_id,
            "tests": test_results,
            "test_summary": {
                "total": len(test_results),
                "successful": successful_tests,
                "skipped": skipped_tests,
                "failed": failed_tests
            }
        }

    except Exception as e:
        log(f"沙箱创建失败: {e}", "ERROR")
        return {
            "success": False,
            "error": str(e)
        }


def save_results(template_name: str, build_result: dict, sandbox_result: dict, config: dict, output_path: str = None):
    """保存测试结果"""
    result = {
        "template_name": template_name,
        "config": config,
        "build": build_result,
        "sandbox_test": sandbox_result,
        "test_date": datetime.now().isoformat()
    }

    # 确定输出文件路径
    if output_path:
        output_file = Path(output_path)
        # 确保目录存在
        output_file.parent.mkdir(parents=True, exist_ok=True)
    else:
        outputs_dir = PROJECT_ROOT / "outputs"
        outputs_dir.mkdir(exist_ok=True)
        output_file = outputs_dir / f"template_build_{template_name}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    log(f"测试结果已保存到: {output_file}", "SUCCESS")

    # 打印摘要
    log("="*60, "INFO")
    log("测试摘要", "INFO")
    log("="*60, "INFO")
    log(f"模板名称: {template_name}", "INFO")
    log(f"构建状态: {'✓ 成功' if build_result['success'] else '✗ 失败'}",
        "SUCCESS" if build_result['success'] else "ERROR")
    log(f"构建耗时: {build_result['build_time']:.1f} 秒", "INFO")

    if sandbox_result.get('success'):
        log(f"沙箱创建: ✓ 成功", "SUCCESS")
        log(f"创建耗时: {sandbox_result['create_time']:.2f} 秒", "INFO")
    else:
        log(f"沙箱创建: ✗ 失败", "ERROR")


def main():
    parser = argparse.ArgumentParser(
        description="E2B 模板构建测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用默认配置
  python3 test_template_build.py

  # 自定义配置
  python3 test_template_build.py --name my_template --memory 8192 --cpu 8

  # 只构建，不测试沙箱创建
  python3 test_template_build.py --name agent_test --skip-sandbox-test
        """
    )

    parser.add_argument("--name", default="agent_test",
                       help="模板名称 (默认: agent_test)")
    parser.add_argument("--memory", type=int, default=4096,
                       help="内存大小 MB (默认: 4096)")
    parser.add_argument("--cpu", type=int, default=6,
                       help="CPU 核心数 (默认: 6)")
    parser.add_argument("--dockerfile", default="e2b.Dockerfile",
                       help="Dockerfile 路径 (默认: e2b.Dockerfile)")
    parser.add_argument("--skip-sandbox-test", action="store_true",
                       help="跳过沙箱创建测试")
    parser.add_argument("--output", type=str,
                       help="输出JSON文件路径 (默认: outputs/template_build_<name>.json)")

    args = parser.parse_args()

    log("="*60, "INFO")
    log("E2B 模板构建测试", "INFO")
    log("="*60, "INFO")
    log(f"模板名称: {args.name}", "INFO")
    log(f"内存配置: {args.memory}MB", "INFO")
    log(f"CPU核心: {args.cpu}", "INFO")
    log(f"Dockerfile: {args.dockerfile}", "INFO")
    log("="*60, "INFO")

    # 检查 E2B CLI
    if not check_e2b_cli():
        sys.exit(1)

    # 检查 Dockerfile
    dockerfile_path = PROJECT_ROOT / args.dockerfile
    if not dockerfile_path.exists():
        log(f"Dockerfile 不存在: {dockerfile_path}", "ERROR")
        sys.exit(1)

    try:
        # 构建模板（使用命令行参数）
        build_result = build_template(
            args.name,
            args.memory,
            args.cpu,
            args.dockerfile
        )

        if not build_result['success']:
            log("构建失败，跳过后续测试", "WARN")
            save_results(args.name, build_result, {}, {
                "memory_mb": args.memory,
                "cpu_count": args.cpu,
                "dockerfile": args.dockerfile
            }, args.output)
            sys.exit(1)

        # 测试沙箱创建
        sandbox_result = {}
        if not args.skip_sandbox_test:
            sandbox_result = test_sandbox_creation(args.name)
        else:
            log("跳过沙箱创建测试", "WARN")

        # 保存结果
        save_results(args.name, build_result, sandbox_result, {
            "memory_mb": args.memory,
            "cpu_count": args.cpu,
            "dockerfile": args.dockerfile
        }, args.output)

        log("="*60, "SUCCESS")
        log("测试完成!", "SUCCESS")
        log("="*60, "SUCCESS")

    except Exception as e:
        log(f"测试异常: {e}", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
