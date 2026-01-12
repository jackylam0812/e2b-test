#!/usr/bin/env python3
"""
自动化沙箱性能测试脚本
使用 E2B SDK 的 sandbox.commands API 自动执行测试
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# 禁用 SSL 证书验证
import ssl
ssl._create_default_https_context = ssl._create_unverified_context

# Monkey patch httpx 禁用 SSL 验证
import httpx
_original_client_init = httpx.Client.__init__
def _patched_client_init(self, *args, **kwargs):
    kwargs.setdefault('verify', False)
    return _original_client_init(self, *args, **kwargs)
httpx.Client.__init__ = _patched_client_init

# Monkey patch NewSandbox 模型，添加 secure=false 禁用 envd 安全认证
import e2b.api.client.models.new_sandbox as new_sandbox_module
_original_to_dict = new_sandbox_module.NewSandbox.to_dict
def _patched_to_dict(self):
    result = _original_to_dict(self)
    result['secure'] = False  # 禁用 envd 安全认证
    return result
new_sandbox_module.NewSandbox.to_dict = _patched_to_dict

from e2b import Sandbox

# 从环境变量获取配置
E2B_API_KEY = os.environ.get('E2B_API_KEY')
E2B_DOMAIN = os.environ.get('E2B_DOMAIN')
E2B_TEMPLATE = os.environ.get('E2B_TEMPLATE_NAME')

if not E2B_API_KEY:
    print("错误: 请设置 E2B_API_KEY 环境变量")
    sys.exit(1)


class SandboxTester:
    """沙箱性能测试器"""

    def __init__(self, output_dir="outputs/sandbox_tests"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.test_scripts_dir = Path(__file__).parent
        self.sandbox = None

    def create_sandbox(self):
        """创建沙箱"""
        print("\n" + "=" * 60)
        print("创建沙箱...")
        print("=" * 60)

        if E2B_TEMPLATE:
            self.sandbox = Sandbox(
                template=E2B_TEMPLATE,
                api_key=E2B_API_KEY,
                timeout=1800  # 30分钟
            )
        else:
            self.sandbox = Sandbox(
                api_key=E2B_API_KEY,
                timeout=1800
            )

        print(f"✓ 沙箱已创建: {self.sandbox.sandbox_id}")
        return self.sandbox

    def close_sandbox(self):
        """关闭沙箱"""
        if self.sandbox:
            print("\n" + "=" * 60)
            print("关闭沙箱...")
            print("=" * 60)
            try:
                self.sandbox.kill()
                print("✓ 沙箱已关闭")
            except Exception as e:
                # 404 错误通常表示沙箱已经不存在了（可能已被删除或超时）
                if "404" in str(e):
                    print("✓ 沙箱已经不存在（可能已被自动清理）")
                else:
                    print(f"⚠ 关闭沙箱失败: {e}")

    def run_cpu_test(self):
        """运行 CPU 性能测试"""
        print("\n" + "=" * 60)
        print("运行 CPU 性能测试")
        print("=" * 60)

        # 读取测试脚本（从备份目录）
        script_path = self.test_scripts_dir / "_deprecated_shell_scripts" / "run_cpu_test.sh"
        with open(script_path, 'r') as f:
            script_content = f.read()

        # 上传脚本到沙箱
        self.sandbox.files.write("/tmp/run_cpu_test.sh", script_content)
        print("✓ 测试脚本已上传")

        # 添加执行权限
        self.sandbox.commands.run("chmod +x /tmp/run_cpu_test.sh")

        # 执行测试（实时显示输出）
        print("\n开始执行测试（这可能需要一些时间）...")
        print("-" * 60)

        def on_stdout(line):
            if line.strip():
                print(f"  {line.rstrip()}")

        result = self.sandbox.commands.run(
            "/tmp/run_cpu_test.sh",
            on_stdout=on_stdout,
            timeout=300,
            user="root"  # 需要 root 权限安装 sysbench
        )

        print("-" * 60)

        if result.exit_code != 0:
            print(f"✗ 测试失败，退出码: {result.exit_code}")
            if result.stderr:
                print(f"错误信息: {result.stderr}")
            return None

        # 读取结果
        try:
            result_json = self.sandbox.files.read("/tmp/sandbox_cpu_result.json")
            result_data = json.loads(result_json)

            # 保存结果到本地
            output_file = self.output_dir / f"cpu_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)

            print(f"✓ 测试完成，结果已保存到: {output_file}")
            return result_data
        except Exception as e:
            print(f"✗ 读取结果失败: {e}")
            return None

    def run_memory_test(self):
        """运行内存性能测试"""
        print("\n" + "=" * 60)
        print("运行内存性能测试")
        print("=" * 60)

        # 读取测试脚本（从备份目录）
        script_path = self.test_scripts_dir / "_deprecated_shell_scripts" / "run_memory_test.sh"
        with open(script_path, 'r') as f:
            script_content = f.read()

        # 上传脚本到沙箱
        self.sandbox.files.write("/tmp/run_memory_test.sh", script_content)
        print("✓ 测试脚本已上传")

        # 添加执行权限
        self.sandbox.commands.run("chmod +x /tmp/run_memory_test.sh")

        # 执行测试（实时显示输出）
        print("\n开始执行测试（这可能需要一些时间）...")
        print("-" * 60)

        def on_stdout(line):
            if line.strip():
                print(f"  {line.rstrip()}")

        result = self.sandbox.commands.run(
            "/tmp/run_memory_test.sh",
            on_stdout=on_stdout,
            timeout=600,
            user="root"
        )

        print("-" * 60)

        if result.exit_code != 0:
            print(f"✗ 测试失败，退出码: {result.exit_code}")
            if result.stderr:
                print(f"错误信息: {result.stderr}")
            return None

        # 读取结果
        try:
            result_json = self.sandbox.files.read("/tmp/sandbox_memory_result.json")
            result_data = json.loads(result_json)

            # 保存结果到本地
            output_file = self.output_dir / f"memory_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)

            print(f"✓ 测试完成，结果已保存到: {output_file}")
            return result_data
        except Exception as e:
            print(f"✗ 读取结果失败: {e}")
            return None

    def run_disk_test(self):
        """运行磁盘性能测试"""
        print("\n" + "=" * 60)
        print("运行磁盘性能测试")
        print("=" * 60)

        # 读取测试脚本（从备份目录）
        script_path = self.test_scripts_dir / "_deprecated_shell_scripts" / "run_disk_test.sh"
        if not script_path.exists():
            print("⚠ 磁盘测试脚本不存在，跳过")
            return None

        with open(script_path, 'r') as f:
            script_content = f.read()

        # 上传脚本到沙箱
        self.sandbox.files.write("/tmp/run_disk_test.sh", script_content)
        print("✓ 测试脚本已上传")

        # 添加执行权限
        self.sandbox.commands.run("chmod +x /tmp/run_disk_test.sh")

        # 执行测试（实时显示输出）
        print("\n开始执行测试（这可能需要一些时间）...")
        print("-" * 60)

        def on_stdout(line):
            if line.strip():
                print(f"  {line.rstrip()}")

        result = self.sandbox.commands.run(
            "/tmp/run_disk_test.sh",
            on_stdout=on_stdout,
            timeout=600,
            user="root"
        )

        print("-" * 60)

        if result.exit_code != 0:
            print(f"✗ 测试失败，退出码: {result.exit_code}")
            if result.stderr:
                print(f"错误信息: {result.stderr}")
            return None

        # 读取结果
        try:
            result_json = self.sandbox.files.read("/tmp/sandbox_disk_result.json")
            result_data = json.loads(result_json)

            # 保存结果到本地
            output_file = self.output_dir / f"disk_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w') as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)

            print(f"✓ 测试完成，结果已保存到: {output_file}")
            return result_data
        except Exception as e:
            print(f"✗ 读取结果失败: {e}")
            return None

    def run_network_test(self):
        """运行网络性能测试"""
        print("\n" + "=" * 60)
        print("运行网络性能测试")
        print("=" * 60)

        # 读取测试脚本
        script_path = self.test_scripts_dir / "test_network_improved.sh"
        if not script_path.exists():
            print("⚠ 网络测试脚本不存在，跳过")
            return None

        with open(script_path, 'r') as f:
            script_content = f.read()

        # 上传脚本到沙箱
        self.sandbox.files.write("/tmp/run_network_test.sh", script_content)
        print("✓ 测试脚本已上传")

        # 添加执行权限
        self.sandbox.commands.run("chmod +x /tmp/run_network_test.sh")

        # 安装必要的工具（bc 用于浮点数计算）
        print("✓ 安装测试依赖...")
        install_result = self.sandbox.commands.run(
            "apt-get update -qq && apt-get install -y -qq bc curl iputils-ping 2>&1 | grep -v 'debconf\\|WARNING' || true",
            timeout=120,
            user="root"
        )

        # 执行测试（实时显示输出）
        print("\n开始执行测试（这可能需要一些时间）...")
        print("-" * 60)

        def on_stdout(line):
            if line.strip():
                print(f"  {line.rstrip()}")

        result = self.sandbox.commands.run(
            "/tmp/run_network_test.sh",
            on_stdout=on_stdout,
            timeout=300,
            user="user"  # 网络测试不需要 root 权限
        )

        print("-" * 60)

        if result.exit_code != 0:
            print(f"✗ 测试失败，退出码: {result.exit_code}")
            if result.stderr:
                print(f"错误信息: {result.stderr}")
            return None

        # 从输出中提取 JSON 结果
        # 网络测试脚本直接输出 JSON 到 stdout
        try:
            stdout = result.stdout

            # 按行分割，找到包含 JSON 的行
            lines = stdout.split('\n')
            json_lines = []
            in_json = False
            brace_count = 0

            for line in lines:
                # 检测 JSON 开始
                if '{' in line and not in_json:
                    in_json = True
                    brace_count = 0

                if in_json:
                    json_lines.append(line)
                    brace_count += line.count('{') - line.count('}')

                    # JSON 结束
                    if brace_count == 0:
                        break

            if json_lines:
                json_str = '\n'.join(json_lines)

                # 修复 JSON 中的数字格式问题（如 .96 -> 0.96）
                import re
                json_str = re.sub(r':\s*\.(\d+)', r': 0.\1', json_str)

                result_data = json.loads(json_str)

                # 保存结果到本地
                output_file = self.output_dir / f"network_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(output_file, 'w') as f:
                    json.dump(result_data, f, indent=2, ensure_ascii=False)

                print(f"✓ 测试完成，结果已保存到: {output_file}")
                return result_data
            else:
                print("✗ 无法从输出中提取 JSON 结果")
                return None
        except Exception as e:
            print(f"✗ 解析结果失败: {e}")
            return None

    def run_network_diagnose(self):
        """运行网络诊断"""
        print("\n" + "=" * 60)
        print("运行网络诊断")
        print("=" * 60)

        # 读取诊断脚本
        script_path = self.test_scripts_dir / "diagnose_network.sh"
        if not script_path.exists():
            print("⚠ 网络诊断脚本不存在，跳过")
            return None

        with open(script_path, 'r') as f:
            script_content = f.read()

        # 上传脚本到沙箱
        self.sandbox.files.write("/tmp/diagnose_network.sh", script_content)
        print("✓ 诊断脚本已上传")

        # 添加执行权限
        self.sandbox.commands.run("chmod +x /tmp/diagnose_network.sh")

        # 执行诊断（实时显示输出）
        print("\n开始诊断...")
        print("-" * 60)

        def on_stdout(line):
            if line.strip():
                print(f"  {line.rstrip()}")

        result = self.sandbox.commands.run(
            "/tmp/diagnose_network.sh",
            on_stdout=on_stdout,
            timeout=120,
            user="root"  # 诊断需要 root 权限查看某些信息
        )

        print("-" * 60)

        if result.exit_code != 0:
            print(f"⚠ 诊断脚本退出码: {result.exit_code}")

        # 保存诊断输出
        output_file = self.output_dir / f"network_diagnose_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(output_file, 'w') as f:
            f.write(result.stdout)

        print(f"✓ 诊断完成，输出已保存到: {output_file}")
        return result.stdout

    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "=" * 60)
        print("沙箱性能自动化测试")
        print("=" * 60)
        print(f"E2B 域名: {E2B_DOMAIN}")
        print(f"模板: {E2B_TEMPLATE or '默认'}")
        print(f"输出目录: {self.output_dir}")
        print("=" * 60)

        results = {}
        start_time = time.time()

        try:
            # 创建沙箱
            self.create_sandbox()

            # 运行 CPU 测试
            cpu_result = self.run_cpu_test()
            if cpu_result:
                results['cpu'] = cpu_result

            # 运行内存测试
            memory_result = self.run_memory_test()
            if memory_result:
                results['memory'] = memory_result

            # 运行磁盘测试
            disk_result = self.run_disk_test()
            if disk_result:
                results['disk'] = disk_result

            # 运行网络测试
            network_result = self.run_network_test()
            if network_result:
                results['network'] = network_result

        except KeyboardInterrupt:
            print("\n\n⚠ 测试被用户中断")
        except Exception as e:
            print(f"\n\n✗ 测试出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # 关闭沙箱
            self.close_sandbox()

        # 生成汇总报告
        elapsed_time = time.time() - start_time
        summary = {
            "test_time": datetime.now().isoformat(),
            "elapsed_seconds": elapsed_time,
            "sandbox_id": self.sandbox.sandbox_id if self.sandbox else None,
            "e2b_domain": E2B_DOMAIN,
            "template": E2B_TEMPLATE,
            "results": results
        }

        # 保存汇总报告
        summary_file = self.output_dir / f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        # 打印汇总
        print("\n" + "=" * 60)
        print("测试汇总")
        print("=" * 60)
        print(f"总耗时: {elapsed_time:.2f} 秒")
        print(f"完成的测试: {len(results)}")
        if 'cpu' in results:
            print(f"  ✓ CPU 测试")
        if 'memory' in results:
            print(f"  ✓ 内存测试")
        if 'disk' in results:
            print(f"  ✓ 磁盘测试")
        if 'network' in results:
            print(f"  ✓ 网络测试")
        print(f"\n汇总报告: {summary_file}")
        print("=" * 60)

        return results


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='自动化沙箱性能测试',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行所有测试
  python3 run_sandbox_tests.py

  # 指定输出目录
  python3 run_sandbox_tests.py --output outputs/my_tests

  # 只运行 CPU 测试
  python3 run_sandbox_tests.py --test cpu

  # 运行 CPU 和内存测试
  python3 run_sandbox_tests.py --test cpu memory

  # 运行网络测试
  python3 run_sandbox_tests.py --test network

  # 运行网络诊断
  python3 run_sandbox_tests.py --diagnose
        """
    )

    parser.add_argument(
        '--output',
        type=str,
        default='outputs/sandbox_tests',
        help='输出目录 (默认: outputs/sandbox_tests)'
    )

    parser.add_argument(
        '--test',
        nargs='+',
        choices=['cpu', 'memory', 'disk', 'network', 'all'],
        default=['all'],
        help='要运行的测试 (默认: all)'
    )

    parser.add_argument(
        '--diagnose',
        action='store_true',
        help='运行网络诊断（不包含在 all 中）'
    )

    args = parser.parse_args()

    # 创建测试器
    tester = SandboxTester(output_dir=args.output)

    # 创建沙箱
    try:
        tester.create_sandbox()

        # 如果指定了诊断，运行诊断
        if args.diagnose:
            tester.run_network_diagnose()
        # 运行指定的测试
        elif 'all' in args.test:
            tester.run_all_tests()
        else:
            if 'cpu' in args.test:
                tester.run_cpu_test()
            if 'memory' in args.test:
                tester.run_memory_test()
            if 'disk' in args.test:
                tester.run_disk_test()
            if 'network' in args.test:
                tester.run_network_test()

    finally:
        tester.close_sandbox()


if __name__ == '__main__':
    main()
