# 宿主机测试

宿主机性能测试套件，用于评估运行 E2B 服务的宿主机硬件和云存储性能。

## 目录结构

```
tests/host/
├── run_host_tests.py           # 统一测试入口（Python）
├── 04_host_performance.py      # 硬件性能测试
├── 05_cloud_storage.py         # 云存储性能测试
├── io_test_scripts/            # IO 专项测试工具集
│   ├── README.md               # IO 工具使用指南
│   ├── fio_comprehensive_test.sh
│   ├── aws_ebs_monitor.sh
│   ├── realtime_io_monitor.sh
│   ├── check_tail_latency.sh
│   └── nbd_workload_simulator.sh
└── README.md                   # 本文档
```

## 快速开始

### 运行所有测试

```bash
cd tests/host
python3 run_host_tests.py --all
```

### 运行指定测试

```bash
# CPU 测试
python3 run_host_tests.py --cpu

# 内存测试
python3 run_host_tests.py --memory

# 磁盘 I/O 测试
python3 run_host_tests.py --disk

# 网络测试
python3 run_host_tests.py --network

# 大页内存检查
python3 run_host_tests.py --hugepages

# 组合多个测试
python3 run_host_tests.py --cpu --memory --disk
```

### 云存储测试

```bash
# S3 测试
python3 run_host_tests.py --cloud-storage s3://your-bucket-name

# GCS 测试
python3 run_host_tests.py --cloud-storage gs://your-bucket-name
```

### 使用 IO 专项工具

```bash
# FIO 综合测试
python3 run_host_tests.py --io-tool fio_comprehensive_test

# AWS EBS 监控
python3 run_host_tests.py --io-tool aws_ebs_monitor --io-tool-args vol-123456

# 实时 I/O 监控
python3 run_host_tests.py --io-tool realtime_io_monitor --io-tool-args nvme1n1 60 1

# NBD 工作负载模拟
python3 run_host_tests.py --io-tool nbd_workload_simulator
```

### 指定输出目录

```bash
python3 run_host_tests.py --all --output /tmp/my_test_results
```

## 命令行选项

```
usage: run_host_tests.py [-h] [--all] [--cpu] [--memory] [--disk] [--network]
                         [--hugepages] [--cloud-storage BUCKET_URL]
                         [--io-tool TOOL] [--io-tool-args [ARGS ...]]
                         [--output OUTPUT] [--verbose]

硬件性能测试:
  --all              运行所有硬件性能测试
  --cpu              运行 CPU 性能测试
  --memory           运行内存性能测试
  --disk             运行磁盘 I/O 性能测试
  --network          运行网络性能测试
  --hugepages        检查大页内存配置

云存储测试:
  --cloud-storage BUCKET_URL
                     运行云存储测试 (例: s3://bucket 或 gs://bucket)

IO 测试工具:
  --io-tool TOOL     运行指定的 IO 测试工具
                     (fio_comprehensive_test, aws_ebs_monitor,
                      realtime_io_monitor, check_tail_latency,
                      nbd_workload_simulator)
  --io-tool-args [ARGS ...]
                     传递给 IO 工具的参数

通用选项:
  --output OUTPUT, -o OUTPUT
                     输出目录 (默认: ../../outputs)
  --verbose, -v      显示详细输出
```

## 测试指标

### 1. CPU 性能测试

测试项目：
- 单线程性能（events/sec）
- 多线程性能（events/sec）
- CPU 架构信息

### 2. 内存性能测试

测试项目：
- 内存读写带宽（MiB/s）
- 随机内存访问性能（ops/sec）

### 3. 磁盘 I/O 性能测试

测试项目：
- 随机读 IOPS（不同队列深度）
- 随机写 IOPS
- 顺序读写吞吐量（MB/s）
- 读写延迟分布（P50/P95/P99）

关键指标：
- **4K 随机写 IOPS**：< 3000 可能影响 NBD 性能
- **读写延迟**：> 10ms 可能导致 NBD 超时

### 4. 网络性能测试

测试项目：
- 公网延迟（ping）
- 下载/上传带宽（MB/s）
- speedtest 测试（可选）
- iperf3 内网带宽测试（可选）
- 网络 PPS（Packets Per Second）

### 5. 大页内存配置

检查项目：
- 是否启用大页内存
- 大页大小和数量
- 可用大页数量

### 6. 云存储性能测试

测试项目：
- 上传/下载延迟
- 小文件性能
- 大文件吞吐量
- 并发性能

## 输出文件

测试完成后，结果保存在输出目录中：

```
outputs/
├── host_test_summary.json       # 测试汇总
├── 04_host_performance.json     # 硬件性能测试结果
└── 05_cloud_storage.json        # 云存储测试结果（如果运行）
```

## 依赖工具

测试需要以下工具，脚本会提示安装：

