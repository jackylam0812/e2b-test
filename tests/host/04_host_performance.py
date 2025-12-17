#!/usr/bin/env python3
"""
宿主机性能测试脚本

测试指标（完整版）:
1. CPU性能（单核/多核、架构信息）
2. 内存性能（读写带宽、随机访问）
3. 磁盘I/O性能（随机读写IOPS、顺序读写吞吐量、延迟分布）
4. 网络性能（公网延迟、下载/上传带宽）
5. 大页内存配置检查

测试参数:
--test cpu       : 仅测试CPU性能
--test memory    : 仅测试内存性能
--test disk      : 仅测试磁盘I/O性能
--test network   : 仅测试网络性能
--test hugepages : 仅检查大页内存配置
--test all       : 运行所有测试
--output <file>  : 将结果保存为JSON文件

这些测试直接在宿主机上运行（不在沙箱内）
"""

import os
import sys
import time
import json
import statistics
import subprocess
from typing import Dict

# 导入彩色日志
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import get_logger

logger = get_logger(__name__)


def test_host_cpu_performance() -> Dict:
    """测试宿主机CPU性能"""
    logger.info("开始测试宿主机CPU性能...")

    results = {}

    try:
        # 检查是否安装 sysbench
        check = subprocess.run(["which", "sysbench"], capture_output=True)
        if check.returncode != 0:
            logger.warning("  ⚠️  sysbench 未安装，跳过CPU测试")
            logger.info("     安装: apt-get install sysbench")
            return {"skipped": "sysbench not installed"}

        # 单线程测试
        logger.info("  单线程测试（10秒）...")
        result = subprocess.run(
            ["sysbench", "cpu", "--threads=1", "--time=10", "run"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'events per second' in line:
                    score = float(line.split()[-1])
                    results["single_thread_events_per_sec"] = score
                    logger.info(f"✓ {score:.2f} events/s")
                    break

        # 多线程测试（所有核心）
        import multiprocessing
        threads = multiprocessing.cpu_count()
        logger.info(f"  多线程测试（{threads}线程，10秒）...")
        result = subprocess.run(
            ["sysbench", "cpu", f"--threads={threads}", "--time=10", "run"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'events per second' in line:
                    score = float(line.split()[-1])
                    results["multi_thread_events_per_sec"] = score
                    results["cpu_threads"] = threads
                    logger.info(f"✓ {score:.2f} events/s")
                    break

        # CPU 信息
        cpu_info = subprocess.run(
            ["lscpu"], capture_output=True, text=True
        )
        if cpu_info.returncode == 0:
            results["cpu_info"] = cpu_info.stdout

    except Exception as e:
        logger.error(f"  ✗ CPU测试失败: {e}")
        results["error"] = str(e)

    return results


def test_host_disk_io() -> Dict:
    """测试宿主机磁盘I/O性能"""
    logger.info("\n开始测试宿主机磁盘I/O性能...")

    results = {}

    try:
        # 检查 fio
        check = subprocess.run(["which", "fio"], capture_output=True)
        if check.returncode != 0:
            logger.warning("  ⚠️  fio 未安装，跳过磁盘测试")
            logger.info("     安装: apt-get install fio")
            return {"skipped": "fio not installed"}

        test_file = "/tmp/fio_test"

        # 随机读 IOPS (不同队列深度)
        results["random_read_iops_by_qd"] = {}
        for qd in [1, 4, 16, 32]:
            logger.info(f"  随机读 IOPS 测试 (QD={qd}, 10秒)...")
            result = subprocess.run([
                "fio", "--name=randread", "--ioengine=libaio", f"--iodepth={qd}",
                "--rw=randread", "--bs=4k", "--direct=1", "--size=500M",
                "--numjobs=1", "--runtime=10", "--time_based",
                "--group_reporting", "--output-format=json", f"--filename={test_file}"
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                iops = data["jobs"][0]["read"]["iops"]
                results["random_read_iops_by_qd"][f"qd_{qd}"] = iops
                if qd == 1:
                    results["random_read_iops"] = iops  # 默认记录 QD=1
                logger.info(f"✓ {iops:.2f} IOPS")
            else:
                logger.error(f"✗ 失败")

        # 随机写 IOPS
        logger.info("  随机写 IOPS 测试（QD=1, 10秒）...")
        result = subprocess.run([
            "fio", "--name=randwrite", "--ioengine=libaio", "--iodepth=1",
            "--rw=randwrite", "--bs=4k", "--direct=1", "--size=500M",
            "--numjobs=1", "--runtime=10", "--time_based",
            "--group_reporting", "--output-format=json", f"--filename={test_file}"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            data = json.loads(result.stdout)
            iops = data["jobs"][0]["write"]["iops"]
            results["random_write_iops"] = iops
            logger.info(f"✓ {iops:.2f} IOPS")
        else:
            logger.error(f"✗ 失败")

        # 顺序读吞吐量
        logger.info("  顺序读吞吐量测试（10秒）...")
        result = subprocess.run([
            "fio", "--name=seqread", "--ioengine=libaio", "--iodepth=16",
            "--rw=read", "--bs=1m", "--direct=1", "--size=1G",
            "--numjobs=1", "--runtime=10", "--time_based",
            "--group_reporting", "--output-format=json", f"--filename={test_file}"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            data = json.loads(result.stdout)
            throughput_kb = data["jobs"][0]["read"]["bw"]
            throughput_mb = throughput_kb / 1024
            results["sequential_read_throughput_mbs"] = throughput_mb
            logger.info(f"✓ {throughput_mb:.2f} MB/s")
        else:
            logger.error(f"✗ 失败")

        # 顺序写吞吐量
        logger.info("  顺序写吞吐量测试（10秒）...")
        result = subprocess.run([
            "fio", "--name=seqwrite", "--ioengine=libaio", "--iodepth=16",
            "--rw=write", "--bs=1m", "--direct=1", "--size=1G",
            "--numjobs=1", "--runtime=10", "--time_based",
            "--group_reporting", "--output-format=json", f"--filename={test_file}"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            data = json.loads(result.stdout)
            throughput_kb = data["jobs"][0]["write"]["bw"]
            throughput_mb = throughput_kb / 1024
            results["sequential_write_throughput_mbs"] = throughput_mb
            logger.info(f"✓ {throughput_mb:.2f} MB/s")
        else:
            logger.error(f"✗ 失败")

        # 磁盘延迟测试 (读)
        logger.info("  磁盘读延迟测试（10秒）...")
        result = subprocess.run([
            "fio", "--name=latency_read", "--ioengine=libaio", "--iodepth=1",
            "--rw=randread", "--bs=4k", "--direct=1", "--size=500M",
            "--numjobs=1", "--runtime=10", "--time_based",
            "--group_reporting", "--output-format=json", f"--filename={test_file}"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                job = data["jobs"][0]["read"]

                # 尝试从不同的延迟字段获取数据
                if "lat_ns" in job and "percentile" in job["lat_ns"]:
                    # 新版本 fio
                    lat_ns = job["lat_ns"]
                    results["read_latency_us"] = {
                        "mean": lat_ns["mean"] / 1000,
                        "p50": lat_ns["percentile"]["50.000000"] / 1000,
                        "p95": lat_ns["percentile"]["95.000000"] / 1000,
                        "p99": lat_ns["percentile"]["99.000000"] / 1000,
                    }
                elif "clat_ns" in job and "percentile" in job["clat_ns"]:
                    # 使用 clat (完成延迟)
                    lat_ns = job["clat_ns"]
                    results["read_latency_us"] = {
                        "mean": lat_ns["mean"] / 1000,
                        "p50": lat_ns["percentile"]["50.000000"] / 1000,
                        "p95": lat_ns["percentile"]["95.000000"] / 1000,
                        "p99": lat_ns["percentile"]["99.000000"] / 1000,
                    }
                else:
                    # 回退到简单的平均延迟
                    if "lat_ns" in job and "mean" in job["lat_ns"]:
                        results["read_latency_us"] = {"mean": job["lat_ns"]["mean"] / 1000}
                    elif "clat_ns" in job and "mean" in job["clat_ns"]:
                        results["read_latency_us"] = {"mean": job["clat_ns"]["mean"] / 1000}

                if "p50" in results.get("read_latency_us", {}):
                    logger.info(f"✓ P50/P95/P99: {results['read_latency_us']['p50']:.2f} / {results['read_latency_us']['p95']:.2f} / {results['read_latency_us']['p99']:.2f} μs")
                elif "mean" in results.get("read_latency_us", {}):
                    logger.info(f"✓ Mean: {results['read_latency_us']['mean']:.2f} μs")
                else:
                    logger.error(f"✗ 无法解析延迟数据")
            except (KeyError, json.JSONDecodeError) as e:
                logger.error(f"✗ 解析失败: {e}")
        else:
            logger.error(f"✗ 失败")

        # 磁盘延迟测试 (写)
        logger.info("  磁盘写延迟测试（10秒）...")
        result = subprocess.run([
            "fio", "--name=latency_write", "--ioengine=libaio", "--iodepth=1",
            "--rw=randwrite", "--bs=4k", "--direct=1", "--size=500M",
            "--numjobs=1", "--runtime=10", "--time_based",
            "--group_reporting", "--output-format=json", f"--filename={test_file}"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                job = data["jobs"][0]["write"]

                # 尝试从不同的延迟字段获取数据
                if "lat_ns" in job and "percentile" in job["lat_ns"]:
                    lat_ns = job["lat_ns"]
                    results["write_latency_us"] = {
                        "mean": lat_ns["mean"] / 1000,
                        "p50": lat_ns["percentile"]["50.000000"] / 1000,
                        "p95": lat_ns["percentile"]["95.000000"] / 1000,
                        "p99": lat_ns["percentile"]["99.000000"] / 1000,
                    }
                elif "clat_ns" in job and "percentile" in job["clat_ns"]:
                    lat_ns = job["clat_ns"]
                    results["write_latency_us"] = {
                        "mean": lat_ns["mean"] / 1000,
                        "p50": lat_ns["percentile"]["50.000000"] / 1000,
                        "p95": lat_ns["percentile"]["95.000000"] / 1000,
                        "p99": lat_ns["percentile"]["99.000000"] / 1000,
                    }
                else:
                    # 回退到简单的平均延迟
                    if "lat_ns" in job and "mean" in job["lat_ns"]:
                        results["write_latency_us"] = {"mean": job["lat_ns"]["mean"] / 1000}
                    elif "clat_ns" in job and "mean" in job["clat_ns"]:
                        results["write_latency_us"] = {"mean": job["clat_ns"]["mean"] / 1000}

                if "p50" in results.get("write_latency_us", {}):
                    logger.info(f"✓ P50/P95/P99: {results['write_latency_us']['p50']:.2f} / {results['write_latency_us']['p95']:.2f} / {results['write_latency_us']['p99']:.2f} μs")
                elif "mean" in results.get("write_latency_us", {}):
                    logger.info(f"✓ Mean: {results['write_latency_us']['mean']:.2f} μs")
                else:
                    logger.error(f"✗ 无法解析延迟数据")
            except (KeyError, json.JSONDecodeError) as e:
                logger.error(f"✗ 解析失败: {e}")
        else:
            logger.error(f"✗ 失败")

        # 清理测试文件
        subprocess.run(["rm", "-f", test_file], capture_output=True)

    except Exception as e:
        logger.error(f"  ✗ 磁盘测试失败: {e}")
        results["error"] = str(e)

    return results


def test_host_memory_performance() -> Dict:
    """测试宿主机内存性能"""
    logger.info("\n开始测试宿主机内存性能...")

    results = {}

    try:
        # 检查是否安装 sysbench
        check = subprocess.run(["which", "sysbench"], capture_output=True)
        if check.returncode != 0:
            logger.warning("  ⚠️  sysbench 未安装，跳过内存测试")
            logger.info("     安装: apt-get install sysbench")
            return {"skipped": "sysbench not installed"}

        # 内存写带宽测试
        logger.info("  内存写带宽测试（10秒）...")
        result = subprocess.run([
            "sysbench", "memory", "--memory-block-size=1M",
            "--memory-total-size=10G", "--memory-oper=write",
            "--time=10", "run"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'transferred' in line and 'MiB/sec' in line:
                    # 解析类似: "10240.00 MiB transferred (1024.00 MiB/sec)"
                    bandwidth = float(line.split('(')[1].split()[0])
                    results["write_bandwidth_mbs"] = bandwidth
                    logger.info(f"✓ {bandwidth:.2f} MiB/s")
                    break
        else:
            logger.error(f"✗ 失败")

        # 内存读带宽测试
        logger.info("  内存读带宽测试（10秒）...")
        result = subprocess.run([
            "sysbench", "memory", "--memory-block-size=1M",
            "--memory-total-size=10G", "--memory-oper=read",
            "--time=10", "run"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'transferred' in line and 'MiB/sec' in line:
                    bandwidth = float(line.split('(')[1].split()[0])
                    results["read_bandwidth_mbs"] = bandwidth
                    logger.info(f"✓ {bandwidth:.2f} MiB/s")
                    break
        else:
            logger.error(f"✗ 失败")

        # 随机内存访问测试
        logger.info("  随机内存访问测试（10秒）...")
        result = subprocess.run([
            "sysbench", "memory", "--memory-block-size=1K",
            "--memory-total-size=1G", "--memory-access-mode=rnd",
            "--time=10", "run"
        ], capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'total number of events' in line:
                    events = int(line.split(':')[1].strip())
                    ops_per_sec = events / 10  # 10秒测试
                    results["random_access_ops_per_sec"] = ops_per_sec
                    logger.info(f"✓ {ops_per_sec:.2f} ops/s")
                    break
        else:
            logger.error(f"✗ 失败")

    except Exception as e:
        logger.error(f"  ✗ 内存测试失败: {e}")
        results["error"] = str(e)

    return results


def test_host_network_performance() -> Dict:
    """测试宿主机网络性能"""
    logger.info("\n开始测试宿主机网络性能...")

    results = {}

    try:
        # 测试到公网的延迟
        logger.info("  公网延迟测试 (ping 8.8.8.8)...")
        result = subprocess.run(
            ["ping", "-c", "20", "8.8.8.8"],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0:
            for line in result.stdout.split('\n'):
                if 'rtt min/avg/max' in line or 'min/avg/max' in line:
                    # 解析: rtt min/avg/max/mdev = 1.234/2.345/3.456/0.123 ms
                    stats = line.split('=')[1].strip().split()[0]
                    min_rtt, avg_rtt, max_rtt, mdev = map(float, stats.split('/'))
                    results["internet_latency_ms"] = {
                        "min": min_rtt,
                        "avg": avg_rtt,
                        "max": max_rtt,
                        "mdev": mdev
                    }
                    logger.info(f"✓ 平均 {avg_rtt:.3f} ms")
                    break
        else:
            logger.error(f"✗ 失败")

        # 测试下载带宽 (从公网下载测试文件)
        logger.info("  公网下载带宽测试 (10MB文件)...")
        test_url = "https://speed.cloudflare.com/10mb.bin"
        start_time = time.time()
        result = subprocess.run(
            ["curl", "-o", "/dev/null", "-s", "-w", "%{speed_download}", test_url],
            capture_output=True, text=True, timeout=30
        )
        elapsed = time.time() - start_time

        if result.returncode == 0 and result.stdout:
            speed_bytes = float(result.stdout)  # bytes/sec
            speed_mbs = speed_bytes / (1024 * 1024)  # MB/s
            results["download_bandwidth_mbs"] = speed_mbs
            logger.info(f"✓ {speed_mbs:.2f} MB/s")
        else:
            logger.error(f"✗ 失败")

        # 测试上传带宽 (上传到测试服务)
        logger.info("  公网上传带宽测试 (5MB文件)...")
        # 创建测试文件
        subprocess.run(["dd", "if=/dev/zero", "of=/tmp/upload_test", "bs=1M", "count=5"],
                      capture_output=True, timeout=10)

        result = subprocess.run(
            ["curl", "-T", "/tmp/upload_test", "-o", "/dev/null", "-s", "-w", "%{speed_upload}",
             "https://transfer.sh/upload_test"],
            capture_output=True, text=True, timeout=30
        )

        if result.returncode == 0 and result.stdout:
            speed_bytes = float(result.stdout)  # bytes/sec
            speed_mbs = speed_bytes / (1024 * 1024)  # MB/s
            results["upload_bandwidth_mbs"] = speed_mbs
            logger.info(f"✓ {speed_mbs:.2f} MB/s")
        else:
            logger.error(f"✗ 失败")

        # 清理测试文件
        subprocess.run(["rm", "-f", "/tmp/upload_test"], capture_output=True)

    except Exception as e:
        logger.error(f"  ✗ 网络测试失败: {e}")
        results["error"] = str(e)

    return results


def test_host_huge_pages() -> Dict:
    """检查大页内存配置"""
    logger.info("\n检查宿主机大页内存配置...")

    results = {}

    try:
        # 读取大页信息
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()

        for line in meminfo.split('\n'):
            if 'HugePages_Total' in line:
                results["huge_pages_total"] = int(line.split()[1])
            elif 'HugePages_Free' in line:
                results["huge_pages_free"] = int(line.split()[1])
            elif 'Hugepagesize' in line:
                results["huge_page_size_kb"] = int(line.split()[1])

        if results.get("huge_pages_total", 0) > 0:
            results["huge_pages_enabled"] = True
            total_gb = (results["huge_pages_total"] * results["huge_page_size_kb"]) / (1024 * 1024)
            results["huge_pages_total_gb"] = total_gb
            logger.info(f"  ✓ 大页内存已启用")
            logger.info(f"    大小: {results['huge_page_size_kb']} KB")
            logger.info(f"    总量: {results['huge_pages_total']} 页 ({total_gb:.2f} GB)")
            logger.info(f"    可用: {results['huge_pages_free']} 页")
        else:
            results["huge_pages_enabled"] = False
            logger.error(f"  ✗ 大页内存未启用")

    except Exception as e:
        logger.error(f"  ✗ 检查失败: {e}")
        results["error"] = str(e)

    return results


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="宿主机性能测试")
    parser.add_argument("--test", choices=["cpu", "memory", "disk", "network", "hugepages", "all"],
                       required=True, help="测试类型")
    parser.add_argument("--output", type=str, help="输出JSON文件路径")

    args = parser.parse_args()

    logger.info(f"\n{'='*60}")
    logger.info("宿主机性能测试")
    logger.info(f"{'='*60}\n")

    results = {}

    if args.test == "cpu" or args.test == "all":
        results["cpu"] = test_host_cpu_performance()

    if args.test == "memory" or args.test == "all":
        results["memory"] = test_host_memory_performance()

    if args.test == "disk" or args.test == "all":
        results["disk_io"] = test_host_disk_io()

    if args.test == "network" or args.test == "all":
        results["network"] = test_host_network_performance()

    if args.test == "hugepages" or args.test == "all":
        results["huge_pages"] = test_host_huge_pages()

    # 保存结果
    if args.output and results:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        logger.info(f"\n✓ 结果已保存到: {args.output}\n")

    return results


if __name__ == "__main__":
    main()
