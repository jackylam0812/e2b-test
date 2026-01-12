#!/usr/bin/env python3
"""
E2B沙箱生命周期测试脚本

测试指标:
- 冷启动延迟（每次重启 orchestrator）
- 热启动延迟（模板缓存 + 进程池预热）

环境变量 (必须通过 .e2b_env 配置):
- E2B_DOMAIN: E2B 服务域名 (必需)
- E2B_API_KEY: E2B API 密钥 (必需)
- E2B_ORCHESTRATOR_JOB: Nomad orchestrator job 名称 (默认: orchestrator)
- NOMAD_ADDR: Nomad 服务地址 (冷启动测试需要)
- NOMAD_TOKEN: Nomad 访问令牌 (冷启动测试需要)

使用方法:
  source .e2b_env
  python3 01_sandbox_lifecycle.py --test cold --iterations 3
"""

import os
import sys
import ssl
import time
import json
import statistics
from typing import List, Dict

# ========== 禁用 SSL 证书验证 ==========
# 设置所有可能的环境变量
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['SSL_CERT_FILE'] = ''
os.environ['SSL_CERT_DIR'] = ''
os.environ['REQUESTS_VERIFY'] = 'false'

# 创建不验证证书的 SSL 上下文（必须在导入任何网络库之前）
ssl._create_default_https_context = ssl._create_unverified_context