- `sysbench` - CPU/内存测试
- `fio` - 磁盘 I/O 测试
- `speedtest` - 网络带宽测试（可选）
- `iperf3` - 内网带宽测试（可选）
- `aws-cli` - AWS 云存储测试（可选）
- `gsutil` - Google Cloud Storage 测试（可选）

安装命令（Ubuntu/Debian）：

```bash
# 基础工具
sudo apt-get update
sudo apt-get install -y sysbench fio

# 可选工具
sudo apt-get install -y iperf3

# Speedtest
curl -s https://packagecloud.io/install/repositories/ookla/speedtest-cli/script.deb.sh | sudo bash
sudo apt-get install speedtest

# AWS CLI
sudo apt-get install awscli

# Google Cloud SDK
# 参考: https://cloud.google.com/sdk/docs/install
```

## 性能基准参考

### AWS EBS 性能基准

| 卷类型 | 基准 IOPS | 延迟 | 价格 (2TB/月) |
|:---|:---|:---|:---|
| gp2 | 3 IOPS/GB (最小 100, 最大 16000) | 1-3 ms | ~$200 |
| gp3 | 3000 基准, 最高 16000 | 1-3 ms | ~$160 |
| io2 | 可配置, 最高 256000 | < 1 ms | ~$250 + IOPS 费用 |

### 4K 随机写性能对比

| 存储类型 | IOPS | 吞吐量 | 延迟 |
|:---|:---|:---|:---|
| AWS gp2 (3000 IOPS) | 3,000 | 12 MB/s | 1-3 ms |
| AWS gp3 (10000 IOPS) | 10,000 | 40 MB/s | 1-3 ms |
| 本地 NVMe SSD | 100,000+ | 400+ MB/s | < 0.1 ms |

## 故障诊断

### 问题 1: NBD 连接超时

**症状**：
- 沙箱创建缓慢或失败
- orchestrator 日志显示 NBD 超时

**诊断**：
```bash
# 1. 测试磁盘性能
python3 run_host_tests.py --disk

# 2. 检查关键指标
# - 4K 随机写 IOPS 是否 < 3000
# - 延迟是否 > 10ms
```

**解决方案**：
- 升级 AWS EBS 到 gp3 (10000 IOPS)
- 或使用实例存储 (Instance Store)

### 问题 2: 磁盘 I/O 慢

**症状**：
- 4K 随机写 < 3000 IOPS
- 延迟 > 10ms

**诊断**：
```bash
# 如果是 AWS EBS
python3 run_host_tests.py --io-tool aws_ebs_monitor --io-tool-args vol-xxxxx

# 检查：
# - IOPS 使用率是否 > 90%
# - BurstBalance 是否 < 20%
```

**解决方案**：
```bash
# 升级 EBS 卷类型
aws ec2 modify-volume \
  --volume-id vol-xxxxx \
  --volume-type gp3 \
  --iops 10000 \
  --throughput 500
```

## IO 专项工具

详细的 IO 测试工具文档请参考：[io_test_scripts/README.md](io_test_scripts/README.md)

工具列表：
1. **fio_comprehensive_test.sh** - FIO 综合 I/O 测试
2. **aws_ebs_monitor.sh** - AWS EBS 监控
3. **realtime_io_monitor.sh** - 实时 I/O 监控
4. **check_tail_latency.sh** - 尾延迟检查
5. **nbd_workload_simulator.sh** - NBD 工作负载模拟器

## 常见问题

### Q: 测试需要多长时间？

A:
- 完整测试（--all）：约 5-10 分钟
- 单项测试：1-3 分钟
- FIO 综合测试：8-10 分钟

### Q: 测试会影响生产环境吗？

A: 测试会产生大量 I/O 和 CPU 负载，可能影响正在运行的服务。建议：
- 在低峰时段运行
- 或在测试环境中运行

### Q: 如何解读测试结果？

A: 关注以下关键指标：
- CPU 单核性能 > 1000 events/s
- 内存带宽 > 10000 MiB/s
- 4K 随机写 IOPS > 3000
- 磁盘延迟 < 10ms
- 网络延迟 < 50ms

### Q: 旧的 run_host_tests.sh 还能用吗？

A: 建议使用新的 Python 版本 `run_host_tests.py`，它提供：
- 更好的错误处理
- 统一的输出格式
- 更多的命令行选项
- 更清晰的日志输出

旧脚本仍然保留但不再维护。

## 更新日志

### 2025-12-19
- 创建统一的 Python 入口脚本 `run_host_tests.py`
- 删除重复和过时的测试脚本
- 整理 IO 测试工具集
- 更新文档

### 2024-11-25
- 初始版本
- Shell 脚本入口

## 贡献

如有问题或建议，请提交 Issue 或 Pull Request。

---

**维护者**: E2B Team
**最后更新**: 2025-12-19
