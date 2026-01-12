# 磁盘 I/O 性能测试工具集

这是一套完整的磁盘 I/O 性能测试和监控脚本，专门用于诊断 AWS EBS 和 NBD 相关的性能问题。

## 脚本列表

### 1. fio_comprehensive_test.sh - FIO 综合测试

**用途**：使用业界标准的 fio 工具进行全面的 I/O 性能测试。

**用法**：
```bash
bash fio_comprehensive_test.sh [测试目录]

# 示例
bash fio_comprehensive_test.sh /orchestrator/sandbox
```

**测试项目**：
- 顺序读/写
- 4K 随机读/写（关键测试）
- 混合读写
- 延迟测试
- 高队列深度测试
- fsync 性能测试

**运行时间**：约 8-10 分钟

**输出**：`/tmp/fio_results/`

---

### 2. realtime_io_monitor.sh - 实时 I/O 监控

**用途**：实时监控磁盘 I/O 性能指标。

**用法**：
```bash
bash realtime_io_monitor.sh [设备名] [监控时长(秒)] [采样间隔(秒)]

# 示例：监控 nvme1n1 设备 60 秒，每秒采样一次
bash realtime_io_monitor.sh nvme1n1 60 1
```

**监控指标**：
- IOPS (读/写)
- 吞吐量 (MB/s)
- I/O 延迟 (await)
- 队列长度
- 磁盘利用率

**运行时间**：根据参数设定

**输出**：`/tmp/io_monitor_<timestamp>/`

---

### 3. aws_ebs_monitor.sh - AWS EBS 监控

**用途**：使用 AWS CloudWatch 获取 EBS 卷的性能指标。

**前提条件**：
- 已安装 AWS CLI
- 已配置 AWS 凭证 (`aws configure`)

**用法**：
```bash
bash aws_ebs_monitor.sh <volume-id> [监控时长(分钟)]

# 示例：监控 vol-0323a2d805288d8c7 最近 60 分钟的数据
bash aws_ebs_monitor.sh vol-0323a2d805288d8c7 60
```

**监控指标**：
- IOPS (读/写)
- 吞吐量
- 延迟
- 队列长度
- 突发余额 (BurstBalance, 仅 gp2)
- IOPS 使用率

**运行时间**：约 1-2 分钟

**输出**：`/tmp/aws_ebs_monitor_<timestamp>/`

---

### 4. check_tail_latency.sh - 尾延迟检查

**用途**：检查磁盘 I/O 的尾延迟分布。

**用法**：
```bash
bash check_tail_latency.sh [测试目录]

# 示例
bash check_tail_latency.sh /orchestrator/sandbox
```

**运行时间**：约 2-3 分钟

**输出**：屏幕输出延迟分布统计

---

### 5. nbd_workload_simulator.sh - NBD 工作负载模拟器

**用途**：模拟多个沙箱并发运行时的 I/O 模式。

**用法**：
```bash
bash nbd_workload_simulator.sh [测试目录] [沙箱数量] [运行时长(秒)]

# 示例：模拟 38 个沙箱运行 300 秒
bash nbd_workload_simulator.sh /orchestrator/sandbox 38 300
```

**模拟场景**：
- 文件系统元数据操作（4K 随机写）
- 代码执行（64K 随机读）
- 日志写入（16K 顺序写）
- 混合工作负载

**运行时间**：根据参数设定（默认 5 分钟）

**输出**：`/orchestrator/sandbox/nbd_workload_test/`

---

## 推荐的测试流程

### 第 1 步：运行基础性能测试

使用统一入口脚本运行完整的硬件性能测试：

```bash
cd tests/host
python3 run_host_tests.py --all
```

或者使用 fio 进行详细的 I/O 测试：

```bash
cd tests/host/io_test_scripts
bash fio_comprehensive_test.sh /orchestrator/sandbox
```

**查看关键指标**：
- 4K 随机写 IOPS 是否 < 3000？
- 延迟是否 > 10ms？

### 第 2 步：实时监控

在运行实际工作负载时进行监控：

```bash
# 终端 1：启动监控
bash realtime_io_monitor.sh nvme1n1 300 1

# 终端 2：运行实际工作负载（如创建沙箱）
# ...
```

**查看关键指标**：
- await (I/O 等待时间) 是否 > 100ms？
- 队列长度是否 > 1？
- 磁盘利用率是否 > 90%？

### 第 3 步：AWS EBS 分析（如果是云环境）

```bash
# 获取 EBS 卷的 CloudWatch 指标
bash aws_ebs_monitor.sh vol-0323a2d805288d8c7 60
```

**查看关键指标**：
- IOPS 使用率是否 > 90%？
- BurstBalance (gp2) 是否 < 10%？
- 队列长度是否 > 1？

### 第 4 步：工作负载模拟