# 更底层的方法：拦截 SSLContext 的创建
_original_create_default_context = ssl.create_default_context
def _patched_create_default_context(*args, **kwargs):
    ctx = _original_create_default_context(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
ssl.create_default_context = _patched_create_default_context

# 拦截 SSLContext 的 wrap_socket 方法，确保所有 SSL 连接都不验证证书
_original_wrap_socket = ssl.SSLContext.wrap_socket
def _patched_wrap_socket(self, sock, server_side=False, do_handshake_on_connect=True,
                        suppress_ragged_eofs=True, server_hostname=None, session=None):
    # 确保不验证证书
    self.check_hostname = False
    self.verify_mode = ssl.CERT_NONE
    return _original_wrap_socket(
        self, sock, server_side=server_side,
        do_handshake_on_connect=do_handshake_on_connect,
        suppress_ragged_eofs=suppress_ragged_eofs,
        server_hostname=server_hostname, session=session
    )
ssl.SSLContext.wrap_socket = _patched_wrap_socket

# 禁用 SSL 警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 尝试配置 requests（如果存在）
try:
    import requests
    requests.packages.urllib3.disable_warnings()
except (ImportError, AttributeError):
    pass

# 尝试配置 httpx（如果存在）
try:
    import httpx
    # 拦截 httpx 的 Client 和 AsyncClient 初始化
    _original_httpx_client_init = httpx.Client.__init__
    def _patched_httpx_client_init(self, *args, verify=False, **kwargs):
        return _original_httpx_client_init(self, *args, verify=False, **kwargs)
    httpx.Client.__init__ = _patched_httpx_client_init
    
    _original_httpx_async_client_init = httpx.AsyncClient.__init__
    def _patched_httpx_async_client_init(self, *args, verify=False, **kwargs):
        return _original_httpx_async_client_init(self, *args, verify=False, **kwargs)
    httpx.AsyncClient.__init__ = _patched_httpx_async_client_init
except (ImportError, AttributeError):
    pass

# 导入 E2B SDK 和其他依赖
from e2b import Sandbox

# 导入彩色日志
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import get_logger

logger = get_logger(__name__)
import subprocess

# 检查必需的环境变量
required_env_vars = ['E2B_DOMAIN', 'E2B_API_KEY']
missing_vars = [var for var in required_env_vars if var not in os.environ]
if missing_vars:
    logger.error(f"错误: 缺少必需的环境变量: {', '.join(missing_vars)}")
    logger.info("请先运行: source .e2b_env")
    sys.exit(1)

# 设置默认值（如果未设置）
os.environ.setdefault('E2B_ORCHESTRATOR_JOB', 'orchestrator')


def restart_nomad_orchestrator(job_name: str, wait_time: int = 30) -> bool:
    """
    重启 Nomad orchestrator job 以确保真正的冷启动

    Args:
        job_name: Nomad job 名称
        wait_time: 重启后等待时间（秒）

    Returns:
        是否成功重启
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"重启 Nomad Orchestrator: {job_name}")
    logger.info(f"{'='*60}")

    nomad_addr = os.getenv('NOMAD_ADDR')
    nomad_token = os.getenv('NOMAD_TOKEN')

    logger.info(f"Nomad 地址: {nomad_addr}")
    logger.info(f"Job 名称: {job_name}")

    try:
        # 构建 nomad 命令
        nomad_cmd = ['nomad', 'job', 'restart']

        # 添加 -address 参数
        if nomad_addr:
            nomad_cmd.extend(['-address', nomad_addr])

        # 添加 -token 参数
        if nomad_token:
            nomad_cmd.extend(['-token', nomad_token])

        # 添加自动确认参数（非交互式）
        nomad_cmd.append('-yes')
        nomad_cmd.append('-on-error=fail')

        # 添加 job 名称
        nomad_cmd.append(job_name)

        logger.info(f"\n执行命令: {' '.join(nomad_cmd[:3])} ... {job_name}")
        logger.info("重启中...")

        # 执行重启命令
        result = subprocess.run(
            nomad_cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0:
            logger.info("✓ 成功")
            logger.info(f"\n等待 orchestrator 就绪 ({wait_time} 秒)...")

            # 显示进度条
            for i in range(wait_time):
                time.sleep(1)
                progress = int((i + 1) / wait_time * 50)
                bar = '█' * progress + '░' * (50 - progress)
                logger.info(f"\r  [{bar}] {i+1}/{wait_time}s")

            logger.info("\n✓ Orchestrator 已就绪")
            logger.info(f"{'='*60}\n")
            return True
        else:
            logger.error("✗ 失败")
            logger.error(f"\n错误信息:")
            logger.info(result.stderr)
            return False

    except subprocess.TimeoutExpired:
        logger.error("✗ 超时")
        logger.info("\n重启命令执行超时 (60秒)")
        return False

    except FileNotFoundError:
        logger.error("✗ 失败")
        logger.error("\n错误: 未找到 'nomad' 命令")
        logger.info("请确保 Nomad CLI 已安装并在 PATH 中")
        return False

    except Exception as e:
        logger.error("✗ 失败")
        logger.info(f"\n异常: {e}")
        return False


def test_cold_start_latency(iterations: int = 10, template: str = None) -> Dict:
    """
    测试冷启动延迟

    注意: 冷启动测试会在每次测试前重启 orchestrator，确保真正的冷启动。
    Orchestrator job 名称从环境变量 E2B_ORCHESTRATOR_JOB 获取（默认: orchestrator）

    Args:
        iterations: 测试次数
        template: 模板ID(可选)

    Returns:
        包含统计数据的字典
    """
    # 获取 orchestrator job 名称
    orchestrator_job = os.getenv('E2B_ORCHESTRATOR_JOB', 'orchestrator')

    logger.info(f"开始测试冷启动延迟 (迭代{iterations}次)...")
    logger.info(f"💡 每次测试前重启 orchestrator: {orchestrator_job}")
    logger.warning(f"⚠️  预计耗时: 约 {int((30 + 10) * iterations / 60)} 分钟\n")

    cold_start_latencies = []

    for i in range(iterations):
        # 每次测试前都重启 orchestrator（真冷启动）
        logger.info(f"\n{'─'*60}")
        logger.info(f"第 {i+1}/{iterations} 次真冷启动测试")
        logger.info(f"{'─'*60}")
        success = restart_nomad_orchestrator(orchestrator_job, wait_time=30)
        if not success:
            logger.error(f"⚠️  重启失败，跳过第 {i+1} 次测试\n")
            continue

        logger.info(f"  测试 {i+1}/{iterations}...")

        start_time = time.time()

        try:
            # 创建沙箱（不指定模板使用默认）
            if template:
                sandbox = Sandbox(template)
            else:
                sandbox = Sandbox()

            # Sandbox 创建成功即表示就绪
            # （不执行额外命令，避免 streaming response 问题）

            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            cold_start_latencies.append(latency_ms)
            logger.info(f"{latency_ms:.2f} ms [真冷启动 #{i+1}]")

            # 关闭沙箱
            sandbox.kill()

        except Exception as e:
            logger.error(f"失败: {e}")
            continue
    
    # 计算统计数据
    if not cold_start_latencies:
        return {"error": "所有测试都失败"}

    cold_start_latencies.sort()
    n = len(cold_start_latencies)

    stats = {
        "raw_data": cold_start_latencies,
        "count": n,
        "min": min(cold_start_latencies),
        "max": max(cold_start_latencies),
        "mean": statistics.mean(cold_start_latencies),
        "median": statistics.median(cold_start_latencies),
        "stdev": statistics.stdev(cold_start_latencies) if n > 1 else 0,
        "p50": cold_start_latencies[int(n * 0.50)],
        "p95": cold_start_latencies[int(n * 0.95)],
        "p99": cold_start_latencies[int(n * 0.99)] if n >= 100 else cold_start_latencies[-1],
    }

    stats["note"] = "真冷启动（每次重启 orchestrator）"
    logger.info(f"\n🥶 真冷启动统计（{n} 次，每次重启 orchestrator）:")

    logger.info(f"  最小值: {stats['min']:.2f} ms")
    logger.info(f"  最大值: {stats['max']:.2f} ms")
    logger.info(f"  平均值: {stats['mean']:.2f} ms ⭐")
    logger.info(f"  中位数: {stats['median']:.2f} ms")
    logger.info(f"  P50: {stats['p50']:.2f} ms")
    logger.info(f"  P95: {stats['p95']:.2f} ms")
    logger.info(f"  P99: {stats['p99']:.2f} ms")
    logger.info(f"  标准差: {stats['stdev']:.2f} ms")

    return stats


def test_warm_start_latency(iterations: int = 10, template: str = None) -> Dict:
    """
    测试热启动延迟（节点缓存 + 进程池复用）

    预热策略: 先创建并关闭一个沙箱，让系统缓存模板和预热进程池。
    与冷启动的区别：
    - 冷启动: 第1次测试（拉取模板）vs 第2+次（使用缓存）
    - 热启动: 预热后连续测试（模板缓存 + 进程池热）

    Args:
        iterations: 测试次数
        template: 模板ID(可选)

    Returns:
        包含统计数据的字典
    """
    logger.info(f"开始测试热启动延迟 (迭代{iterations}次)...")
    logger.info("💡 热启动 = 模板已缓存 + 进程池已预热\n")
    
    # 预热: 创建并关闭一个沙箱
    logger.info("  预热中...")
    try:
        if template:
            warmup_sandbox = Sandbox(template)
        else:
            warmup_sandbox = Sandbox()
        warmup_sandbox.kill()
        time.sleep(2)
        logger.info("  预热完成")
    except Exception as e:
        logger.error(f"  预热失败: {e}")
    
    latencies = []
    
    for i in range(iterations):
        logger.info(f"  测试 {i+1}/{iterations}...")
        
        start_time = time.time()
        
        try:
            # 创建沙箱（不指定模板使用默认）
            if template:
                sandbox = Sandbox(template)
            else:
                sandbox = Sandbox()

            # Sandbox 创建成功即表示就绪
            # （不执行额外命令，避免 streaming response 问题）
            
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
            
            logger.info(f"{latency_ms:.2f} ms")
            
            # 关闭沙箱
            sandbox.kill()
            
        except Exception as e:
            logger.error(f"失败: {e}")
            continue
        
        # 短暂等待
        time.sleep(0.5)
    
    # 计算统计数据
    if not latencies:
        return {"error": "所有测试都失败"}
    
    latencies.sort()
    n = len(latencies)
    
    stats = {
        "raw_data": latencies,
        "count": n,
        "min": min(latencies),
        "max": max(latencies),
        "mean": statistics.mean(latencies),
        "median": statistics.median(latencies),
        "stdev": statistics.stdev(latencies) if n > 1 else 0,
        "p50": latencies[int(n * 0.50)],
        "p95": latencies[int(n * 0.95)],
        "p99": latencies[int(n * 0.99)] if n >= 100 else latencies[-1],
    }
    
    logger.info("\n统计结果:")
    logger.info(f"  P50: {stats['p50']:.2f} ms ⭐")
    logger.info(f"  P95: {stats['p95']:.2f} ms")
    logger.info(f"  P99: {stats['p99']:.2f} ms")
    
    return stats



def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="E2B沙箱生命周期测试")
    parser.add_argument("--test", choices=["cold", "warm", "all"],
                       default="all", help="测试类型")
    parser.add_argument("--iterations", type=int, default=10, help="测试迭代次数")
    parser.add_argument("--template", type=str, help="模板ID")
    parser.add_argument("--output", type=str, help="输出JSON文件路径")
    
    args = parser.parse_args()
    
    results = {}
    
    # 冷启动测试（每次重启 orchestrator）
    if args.test in ["cold", "all"]:
        results["cold_start"] = test_cold_start_latency(args.iterations, args.template)
        logger.info("\n" + "="*60 + "\n")
    
    # 热启动测试
    if args.test in ["warm", "all"]:
        results["warm_start"] = test_warm_start_latency(args.iterations, args.template)
        logger.info("\n" + "="*60 + "\n")

    # 保存结果
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"结果已保存到: {args.output}")
    
    return results


if __name__ == "__main__":
    main()
