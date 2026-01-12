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
--test cpu           : 仅测试CPU性能
--test memory        : 仅测试内存性能
--test disk          : 仅测试磁盘I/O性能（基础测试）
--test disk-full     : 完整磁盘I/O测试（包含延迟、高QD等）
--test nbd-workload  : NBD工作负载模拟测试
--test network       : 仅测试网络性能
--test hugepages     : 仅检查大页内存配置
--test all           : 运行所有测试
--output <file>      : 将结果保存为JSON文件
--test-dir <path>    : 测试目录（默认: /tmp）
--num-sandboxes <n>  : NBD模拟的沙箱数量（默认: 38）

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


def test_host_disk_io(test_dir: str = "/tmp", full_test: bool = False) -> Dict:
    """测试宿主机磁盘I/O性能

    Args:
        test_dir: 测试目录路径
        full_test: 是否运行完整测试（包含更多测试场景）
    """
    logger.info("\n开始测试宿主机磁盘I/O性能...")
    if full_test:
        logger.info("  运行完整测试模式")

    results = {}

    try:
        # 检查 fio
        check = subprocess.run(["which", "fio"], capture_output=True)
        if check.returncode != 0:
            logger.warning("  ⚠️  fio 未安装，跳过磁盘测试")
            logger.info("     安装: apt-get install fio")
            return {"skipped": "fio not installed"}

        # 确保测试目录存在
        import os
        os.makedirs(test_dir, exist_ok=True)

        test_file = os.path.join(test_dir, "fio_test")

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

        # 完整测试模式：添加更多测试场景
        if full_test:
            # 混合随机读写测试 (70% 读, 30% 写)
            logger.info("  混合随机读写测试（70/30, 10秒）...")
            result = subprocess.run([
                "fio", "--name=mixed-rw", "--ioengine=libaio", "--iodepth=16",
                "--rw=randrw", "--rwmixread=70", "--bs=4k", "--direct=1", "--size=500M",
                "--numjobs=1", "--runtime=10", "--time_based",
                "--group_reporting", "--output-format=json", f"--filename={test_file}"
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                results["mixed_rw"] = {
                    "read_iops": data["jobs"][0]["read"]["iops"],
                    "write_iops": data["jobs"][0]["write"]["iops"],
                    "total_iops": data["jobs"][0]["read"]["iops"] + data["jobs"][0]["write"]["iops"]
                }
                logger.info(f"✓ 读: {results['mixed_rw']['read_iops']:.2f} IOPS, "
                          f"写: {results['mixed_rw']['write_iops']:.2f} IOPS")
            else:
                logger.error(f"✗ 失败")

            # 高队列深度测试 (QD=256)
            logger.info("  高队列深度测试（QD=256, 10秒）...")
            result = subprocess.run([
                "fio", "--name=high-qd", "--ioengine=libaio", "--iodepth=256",
                "--rw=randwrite", "--bs=4k", "--direct=1", "--size=500M",
                "--numjobs=1", "--runtime=10", "--time_based",
                "--group_reporting", "--output-format=json", f"--filename={test_file}"
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                results["high_qd_iops"] = data["jobs"][0]["write"]["iops"]
                logger.info(f"✓ {results['high_qd_iops']:.2f} IOPS")
            else:
                logger.error(f"✗ 失败")

            # fsync 性能测试
            logger.info("  fsync 性能测试（10秒）...")
            result = subprocess.run([
                "fio", "--name=fsync-test", "--ioengine=sync", "--direct=0",
                "--bs=4k", "--rw=write", "--fsync=1", "--size=100M",
                "--numjobs=1", "--runtime=10", "--time_based",
                "--group_reporting", "--output-format=json", f"--filename={test_file}"
            ], capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                data = json.loads(result.stdout)
                results["fsync_iops"] = data["jobs"][0]["write"]["iops"]
                logger.info(f"✓ {results['fsync_iops']:.2f} IOPS")
            else:
                logger.error(f"✗ 失败")

        # 清理测试文件
        subprocess.run(["rm", "-f", test_file], capture_output=True)

    except Exception as e:
        logger.error(f"  ✗ 磁盘测试失败: {e}")
        results["error"] = str(e)

    return results


def test_nbd_workload(test_dir: str = "/tmp", num_sandboxes: int = 38, duration: int = 60) -> Dict:
    """NBD 工作负载模拟测试

    模拟多个沙箱并发运行时的 I/O 模式

    Args:
        test_dir: 测试目录路径
        num_sandboxes: 模拟的沙箱数量
        duration: 测试运行时长（秒）
    """
    logger.info("\n开始 NBD 工作负载模拟测试...")
    logger.info(f"  测试目录: {test_dir}")
    logger.info(f"  模拟沙箱数: {num_sandboxes}")
    logger.info(f"  运行时长: {duration}秒")

    results = {
        "test_dir": test_dir,
        "num_sandboxes": num_sandboxes,
        "duration": duration
    }

    try:
        # 检查 fio
        check = subprocess.run(["which", "fio"], capture_output=True)
        if check.returncode != 0:
            logger.warning("  ⚠️  fio 未安装，跳过 NBD 工作负载测试")
            logger.info("     安装: apt-get install fio")
            return {"skipped": "fio not installed"}

        # 确保测试目录存在
        import os
        workload_dir = os.path.join(test_dir, "nbd_workload_test")
        os.makedirs(workload_dir, exist_ok=True)

        # 1. 元数据操作测试（4K 随机写）
        logger.info("  [1/4] 元数据操作测试（4K 随机写）...")
        test_file = os.path.join(workload_dir, "metadata_test")
        result = subprocess.run([
            "fio", "--name=metadata_ops", "--ioengine=libaio", "--iodepth=4",
            "--rw=randwrite", "--bs=4k", "--direct=1", "--size=100M",
            f"--numjobs={num_sandboxes}", f"--runtime={duration}", "--time_based",
            "--group_reporting", "--output-format=json", f"--filename={test_file}"
        ], capture_output=True, text=True, timeout=duration + 30)

        if result.returncode == 0:
            data = json.loads(result.stdout)
            job = data["jobs"][0]["write"]
            total_iops = job["iops"]
            avg_latency_us = job.get("lat_ns", {}).get("mean", 0) / 1000 if "lat_ns" in job else 0

            results["metadata_ops"] = {
                "total_iops": total_iops,
                "per_sandbox_iops": total_iops / num_sandboxes,
                "avg_latency_us": avg_latency_us
            }
            logger.info(f"✓ 总 IOPS: {total_iops:.2f}, 每沙箱: {total_iops/num_sandboxes:.2f}")
        else:
            logger.error(f"✗ 失败")
            results["metadata_ops"] = {"error": "test failed"}

        # 2. 代码执行测试（64K 随机读）
        logger.info("  [2/4] 代码执行测试（64K 随机读）...")
        test_file = os.path.join(workload_dir, "code_exec_test")
        result = subprocess.run([
            "fio", "--name=code_execution", "--ioengine=libaio", "--iodepth=8",
            "--rw=randread", "--bs=64k", "--direct=1", "--size=500M",
            f"--numjobs={num_sandboxes}", f"--runtime={duration}", "--time_based",
            "--group_reporting", "--output-format=json", f"--filename={test_file}"
        ], capture_output=True, text=True, timeout=duration + 30)

        if result.returncode == 0:
            data = json.loads(result.stdout)
            job = data["jobs"][0]["read"]
            total_iops = job["iops"]
            bandwidth_mbs = job["bw"] / 1024

            results["code_execution"] = {
                "total_iops": total_iops,
                "per_sandbox_iops": total_iops / num_sandboxes,
                "bandwidth_mbs": bandwidth_mbs
            }
            logger.info(f"✓ 总 IOPS: {total_iops:.2f}, 带宽: {bandwidth_mbs:.2f} MB/s")
        else:
            logger.error(f"✗ 失败")
            results["code_execution"] = {"error": "test failed"}

        # 3. 日志写入测试（16K 顺序写）
        logger.info("  [3/4] 日志写入测试（16K 顺序写）...")
        test_file = os.path.join(workload_dir, "log_write_test")
        result = subprocess.run([
            "fio", "--name=log_writing", "--ioengine=libaio", "--iodepth=2",
            "--rw=write", "--bs=16k", "--direct=1", "--size=200M",
            f"--numjobs={num_sandboxes}", f"--runtime={duration}", "--time_based",
            "--group_reporting", "--output-format=json", f"--filename={test_file}"
        ], capture_output=True, text=True, timeout=duration + 30)

        if result.returncode == 0:
            data = json.loads(result.stdout)
            job = data["jobs"][0]["write"]
            total_iops = job["iops"]
            bandwidth_mbs = job["bw"] / 1024

            results["log_writing"] = {
                "total_iops": total_iops,
                "per_sandbox_iops": total_iops / num_sandboxes,
                "bandwidth_mbs": bandwidth_mbs
            }
            logger.info(f"✓ 总 IOPS: {total_iops:.2f}, 带宽: {bandwidth_mbs:.2f} MB/s")
        else:
            logger.error(f"✗ 失败")
            results["log_writing"] = {"error": "test failed"}

        # 4. 混合工作负载测试
        logger.info("  [4/4] 混合工作负载测试（60% 读）...")
        test_file = os.path.join(workload_dir, "mixed_test")
        result = subprocess.run([
            "fio", "--name=mixed_workload", "--ioengine=libaio", "--iodepth=16",
            "--rw=randrw", "--rwmixread=60", "--bs=4k-64k", "--direct=1", "--size=300M",
            f"--numjobs={num_sandboxes}", f"--runtime={duration}", "--time_based",
            "--group_reporting", "--output-format=json", f"--filename={test_file}"
        ], capture_output=True, text=True, timeout=duration + 30)

        if result.returncode == 0:
            data = json.loads(result.stdout)
            read_job = data["jobs"][0]["read"]
            write_job = data["jobs"][0]["write"]
            read_iops = read_job["iops"]
            write_iops = write_job["iops"]
            total_iops = read_iops + write_iops

            results["mixed_workload"] = {
                "read_iops": read_iops,
                "write_iops": write_iops,
                "total_iops": total_iops,
                "per_sandbox_read_iops": read_iops / num_sandboxes,
                "per_sandbox_write_iops": write_iops / num_sandboxes
            }
            logger.info(f"✓ 读: {read_iops:.2f}, 写: {write_iops:.2f}, 总: {total_iops:.2f} IOPS")
        else:
            logger.error(f"✗ 失败")
            results["mixed_workload"] = {"error": "test failed"}

        # 计算总 IOPS 需求
        if all(key in results and "error" not in results[key]
               for key in ["metadata_ops", "code_execution", "log_writing", "mixed_workload"]):
            estimated_total_iops = (
                results["metadata_ops"]["total_iops"] +
                results["code_execution"]["total_iops"] +
                results["log_writing"]["total_iops"] +
                results["mixed_workload"]["total_iops"]
            )
            results["estimated_total_iops"] = estimated_total_iops

            # 给出建议
            if estimated_total_iops > 10000:
                results["recommendation"] = "gp3 with 16,000 IOPS 或 io2"
            elif estimated_total_iops > 6000:
                results["recommendation"] = "gp3 with 10,000 IOPS"
            elif estimated_total_iops > 3000:
                results["recommendation"] = "gp3 with 6,000 IOPS 或 gp2 (2TB+)"
            else:
                results["recommendation"] = "gp3 (默认 3,000 IOPS)"

            logger.info(f"\n  估算总 IOPS 需求: {estimated_total_iops:.2f}")
            logger.info(f"  推荐配置: {results['recommendation']}")

        # 清理测试文件
        subprocess.run(["rm", "-rf", workload_dir], capture_output=True)

    except Exception as e:
        logger.error(f"  ✗ NBD 工作负载测试失败: {e}")
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

        # speedtest 公网带宽测试
        logger.info("  speedtest 公网带宽测试...")
        check = subprocess.run(["which", "speedtest"], capture_output=True)
        if check.returncode != 0:
            logger.warning("  ⚠️  speedtest 未安装")
            logger.info("     安装: curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash")
            logger.info("            sudo apt-get install speedtest")
            results["speedtest"] = {"skipped": "speedtest not installed"}
        else:
            result = subprocess.run(
                ["speedtest", "--format=json", "--accept-license", "--accept-gdpr"],
                capture_output=True, text=True, timeout=60
            )

            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    download_bps = data.get("download", {}).get("bandwidth", 0)
                    upload_bps = data.get("upload", {}).get("bandwidth", 0)

                    download_mbps = (download_bps * 8) / (1000 * 1000)  # bps to Mbps
                    upload_mbps = (upload_bps * 8) / (1000 * 1000)

                    results["speedtest"] = {
                        "download_mbps": download_mbps,
                        "upload_mbps": upload_mbps,
                        "server": data.get("server", {}).get("name", "unknown"),
                        "latency_ms": data.get("ping", {}).get("latency", 0)
                    }
                    logger.info(f"✓ 下载: {download_mbps:.2f} Mbps, 上传: {upload_mbps:.2f} Mbps")
                except (json.JSONDecodeError, KeyError) as e:
                    logger.error(f"✗ 解析失败: {e}")
                    results["speedtest"] = {"error": str(e)}
            else:
                logger.error(f"✗ 失败")
                results["speedtest"] = {"error": "speedtest command failed"}

        # iperf3 内网带宽测试
        logger.info("  iperf3 内网带宽测试...")
        check = subprocess.run(["which", "iperf3"], capture_output=True)
        if check.returncode != 0:
            logger.warning("  ⚠️  iperf3 未安装")
            logger.info("     安装: apt-get install iperf3")
            results["iperf3"] = {"skipped": "iperf3 not installed"}
        else:
            # 检查环境变量中是否有 iperf3 server 地址
            iperf_server = os.environ.get("IPERF3_SERVER")
            if not iperf_server:
                logger.warning("  ⚠️  未配置 iperf3 server")
                logger.info("     设置环境变量: export IPERF3_SERVER=<server_ip>")
                logger.info("     在另一台机器上运行: iperf3 -s")
                results["iperf3"] = {"skipped": "IPERF3_SERVER not configured"}
            else:
                logger.info(f"  测试到 {iperf_server} 的带宽...")
                result = subprocess.run(
                    ["iperf3", "-c", iperf_server, "-t", "10", "-J"],
                    capture_output=True, text=True, timeout=30
                )

                if result.returncode == 0:
                    try:
                        data = json.loads(result.stdout)
                        bits_per_second = data["end"]["sum_sent"]["bits_per_second"]
                        gbps = bits_per_second / (1000 * 1000 * 1000)

                        results["iperf3"] = {
                            "bandwidth_gbps": gbps,
                            "bandwidth_mbps": gbps * 1000,
                            "server": iperf_server
                        }
                        logger.info(f"✓ {gbps:.2f} Gbps")
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"✗ 解析失败: {e}")
                        results["iperf3"] = {"error": str(e)}
                else:
                    logger.error(f"✗ 连接失败")
                    results["iperf3"] = {"error": "connection failed"}

        # 网络 PPS (Packets Per Second) 测试
        logger.info("  网络 PPS 测试 (UDP小包测试)...")
        if check.returncode != 0:  # iperf3 未安装
            logger.warning("  ⚠️  需要 iperf3")
            results["network_pps"] = {"skipped": "iperf3 not installed"}
        else:
            iperf_server = os.environ.get("IPERF3_SERVER")
            if not iperf_server:
                logger.warning("  ⚠️  未配置 iperf3 server")
                results["network_pps"] = {"skipped": "IPERF3_SERVER not configured"}
            else:
                # 使用 UDP 模式，小包大小（64字节），高带宽限制
                logger.info(f"  UDP 小包测试到 {iperf_server}...")
                result = subprocess.run(
                    ["iperf3", "-c", iperf_server, "-u", "-b", "10G",
                     "-l", "64", "-t", "10", "-J"],
                    capture_output=True, text=True, timeout=30
                )

                if result.returncode == 0:
                    try:
                        data = json.loads(result.stdout)
                        packets = data["end"]["sum"]["packets"]
                        seconds = data["end"]["sum"]["seconds"]
                        pps = packets / seconds

                        results["network_pps"] = {
                            "packets_per_second": pps,
                            "total_packets": packets,
                            "duration_seconds": seconds,
                            "packet_size_bytes": 64
                        }
                        logger.info(f"✓ {pps:.0f} PPS")
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"✗ 解析失败: {e}")
                        results["network_pps"] = {"error": str(e)}
                else:
                    logger.error(f"✗ 测试失败")
                    results["network_pps"] = {"error": "test failed"}

        # 测试下载带宽 (从公网下载测试文件) - 保留原有测试
        logger.info("  公网下载带宽测试 (curl, 10MB文件)...")
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
            results["curl_download_bandwidth_mbs"] = speed_mbs
            logger.info(f"✓ {speed_mbs:.2f} MB/s")
        else:
            logger.error(f"✗ 失败")

        # 测试上传带宽 (上传到测试服务) - 保留原有测试
        logger.info("  公网上传带宽测试 (curl, 5MB文件)...")
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
            results["curl_upload_bandwidth_mbs"] = speed_mbs
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
    parser.add_argument("--test",
                       choices=["cpu", "memory", "disk", "disk-full", "nbd-workload",
                               "network", "hugepages", "all"],
                       required=True, help="测试类型")
    parser.add_argument("--output", type=str, help="输出JSON文件路径")
    parser.add_argument("--test-dir", type=str, default="/tmp",
                       help="测试目录路径（默认: /tmp）")
    parser.add_argument("--num-sandboxes", type=int, default=38,
                       help="NBD模拟的沙箱数量（默认: 38）")
    parser.add_argument("--duration", type=int, default=60,
                       help="NBD工作负载测试时长（秒，默认: 60）")

    args = parser.parse_args()

    logger.info(f"\n{'='*60}")
    logger.info("宿主机性能测试")
    logger.info(f"{'='*60}\n")

    results = {}

    if args.test == "cpu" or args.test == "all":
        results["cpu"] = test_host_cpu_performance()

    if args.test == "memory" or args.test == "all":
        results["memory"] = test_host_memory_performance()

    if args.test == "disk":
        results["disk_io"] = test_host_disk_io(test_dir=args.test_dir, full_test=False)

    if args.test == "disk-full":
        results["disk_io_full"] = test_host_disk_io(test_dir=args.test_dir, full_test=True)

    if args.test == "nbd-workload":
        results["nbd_workload"] = test_nbd_workload(
            test_dir=args.test_dir,
            num_sandboxes=args.num_sandboxes,
            duration=args.duration
        )

    # --test all 运行所有测试，包括完整磁盘测试和 NBD 工作负载
    if args.test == "all":
        # 运行完整磁盘测试
        results["disk_io_full"] = test_host_disk_io(test_dir=args.test_dir, full_test=True)

        # 运行 NBD 工作负载模拟
        results["nbd_workload"] = test_nbd_workload(
            test_dir=args.test_dir,
            num_sandboxes=args.num_sandboxes,
            duration=args.duration
        )

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