```bash
# 模拟实际的 NBD 工作负载
bash nbd_workload_simulator.sh /orchestrator/sandbox 38 300
```

**查看关键指标**：
- 总 IOPS 需求是多少？
- 是否超过当前 EBS 卷的配额？

---

## 性能基准

### AWS EBS 性能基准

| 卷类型 | 基准 IOPS | 突发 IOPS | 延迟 | 价格 (2TB) |
|:---|:---|:---|:---|:---|
| **gp2** | 3 IOPS/GB (最小 100) | 3000 | 1-3 ms | ~$200/月 |
| **gp3** | 3000 (固定) | 16000 | 1-3 ms | ~$160/月 |
| **io1** | 可配置 (最高 64000) | - | < 1 ms | ~$250/月 + IOPS 费用 |
| **io2** | 可配置 (最高 256000) | - | < 1 ms | ~$250/月 + IOPS 费用 |

### 4K 随机写入性能基准

| 存储类型 | IOPS | 速度 (MB/s) | 延迟 |
|:---|:---|:---|:---|
| **AWS gp2 (3000 IOPS)** | 3000 | 12 | 1-3 ms |
| **AWS gp3 (10000 IOPS)** | 10000 | 40 | 1-3 ms |
| **本地 NVMe SSD** | 100000+ | 400+ | < 0.1 ms |
| **您的测试结果** | ~1000 | 4.3 | > 100 ms |

---

## 问题诊断指南

### 症状 1：4K 随机写入速度 < 20 MB/s

**可能原因**：
- AWS EBS IOPS 耗尽（最常见）
- SSD 硬件故障
- 文件系统损坏

**诊断步骤**：
1. 运行 `aws_ebs_monitor.sh` 查看 IOPS 使用率
2. 检查 BurstBalance (gp2)
3. 运行 `smartctl -a /dev/nvme1n1` 检查硬件健康

### 症状 2：I/O 等待时间 (await) > 100ms

**可能原因**：
- 磁盘 IOPS 不足
- 队列积压
- 磁盘接近饱和

**诊断步骤**：
1. 运行 `realtime_io_monitor.sh` 查看队列长度
2. 检查磁盘利用率 (%util)
3. 运行 `aws_ebs_monitor.sh` 查看 VolumeQueueLength

### 症状 3：NBD 连接超时

**可能原因**：
- 底层磁盘 I/O 慢（最常见）
- orchestrator 无法及时响应
- 网络问题（Unix Socket 通常不是问题）

**诊断步骤**：
1. 运行 `python3 run_host_tests.py --disk` 测试磁盘性能
2. 运行 `nbd_workload_simulator.sh` 模拟实际负载
3. 运行 `aws_ebs_monitor.sh` 查看 EBS 性能

---

## 解决方案

### 方案 1：升级 AWS EBS 卷类型

```bash
# 从 gp2 升级到 gp3 (10,000 IOPS)
aws ec2 modify-volume \
  --volume-id vol-0323a2d805288d8c7 \
  --volume-type gp3 \
  --iops 10000 \
  --throughput 500
```

**效果**：
- IOPS 从 3000 提升到 10000
- 4K 随机写入速度从 4.3 MB/s 提升到 40+ MB/s
- NBD 超时问题彻底解决

**成本**：
- 仅增加约 $5/月

### 方案 2：更换硬盘（如果是硬件故障）

如果 `smartctl` 显示硬件错误，立即更换硬盘。

### 方案 3：优化应用层（临时方案）

- 减少并发沙箱数量
- 增加 NBD 超时时间
- 使用实例存储 (Instance Store) 代替 EBS

---

## 常见问题

### Q: 为什么顺序写入正常，但随机写入很慢？

A: 这是 IOPS 限制的典型特征。顺序写入的 I/O 操作数少，不会触及 IOPS 上限；随机写入的 I/O 操作数多，容易耗尽 IOPS 配额。

### Q: 如何判断是否需要升级 EBS？

A: 运行 `aws_ebs_monitor.sh`，如果 IOPS 使用率 > 70% 或 BurstBalance < 20%，建议升级。

### Q: fio 测试需要多长时间？

A: 默认每个测试运行 60 秒，总共约 8-10 分钟。可以修改脚本中的 `RUNTIME` 变量缩短时间。

### Q: 测试会影响生产环境吗？

A: 测试会产生大量 I/O，可能影响正在运行的服务。建议在低峰时段或测试环境中运行。

---

## 技术支持

如果您在使用这些脚本时遇到问题，或者需要进一步的诊断帮助，请提供以下信息：

1. 测试结果文件（`/tmp/` 下的输出目录）
2. `dmesg` 日志
3. `aws ec2 describe-volumes` 的输出
4. orchestrator 日志

---

**作者**: Manus AI  
**版本**: 1.0  
**日期**: 2025-12-09
