#!/usr/bin/env python3
"""
宿主机测试统一入口脚本

提供统一的命令行接口来运行所有宿主机性能测试，包括：
1. 硬件性能测试 (CPU、内存、磁盘、网络)
2. 云存储性能测试 (可选)
3. IO 专项测试工具集

用法:
    python3 run_host_tests.py --all                    # 运行所有测试
    python3 run_host_tests.py --cpu --memory           # 运行指定测试
    python3 run_host_tests.py --cloud-storage s3://bucket  # 测试云存储
    python3 run_host_tests.py --output /path/to/output # 指定输出目录
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# 添加父目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent.absolute()))
from utils.logger import get_logger

logger = get_logger(__name__)


class HostTestRunner:
    """宿主机测试运行器"""

    def __init__(self, output_dir: str):
        self.script_dir = Path(__file__).parent.absolute()
        self.output_dir = Path(output_dir).absolute()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {}
        }

    def run_performance_tests(self, test_types: List[str], test_dir: str = "/tmp",
                             num_sandboxes: int = 38, duration: int = 60) -> bool:
        """运行硬件性能测试"""
        logger.info("\n" + "="*60)
        logger.info("硬件性能测试")
        logger.info("="*60 + "\n")

        test_script = self.script_dir / "04_host_performance.py"
        output_file = self.output_dir / "04_host_performance.json"

        for test_type in test_types:
            logger.info(f"运行测试: {test_type}")

            try:
                cmd = [
                    sys.executable,
                    str(test_script),
                    "--test", test_type,
                    "--output", str(output_file),
                    "--test-dir", test_dir,
                    "--num-sandboxes", str(num_sandboxes),
                    "--duration", str(duration)
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10分钟超时
                )

                if result.returncode == 0:
                    logger.info(f"✓ {test_type} 测试完成")

                    # 读取测试结果
                    if output_file.exists():
                        with open(output_file, 'r') as f:
                            test_data = json.load(f)
                            self.results["tests"].update(test_data)
                else:
                    logger.error(f"✗ {test_type} 测试失败")
                    logger.error(f"错误输出: {result.stderr}")
                    self.results["tests"][test_type] = {"error": result.stderr}
                    return False

            except subprocess.TimeoutExpired:
                logger.error(f"✗ {test_type} 测试超时")
                self.results["tests"][test_type] = {"error": "timeout"}
                return False
            except Exception as e:
                logger.error(f"✗ {test_type} 测试异常: {e}")
                self.results["tests"][test_type] = {"error": str(e)}
                return False

        return True

    def run_cloud_storage_test(self, bucket_url: str) -> bool:
        """运行云存储性能测试"""
        logger.info("\n" + "="*60)
        logger.info("云存储性能测试")
        logger.info("="*60 + "\n")

        test_script = self.script_dir / "05_cloud_storage.py"
        output_file = self.output_dir / "05_cloud_storage.json"

        # 解析存储类型和bucket
        if bucket_url.startswith("s3://"):
            cloud_type = "s3"
            bucket_name = bucket_url[5:]
        elif bucket_url.startswith("gs://"):
            cloud_type = "gcs"
            bucket_name = bucket_url[5:]
        else:
            logger.error("✗ 不支持的云存储URL格式，请使用 s3:// 或 gs://")
            return False

        logger.info(f"测试 {cloud_type.upper()}: {bucket_name}")

        try:
            cmd = [
                sys.executable,
                str(test_script),
                "--bucket", bucket_name,
                "--cloud", cloud_type,
                "--test", "all",
                "--output", str(output_file)
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600
            )

            if result.returncode == 0:
                logger.info("✓ 云存储测试完成")

                # 读取测试结果
                if output_file.exists():
                    with open(output_file, 'r') as f:
                        self.results["tests"]["cloud_storage"] = json.load(f)
                return True
            else:
                logger.error("✗ 云存储测试失败")
                logger.error(f"错误输出: {result.stderr}")
                self.results["tests"]["cloud_storage"] = {"error": result.stderr}
                return False

        except subprocess.TimeoutExpired:
            logger.error("✗ 云存储测试超时")
            self.results["tests"]["cloud_storage"] = {"error": "timeout"}
            return False
        except Exception as e:
            logger.error(f"✗ 云存储测试异常: {e}")
            self.results["tests"]["cloud_storage"] = {"error": str(e)}
            return False

    def run_io_tool(self, tool_name: str, args: List[str] = None) -> bool:
        """运行 IO 测试工具"""
        logger.info("\n" + "="*60)
        logger.info(f"IO 测试工具: {tool_name}")
        logger.info("="*60 + "\n")

        tool_script = self.script_dir / "io_test_scripts" / f"{tool_name}.sh"

        if not tool_script.exists():
            logger.error(f"✗ 工具脚本不存在: {tool_script}")
            return False

        try:
            cmd = ["bash", str(tool_script)]
            if args:
                cmd.extend(args)

            result = subprocess.run(
                cmd,
                cwd=str(self.script_dir / "io_test_scripts"),
                capture_output=False,  # 直接输出到终端
                timeout=3600  # IO 测试可能需要更长时间
            )

            if result.returncode == 0:
                logger.info(f"✓ {tool_name} 完成")
                return True
            else:
                logger.error(f"✗ {tool_name} 失败")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"✗ {tool_name} 超时")
            return False
        except Exception as e:
            logger.error(f"✗ {tool_name} 异常: {e}")
            return False

    def save_summary(self):
        """保存测试汇总"""
        summary_file = self.output_dir / "host_test_summary.json"

        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        logger.info(f"\n测试汇总已保存到: {summary_file}")

        # 显示文件列表
        logger.info("\n输出文件列表:")
        for file in sorted(self.output_dir.glob("*.json")):
            size = file.stat().st_size
            logger.info(f"  {file.name} ({size:,} bytes)")

    def print_summary(self):
        """打印测试摘要"""
        logger.info("\n" + "="*60)
        logger.info("测试摘要")
        logger.info("="*60)

        total = len(self.results["tests"])
        failed = sum(1 for test in self.results["tests"].values()
                    if isinstance(test, dict) and "error" in test)
        passed = total - failed

        logger.info(f"总测试数: {total}")
        logger.info(f"通过: {passed}")
        logger.info(f"失败: {failed}")

        if failed > 0:
            logger.info("\n失败的测试:")
            for name, result in self.results["tests"].items():
                if isinstance(result, dict) and "error" in result:
                    logger.error(f"  - {name}: {result['error']}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="宿主机测试统一入口",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行所有硬件性能测试
  %(prog)s --all

  # 运行指定的测试
  %(prog)s --cpu --memory --disk

  # 运行云存储测试
  %(prog)s --cloud-storage s3://my-bucket

  # 运行 IO 专项测试工具
  %(prog)s --io-tool fio_comprehensive_test

  # 指定输出目录
  %(prog)s --all --output /tmp/test_results
        """
    )

    # 测试选项组
    test_group = parser.add_argument_group('硬件性能测试')
    test_group.add_argument('--all', action='store_true',
                           help='运行所有硬件性能测试')
    test_group.add_argument('--cpu', action='store_true',
                           help='运行 CPU 性能测试')
    test_group.add_argument('--memory', action='store_true',
                           help='运行内存性能测试')
    test_group.add_argument('--disk', action='store_true',
                           help='运行磁盘 I/O 性能测试（基础）')
    test_group.add_argument('--disk-full', action='store_true',
                           help='运行完整磁盘 I/O 测试（包含混合读写、高QD、fsync等）')
    test_group.add_argument('--nbd-workload', action='store_true',
                           help='运行 NBD 工作负载模拟测试')
    test_group.add_argument('--network', action='store_true',
                           help='运行网络性能测试')
    test_group.add_argument('--hugepages', action='store_true',
                           help='检查大页内存配置')

    # 测试参数组
    param_group = parser.add_argument_group('测试参数')
    param_group.add_argument('--test-dir', default='/tmp',
                           help='测试目录路径（默认: /tmp）')
    param_group.add_argument('--num-sandboxes', type=int, default=38,
                           help='NBD 模拟的沙箱数量（默认: 38）')
    param_group.add_argument('--duration', type=int, default=60,
                           help='NBD 工作负载测试时长（秒，默认: 60）')

    # 云存储测试
    cloud_group = parser.add_argument_group('云存储测试')
    cloud_group.add_argument('--cloud-storage', metavar='BUCKET_URL',
                            help='运行云存储测试 (例: s3://bucket-name 或 gs://bucket-name)')

    # IO 工具
    io_group = parser.add_argument_group('IO 测试工具')
    io_group.add_argument('--io-tool', metavar='TOOL',
                         choices=['fio_comprehensive_test', 'aws_ebs_monitor',
                                 'realtime_io_monitor', 'check_tail_latency',
                                 'nbd_workload_simulator'],
                         help='运行指定的 IO 测试工具')
    io_group.add_argument('--io-tool-args', metavar='ARGS', nargs='*',
                         help='传递给 IO 工具的参数')

    # 通用选项
    parser.add_argument('--output', '-o', default='../../outputs',
                       help='输出目录 (默认: ../../outputs)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='显示详细输出')

    args = parser.parse_args()

    # 如果没有指定任何测试，显示帮助
    if not any([args.all, args.cpu, args.memory, args.disk, args.disk_full,
               args.nbd_workload, args.network, args.hugepages,
               args.cloud_storage, args.io_tool]):
        parser.print_help()
        return 1

    # 创建测试运行器
    runner = HostTestRunner(args.output)

    logger.info("="*60)
    logger.info("宿主机测试")
    logger.info("="*60)
    logger.info(f"输出目录: {runner.output_dir}\n")

    success = True

    # 运行硬件性能测试
    test_types = []
    if args.all:
        # --all 包含完整磁盘测试和 NBD 工作负载
        test_types = ['cpu', 'memory', 'disk-full', 'nbd-workload', 'network', 'hugepages']
    else:
        if args.cpu:
            test_types.append('cpu')
        if args.memory:
            test_types.append('memory')
        if args.disk:
            test_types.append('disk')
        if args.disk_full:
            test_types.append('disk-full')
        if args.nbd_workload:
            test_types.append('nbd-workload')
        if args.network:
            test_types.append('network')
        if args.hugepages:
            test_types.append('hugepages')

    if test_types:
        if not runner.run_performance_tests(
            test_types,
            test_dir=args.test_dir,
            num_sandboxes=args.num_sandboxes,
            duration=args.duration
        ):
            success = False

    # 运行云存储测试
    if args.cloud_storage:
        if not runner.run_cloud_storage_test(args.cloud_storage):
            success = False

    # 运行 IO 工具
    if args.io_tool:
        tool_args = args.io_tool_args if args.io_tool_args else []
        if not runner.run_io_tool(args.io_tool, tool_args):
            success = False

    # 保存并显示摘要
    runner.save_summary()
    runner.print_summary()

    logger.info("\n" + "="*60)
    if success:
        logger.info("✓ 所有测试完成!")
    else:
        logger.error("✗ 部分测试失败!")
    logger.info("="*60 + "\n")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
