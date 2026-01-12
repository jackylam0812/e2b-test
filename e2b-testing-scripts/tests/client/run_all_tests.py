#!/usr/bin/env python3
"""
E2B 客户端性能测试 - 主运行脚本

自动执行客户端测试并生成报告:
1. 沙箱生命周期测试 (冷启动/热启动)
2. 模板快照测试 (模板构建/快照性能)
3. 沙箱容量测试 (并发容量/负载均衡)
4. 模板构建测试 (构建时间/功能验证)

环境变量 (必须通过 .e2b_env 配置):
- E2B_DOMAIN: E2B 服务域名 (必需)
- E2B_API_KEY: E2B API 密钥 (必需)
- E2B_TEMPLATE_NAME: 模板名称 (可选)
- NOMAD_ADDR: Nomad 服务地址 (部分测试需要)
- NOMAD_TOKEN: Nomad 访问令牌 (部分测试需要)
- E2B_ORCHESTRATOR_JOB: Orchestrator job 名称 (默认: orchestrator)
- E2B_DEFAULT_ITERATIONS: 默认迭代次数 (默认: 3)
- CLOUD_PROVIDER: 云服务商标识 (用于报告)

使用方法:
  source .e2b_env
  python3 tests/client/run_all_tests.py --all
  python3 tests/client/run_all_tests.py --lifecycle --capacity
"""

import os
import sys
import json
import time
import datetime
import subprocess
from pathlib import Path
from typing import Dict, Any

# 导入彩色日志
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import get_logger

logger = get_logger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
CLIENT_SCRIPTS = Path(__file__).parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# 确保输出目录存在
OUTPUTS_DIR.mkdir(exist_ok=True)


def check_dependencies():
    """检查必需的 Python 依赖"""
    missing_deps = []

    # 检查核心依赖
    try:
        import e2b
    except ImportError:
        missing_deps.append("e2b")

    try:
        import yaml
    except ImportError:
        missing_deps.append("pyyaml")

    if missing_deps:
        logger.info("\n" + "="*60)
        logger.error("错误: 缺少必需的 Python 依赖")
        logger.info("="*60)
        logger.info(f"\n缺少的依赖: {', '.join(missing_deps)}\n")
        logger.info("请运行以下命令安装依赖:")
        logger.info("  pip3 install -r requirements.txt")
        logger.info("\n或手动安装:")
        logger.info(f"  pip3 install {' '.join(missing_deps)}")
        logger.info("\n" + "="*60 + "\n")
        sys.exit(1)


def check_environment():
    """检查必需的环境变量"""
    required_vars = ['E2B_DOMAIN', 'E2B_API_KEY']
    missing_vars = [var for var in required_vars if var not in os.environ]

    if missing_vars:
        logger.info("\n" + "="*60)
        logger.error("错误: 缺少必需的环境变量")
        logger.info("="*60)
        logger.info(f"\n缺少的变量: {', '.join(missing_vars)}\n")
        logger.info("请先配置并加载环境变量:")
        logger.info("  1. 编辑 .e2b_env 文件")
        logger.info("  2. 运行: source .e2b_env")
        logger.info("\n" + "="*60 + "\n")
        sys.exit(1)


def log(message: str, level: str = "INFO"):
    """打印日志"""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    prefix = {
        "INFO": "ℹ️ ",
        "SUCCESS": "✓ ",
        "ERROR": "✗ ",
        "WARN": "⚠️  ",
    }.get(level, "")
    logger.info(f"[{timestamp}] {prefix}{message}")


def run_script(script_path: Path, args: list, description: str) -> Dict[str, Any]:
    """
    运行测试脚本（实时显示输出）

    Args:
        script_path: 脚本路径
        args: 命令行参数
        description: 测试描述

    Returns:
        包含结果和元数据的字典
    """
    log(f"开始: {description}", "INFO")
    logger.info("")  # 空行分隔

    start_time = time.time()

    try:
        # 构建命令
        cmd = ["python3", str(script_path)] + args

        # 使用 Popen 实时显示输出
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # 合并 stderr 到 stdout
            text=True,
            bufsize=1,  # 行缓冲
            cwd=str(PROJECT_ROOT)
        )

        # 实时读取并显示输出
        stdout_lines = []
        try:
            for line in process.stdout:
                # 打印到终端（实时显示）
                print(line, end='', flush=True)
                # 保存到列表（用于报告）
                stdout_lines.append(line)

            # 等待进程结束（带超时）
            process.wait(timeout=1800)  # 30分钟超时

        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            elapsed_time = time.time() - start_time
            log(f"\n超时: {description} (超过30分钟)", "ERROR")
            return {
                "success": False,
                "elapsed_time": elapsed_time,
                "error": "timeout",
                "stdout": "".join(stdout_lines)
            }

        elapsed_time = time.time() - start_time
        stdout_text = "".join(stdout_lines)

        # 空行分隔
        logger.info("")

        if process.returncode == 0:
            log(f"完成: {description} (耗时 {elapsed_time:.1f}s)", "SUCCESS")
            return {
                "success": True,
                "elapsed_time": elapsed_time,
                "stdout": stdout_text,
                "stderr": ""
            }
        else:
            log(f"失败: {description} (退出码 {process.returncode})", "ERROR")
            return {
                "success": False,
                "elapsed_time": elapsed_time,
                "exit_code": process.returncode,
                "stdout": stdout_text,
                "stderr": ""
            }

    except Exception as e:
        elapsed_time = time.time() - start_time
        log(f"异常: {description} - {e}", "ERROR")
        return {
            "success": False,
            "elapsed_time": elapsed_time,
            "error": str(e)
        }


def load_json_result(file_path: Path) -> Dict:
    """加载JSON结果文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log(f"无法加载 {file_path}: {e}", "WARN")
        return {}


def main():
    """主函数"""
    # 首先检查依赖和环境变量
    check_dependencies()
    check_environment()

    import argparse

    parser = argparse.ArgumentParser(
        description="E2B 客户端性能测试套件",
        epilog="支持多种测试：生命周期、模板快照、容量、模板构建"
    )

    # 测试选择
    test_group = parser.add_argument_group('测试选择')
    test_group.add_argument("--all", action="store_true",
                           help="运行所有测试")
    test_group.add_argument("--lifecycle", action="store_true",
                           help="运行沙箱生命周期测试")
    test_group.add_argument("--snapshot", action="store_true",
                           help="运行模板快照测试")
    test_group.add_argument("--capacity", action="store_true",
                           help="运行沙箱容量测试")
    test_group.add_argument("--template-build", action="store_true",
                           help="运行模板构建测试")

    # 参数配置
    param_group = parser.add_argument_group('参数配置')
    param_group.add_argument("--iterations", type=int,
                            help="测试迭代次数(默认从环境变量读取)")
    param_group.add_argument("--cold-iterations", type=int,
                            help="冷启动测试次数(默认3次)")
    param_group.add_argument("--warm-iterations", type=int,
                            help="热启动测试次数(默认10次)")
    param_group.add_argument("--batch-size", type=int, default=10,
                            help="容量测试批次大小(默认10)")
    param_group.add_argument("--max-sandboxes", type=int, default=100,
                            help="容量测试最大沙箱数(默认100)")
    param_group.add_argument("--output-dir", type=str,
                            help="输出目录(默认: outputs/)")

    args = parser.parse_args()

    # 如果没有指定任何测试，显示帮助
    if not any([args.all, args.lifecycle, args.snapshot, args.capacity, args.template_build]):
        parser.print_help()
        return 0

    # 配置
    template = os.getenv('E2B_TEMPLATE_NAME', 'agent_test')
    iterations = args.iterations or int(os.getenv('E2B_DEFAULT_ITERATIONS', '3'))
    cold_iterations = args.cold_iterations or 3
    warm_iterations = args.warm_iterations or 10
    output_dir = Path(args.output_dir) if args.output_dir else OUTPUTS_DIR
    output_dir.mkdir(exist_ok=True)

    # 云服务商标识
    cloud_provider = os.getenv('CLOUD_PROVIDER', 'unknown')

    # 测试开始
    log("="*60, "INFO")
    log("E2B 客户端性能测试套件", "INFO")
    log("="*60, "INFO")
    log(f"云服务商: {cloud_provider}", "INFO")
    log(f"模板: {template}", "INFO")
    log(f"迭代次数: {iterations} (冷启动: {cold_iterations}, 热启动: {warm_iterations})", "INFO")
    log(f"输出目录: {output_dir}", "INFO")
    log("="*60, "INFO")

    overall_start_time = time.time()
    test_results = {}

    # 确定要运行的测试
    run_lifecycle = args.all or args.lifecycle
    run_snapshot = args.all or args.snapshot
    run_capacity = args.all or args.capacity
    run_template_build = args.all or args.template_build

    # ========== 沙箱生命周期测试 ==========
    if run_lifecycle:
        log("\n沙箱生命周期测试", "INFO")
        log("-"*60, "INFO")

        # 冷启动
        cold_output = output_dir / "01_cold_start.json"
        result = run_script(
            CLIENT_SCRIPTS / "01_sandbox_lifecycle.py",
            ["--test", "cold", "--iterations", str(cold_iterations),
             "--template", template, "--output", str(cold_output)],
            "冷启动测试"
        )
        test_results["lifecycle_cold"] = result
        if result["success"]:
            test_results["lifecycle_cold_data"] = load_json_result(cold_output)

        # 热启动
        warm_output = output_dir / "01_warm_start.json"
        result = run_script(
            CLIENT_SCRIPTS / "01_sandbox_lifecycle.py",
            ["--test", "warm", "--iterations", str(warm_iterations),
             "--template", template, "--output", str(warm_output)],
            "热启动测试"
        )
        test_results["lifecycle_warm"] = result
        if result["success"]:
            test_results["lifecycle_warm_data"] = load_json_result(warm_output)

    # ========== 模板快照测试 ==========
    if run_snapshot:
        log("\n模板快照测试", "INFO")
        log("-"*60, "INFO")

        snapshot_output = output_dir / "02_template_snapshot.json"
        result = run_script(
            CLIENT_SCRIPTS / "02_template_snapshot.py",
            ["--output", str(snapshot_output)],
            "模板快照性能测试"
        )
        test_results["template_snapshot"] = result
        if result["success"]:
            test_results["template_snapshot_data"] = load_json_result(snapshot_output)

    # ========== 沙箱容量测试 ==========
    if run_capacity:
        log("\n沙箱容量测试", "INFO")
        log("-"*60, "INFO")

        capacity_output = output_dir / "06_sandbox_capacity.json"
        result = run_script(
            CLIENT_SCRIPTS / "06_sandbox_capacity.py",
            ["--batch-size", str(args.batch_size),
             "--max-sandboxes", str(args.max_sandboxes),
             "--output", str(capacity_output)],
            "沙箱容量测试"
        )
        test_results["sandbox_capacity"] = result
        if result["success"]:
            test_results["sandbox_capacity_data"] = load_json_result(capacity_output)

    # ========== 模板构建测试 ==========
    if run_template_build:
        log("\n模板构建测试", "INFO")
        log("-"*60, "INFO")

        build_output = output_dir / "template_build.json"
        result = run_script(
            CLIENT_SCRIPTS / "test_template_build.py",
            ["--name", template,
             "--output", str(build_output)],
            "模板构建测试"
        )
        test_results["template_build"] = result
        if result["success"]:
            test_results["template_build_data"] = load_json_result(build_output)

    # ========== 生成综合报告 ==========
    log("\n生成综合报告", "INFO")
    log("="*60, "INFO")

    overall_elapsed = time.time() - overall_start_time

    summary = {
        "metadata": {
            "cloud_provider": cloud_provider,
            "template": template,
            "test_date": datetime.datetime.now().isoformat(),
            "total_elapsed_time": overall_elapsed,
            "iterations": {
                "default": iterations,
                "cold_start": cold_iterations,
                "warm_start": warm_iterations
            }
        },
        "results": test_results
    }

    # 保存综合报告
    summary_file = output_dir / "summary_report.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    log(f"综合报告已保存: {summary_file}", "SUCCESS")

    # 打印摘要
    log("\n测试摘要", "INFO")
    log("="*60, "INFO")

    total_tests = len([k for k in test_results.keys() if not k.endswith("_data")])
    successful_tests = len([v for k, v in test_results.items()
                           if not k.endswith("_data") and v.get("success")])

    log(f"总测试数: {total_tests}", "INFO")
    log(f"成功: {successful_tests}", "SUCCESS")
    log(f"失败: {total_tests - successful_tests}", "ERROR" if successful_tests < total_tests else "INFO")
    log(f"总耗时: {overall_elapsed:.1f}s ({overall_elapsed/60:.1f}分钟)", "INFO")

    # 核心指标快速预览
    log("\n测试结果预览", "INFO")
    log("-"*60, "INFO")

    if "lifecycle_cold_data" in test_results:
        cold_data = test_results["lifecycle_cold_data"].get("cold_start", {})
        if "p95" in cold_data:
            log(f"冷启动延迟 (P95): {cold_data['p95']:.2f} ms", "INFO")

    if "lifecycle_warm_data" in test_results:
        warm_data = test_results["lifecycle_warm_data"].get("warm_start", {})
        if "p50" in warm_data:
            log(f"热启动延迟 (P50): {warm_data['p50']:.2f} ms", "INFO")

    log("="*60, "INFO")
    log("测试完成!", "SUCCESS")

    return 0 if successful_tests == total_tests else 1


if __name__ == "__main__":
    sys.exit(main())
