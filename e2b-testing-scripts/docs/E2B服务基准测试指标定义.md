# E2B服务基准测试指标定义

**版本**: 4.0  
**日期**: 2025年11月20日

---

## 文档说明

本文档定义了用于对比云上自建E2B服务的完整基准测试指标体系,涵盖沙箱生命周期、模板管理、快照机制、沙箱内部性能、宿主机性能、云存储集成和成本核算等关键维度。

---

## 一、沙箱生命周期指标

### 1.1 沙箱创建性能

#### 1.1.1 冷启动延迟 (Cold Start Latency)

**定义**: 在无预热VM池、无本地缓存模板的情况下,从发起沙箱创建请求到沙箱完全可用的总耗时。

**计算方法**:
```
冷启动延迟 = T_ready - T_request
```

**分解指标**:
```
冷启动延迟 = 模板下载时间 + VM启动时间 + 初始化时间
```

**单位**: 毫秒 (ms)

**统计维度**: Min, Max, Mean, Median, P50, P95, P99, StdDev

**参考基准**: 
- Firecracker理论启动时间: 125-180ms
- 实际冷启动(含模板下载): 通常500-2000ms

---

#### 1.1.2 热启动延迟 (Warm Start Latency)

**定义**: 在有预热VM池、模板已缓存在本地的情况下,从发起沙箱创建请求到沙箱完全可用的总耗时。

**计算方法**:
```
热启动延迟 = T_ready - T_request (with pre-warmed VM pool and cached template)
```

**单位**: 毫秒 (ms)

**预期范围**: 100-300ms

---

#### 1.1.3 从快照恢复延迟 (Snapshot Restore Latency)

**定义**: 从已有快照恢复沙箱到完全可用的耗时。

**计算方法**:
```
快照恢复延迟 = T_ready - T_restore_request
```

**分解指标**:
```
快照恢复延迟 = 快照加载时间 + 内存恢复时间 + 状态初始化时间
```

**单位**: 毫秒 (ms)

**参考基准**: 使用快照可将启动时间降低到50-150ms。

**测试状态**: ⚠️ **当前E2B API不支持快照恢复功能,此指标暂时无法测试**

---

### 1.2 沙箱运行成本

#### 1.2.1 沙箱活跃成本 (Active Sandbox Cost)

**定义**: 沙箱执行代码时,每小时的资源消耗成本。

**计算方法**:
```
活跃成本 = (实例小时成本 / 单机最大沙箱密度) × 活跃资源占用比例
```

**单位**: 美元/小时/沙箱 (USD/hour/sandbox)

---

## 二、模板管理指标

E2B使用模板(Template)机制来预配置沙箱环境,模板性能直接影响冷启动速度。

### 2.1 模板构建性能

#### 2.1.1 模板构建时间 (Template Build Time)

**定义**: 从基础镜像构建自定义模板(安装依赖、配置环境)到模板可用的总耗时。

**计算方法**:
```
构建时间 = T_build_complete - T_build_start
```

**分解指标**:
```
构建时间 = 镜像上传时间 + 系统配置时间 + 快照生成时间
```

**单位**: 秒 (s) 或 分钟 (min)

---

### 2.2 模板存储成本

#### 2.2.1 模板存储成本 (Template Storage Cost)

**定义**: 在云存储中保存模板文件的月度成本。

**计算方法**:
```
存储成本 = 模板大小(GB) × 存储单价(USD/GB/月) × 模板数量
```

**单位**: 美元/月 (USD/month)

**云厂商差异**:
- **AWS S3**: $0.023/GB/月 (标准存储)
- **GCP GCS**: $0.020/GB/月 (标准存储)
- **Azure Blob**: $0.018/GB/月 (热存储)

---

## 三、快照机制指标

E2B使用Firecracker的快照(Snapshot)功能实现快速启动和状态保存。

### 3.1 快照创建性能

#### 3.1.1 快照创建时间 (Snapshot Creation Time)

**定义**: 将运行中的沙箱状态保存为快照的耗时。

**计算方法**:
```
快照创建时间 = T_snapshot_complete - T_snapshot_start
```

**分解指标**:
```
快照创建时间 = 内存快照时间 + 磁盘快照时间 + 元数据保存时间
```

**单位**: 毫秒 (ms) 或 秒 (s)

**参考基准**: Firecracker创建快照通常需要50-500ms,取决于内存大小。

---

### 3.2 快照存储成本

#### 3.2.1 快照存储成本 (Snapshot Storage Cost)

**定义**: 在云存储中保存快照文件的月度成本。

**计算方法**:
```
存储成本 = 快照大小(GB) × 存储单价(USD/GB/月) × 快照数量
```

**单位**: 美元/月 (USD/month)

---

## 四、沙箱内部性能指标

**测试前提**: 所有测试均在使用**同一模板**构建的沙箱内执行,以确保环境一致性。这些指标衡量不同云厂商的虚拟化开销、资源隔离质量和实际运行时性能。

### 4.1 沙箱CPU性能

#### 4.1.1 沙箱内CPU单线程性能 (Sandbox CPU Single-Thread Performance)

**定义**: 在沙箱内执行单线程计算任务的性能得分。

**计算方法**:
在沙箱内运行sysbench CPU基准测试:
```bash
# 在沙箱内执行
sysbench cpu --threads=1 --time=60 run
```

```
CPU单线程分数 = sysbench_events_per_second (threads=1)
```

**单位**: 事件/秒 (events/s)

**重要性**: 
- 衡量虚拟化层的CPU性能损失
- 对比宿主机原生CPU性能,计算虚拟化开销比例

**虚拟化开销计算**:
```
虚拟化开销 = (1 - 沙箱内分数 / 宿主机原生分数) × 100%
```

**参考基准**: Firecracker的虚拟化开销通常<5%,明显低于传统VM(10-20%)。

---

#### 4.1.2 沙箱内CPU多线程性能 (Sandbox CPU Multi-Thread Performance)

**定义**: 在沙箱内执行多线程计算任务的性能得分。

**计算方法**:
```bash
# 在沙箱内执行,N为沙箱的vCPU数量
sysbench cpu --threads=N --time=60 run
```

```
CPU多线程分数 = sysbench_events_per_second (threads=N)
```

**单位**: 事件/秒 (events/s)

**重要性**: 衡量多核资源分配和调度效率。

---

#### 4.1.3 沙箱CPU频率稳定性 (Sandbox CPU Frequency Stability)

**定义**: 沙箱内CPU频率的波动情况,衡量是否受"吵闹邻居"影响。

**计算方法**:
在沙箱内持续监控CPU频率:
```bash
# 在沙箱内执行
watch -n 1 "cat /proc/cpuinfo | grep MHz"
```

记录多次测量的频率值,计算:
```
频率波动系数 = 标准差 / 平均频率
```

**单位**: 无量纲比值

**目标值**: <0.05 (频率波动<5%)

**重要性**: 高波动说明资源竞争严重或CPU节能策略不合理。

---

### 4.2 沙箱内存性能

#### 4.2.1 沙箱内存带宽 (Sandbox Memory Bandwidth)

**定义**: 沙箱内内存的读写速度。

**计算方法**:
在沙箱内运行sysbench memory测试:
```bash
# 在沙箱内执行
sysbench memory --memory-block-size=1M --memory-total-size=3G run
```

```
内存带宽 = sysbench_memory_throughput
```

**单位**: MiB/s 或 GB/s

**虚拟化影响**: 对比宿主机原生内存带宽,计算性能损失。

---

#### 4.2.2 沙箱内存分配延迟 (Sandbox Memory Allocation Latency)

**定义**: 在沙箱内分配大块内存的延迟。

**计算方法**:
使用简单的C程序测试:
```c
// 在沙箱内编译执行
#include <stdlib.h>
#include <time.h>

int main() {
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    void* ptr = malloc(1024 * 1024 * 1024); // 1GB
    memset(ptr, 0, 1024 * 1024 * 1024);
    clock_gettime(CLOCK_MONOTONIC, &end);
    // 计算耗时
}
```

```
分配延迟 = T_end - T_start
```

**单位**: 毫秒 (ms)

**重要性**: 衡量内存资源的可用性和分配效率。

---

### 4.3 沙箱磁盘I/O性能

#### 4.3.1 沙箱随机读IOPS (Sandbox Random Read IOPS)

**定义**: 沙箱内磁盘每秒可执行的随机读操作次数。

**计算方法**:
在沙箱内运行fio测试:
```bash
# 在沙箱内执行
fio --name=randread --ioengine=libaio --iodepth=1 --rw=randread \
    --bs=4k --direct=1 --size=1G --numjobs=1 --runtime=60 --group_reporting
```

```
随机读IOPS = fio_random_read_iops
```

**单位**: IOPS

**测试参数**:
- 块大小: 4KB
- 队列深度: 1, 4, 16 (分别测试)
- 直接I/O: 是 (绕过页缓存)

**重要性**: 
- 衡量虚拟化层的I/O开销
- 对比宿主机原生IOPS,计算性能损失

---

#### 4.3.2 沙箱随机写IOPS (Sandbox Random Write IOPS)

**定义**: 沙箱内磁盘每秒可执行的随机写操作次数。

**计算方法**:
```bash
# 在沙箱内执行
fio --name=randwrite --ioengine=libaio --iodepth=1 --rw=randwrite \
    --bs=4k --direct=1 --size=1G --numjobs=1 --runtime=60 --group_reporting
```

```
随机写IOPS = fio_random_write_iops
```

**单位**: IOPS

---

#### 4.3.3 沙箱顺序读吞吐量 (Sandbox Sequential Read Throughput)

**定义**: 沙箱内磁盘顺序读取的数据传输速率。

**计算方法**:
```bash
# 在沙箱内执行
fio --name=seqread --ioengine=libaio --iodepth=16 --rw=read \
    --bs=1m --direct=1 --size=2G --numjobs=1 --runtime=60 --group_reporting
```

```
顺序读吞吐量 = fio_sequential_read_throughput
```

**单位**: MB/s

---

#### 4.3.4 沙箱顺序写吞吐量 (Sandbox Sequential Write Throughput)

**定义**: 沙箱内磁盘顺序写入的数据传输速率。

**计算方法**:
```bash
# 在沙箱内执行
fio --name=seqwrite --ioengine=libaio --iodepth=16 --rw=write \
    --bs=1m --direct=1 --size=2G --numjobs=1 --runtime=60 --group_reporting
```

```
顺序写吞吐量 = fio_sequential_write_throughput
```

**单位**: MB/s

---

#### 4.3.5 沙箱磁盘I/O延迟 (Sandbox Disk I/O Latency)

**定义**: 沙箱内磁盘I/O操作的延迟分布。

**计算方法**:
从fio输出中提取延迟指标:
```
平均延迟 = fio_avg_latency
P50延迟 = fio_p50_latency
P95延迟 = fio_p95_latency
P99延迟 = fio_p99_latency
```

**单位**: 微秒 (μs) 或 毫秒 (ms)

**重要性**: P99延迟反映极端情况下的性能,对延迟敏感型应用至关重要。

---

### 4.4 沙箱网络性能

#### 4.4.1 沙箱对外网络延迟 (Sandbox External Network Latency)

**定义**: 从沙箱内访问外部网络的往返时间。

**计算方法**:
在沙箱内ping公共DNS:
```bash
# 在沙箱内执行
ping -c 100 8.8.8.8
```

```
网络延迟 = ping_rtt_average
```

**单位**: 毫秒 (ms)

**统计维度**: 最小值、平均值、最大值、标准差

**虚拟化开销**: 对比宿主机直接ping的延迟,计算额外开销。

---

#### 4.4.2 沙箱下载带宽 (Sandbox Download Bandwidth)

**定义**: 沙箱从外部下载数据的最大速率。

**计算方法**:
在沙箱内下载测试文件:
```bash
# 在沙箱内执行
curl -o /dev/null https://speed.cloudflare.com/100mb.bin
```

```
下载带宽 = 文件大小 / 下载耗时
```

**单位**: Mbps 或 MB/s

**重要性**: 影响沙箱内下载依赖包、访问API的速度。

---

#### 4.4.3 沙箱上传带宽 (Sandbox Upload Bandwidth)

**定义**: 沙箱向外部上传数据的最大速率。

**计算方法**:
在沙箱内上传测试文件到公共服务:
```bash
# 在沙箱内执行
curl -T test_file.bin https://transfer.sh/test_file.bin
```

```
上传带宽 = 文件大小 / 上传耗时
```

**单位**: Mbps 或 MB/s

---

#### 4.4.4 沙箱网络吞吐量稳定性 (Sandbox Network Throughput Stability)

**定义**: 沙箱网络带宽的波动情况,衡量是否受同宿主机其他沙箱影响。

**计算方法**:
多次测试下载速度,计算:
```
带宽波动系数 = 标准差 / 平均带宽
```

**单位**: 无量纲比值

**目标值**: <0.1 (波动<10%)

---

### 4.5 沙箱应用场景性能

#### 4.5.1 Python代码执行性能 (Python Code Execution Performance)

**定义**: 在沙箱内执行标准Python基准测试的性能。

**计算方法**:
在沙箱内运行pyperformance:
```bash
# 在沙箱内执行
pip install pyperformance
pyperformance run -o results.json
```

```
Python性能分数 = pyperformance_geometric_mean
```

**单位**: 分数 (score)

**重要性**: E2B常用于Python代码执行,该指标直接反映实际业务性能。

---

#### 4.5.2 Node.js代码执行性能 (Node.js Code Execution Performance)

**定义**: 在沙箱内执行标准Node.js基准测试的性能。

**计算方法**:
在沙箱内运行Octane或自定义基准测试:
```bash
# 在沙箱内执行
node benchmark.js
```

```
Node.js性能分数 = benchmark_score
```

**单位**: 分数 (score) 或 操作/秒

---

#### 4.5.3 包管理器安装速度 (Package Manager Installation Speed)

**定义**: 在沙箱内安装常用依赖包的速度。

**计算方法**:
测试安装标准包:
```bash
# Python (pip)
time pip install numpy pandas scikit-learn

# Node.js (npm)
time npm install express react lodash
```

```
安装速度 = 安装总耗时
```

**单位**: 秒 (s)

**影响因素**:
- 网络下载速度
- 磁盘I/O性能
- CPU性能(编译原生扩展)

---

#### 4.5.4 容器内容器性能 (Container-in-Sandbox Performance)

**定义**: 在沙箱内运行Docker容器的性能(如果支持嵌套虚拟化)。

**计算方法**:
```bash
# 在沙箱内执行
time docker run --rm alpine echo "Hello"
```

```
容器启动延迟 = docker_run_time
```

**单位**: 秒 (s)

**注意**: 嵌套虚拟化性能开销较大,不同云厂商支持情况不同。

---

### 4.6 沙箱资源隔离质量

#### 4.6.1 CPU隔离效果 (CPU Isolation Quality)

**定义**: 沙箱是否受同宿主机其他沙箱的CPU竞争影响。

**计算方法**:
1. 在空闲宿主机上测试沙箱CPU性能,记为`基准分数`
2. 在同一宿主机上启动多个高CPU负载沙箱
3. 再次测试目标沙箱CPU性能,记为`负载分数`

```
CPU隔离效果 = (1 - |负载分数 - 基准分数| / 基准分数) × 100%
```

**单位**: 百分比 (%)

**目标值**: >95% (性能下降<5%)

**重要性**: 衡量"吵闹邻居"问题的严重程度。

---

#### 4.6.2 内存隔离效果 (Memory Isolation Quality)

**定义**: 沙箱内存性能是否受其他沙箱影响。

**计算方法**:
类似CPU隔离测试,对比空闲和高内存负载下的内存带宽。

```
内存隔离效果 = (1 - |负载带宽 - 基准带宽| / 基准带宽) × 100%
```

**单位**: 百分比 (%)

---

#### 4.6.3 磁盘I/O隔离效果 (Disk I/O Isolation Quality)

**定义**: 沙箱磁盘I/O性能是否受其他沙箱影响。

**计算方法**:
类似CPU隔离测试,对比空闲和高I/O负载下的IOPS。

```
磁盘I/O隔离效果 = (1 - |负载IOPS - 基准IOPS| / 基准IOPS) × 100%
```

**单位**: 百分比 (%)

**重要性**: 磁盘I/O是最容易受"吵闹邻居"影响的资源。

---

## 五、宿主机性能指标

宿主机的底层性能直接决定E2B服务的上限。

### 5.1 CPU性能

#### 5.1.1 CPU单核性能 (Single-Core CPU Performance)

**定义**: 宿主机单个物理核心的计算性能。

**计算方法**:
使用标准基准测试工具(如sysbench、Geekbench):
```
单核分数 = benchmark_single_core_score
```

**单位**: 分数 (score) 或 GFLOPS

**重要性**: 影响沙箱内单线程任务的执行速度。

---

#### 5.1.2 CPU多核性能 (Multi-Core CPU Performance)

**定义**: 宿主机所有物理核心并行计算的性能。

**计算方法**:
```
多核分数 = benchmark_multi_core_score
```

**单位**: 分数 (score) 或 GFLOPS

---

#### 5.1.3 CPU架构与型号 (CPU Architecture & Model)

**定义**: 宿主机使用的CPU型号和微架构。

**记录内容**:
- CPU厂商: Intel / AMD / ARM
- 型号: 如 Intel Xeon Platinum 8488C (Sapphire Rapids)
- 代次: 如 AMD EPYC 9004 (Genoa)
- 基础频率和睿频
- 核心数和线程数

**重要性**: 不同代次CPU性能差异可达30-50%。

---

### 5.2 内存性能

#### 5.2.1 内存带宽 (Memory Bandwidth)

**定义**: 宿主机内存的读写速度。

**计算方法**:
使用内存基准测试工具(如STREAM、sysbench memory):
```
内存带宽 = benchmark_memory_bandwidth
```

**单位**: GB/s

**测试模式**:
- 顺序读带宽
- 顺序写带宽
- 随机读带宽
- 随机写带宽

**参考基准**:
- DDR4-3200: 约25 GB/s/通道
- DDR5-4800: 约38 GB/s/通道

---

#### 5.2.2 内存延迟 (Memory Latency)

**定义**: 内存随机访问的平均延迟。

**计算方法**:
```
内存延迟 = benchmark_memory_latency
```

**单位**: 纳秒 (ns)

**参考基准**: 现代服务器内存延迟通常在60-100ns。

---

#### 5.2.3 大页内存支持 (Huge Pages Support)

**定义**: 宿主机是否启用大页内存(Huge Pages),以及大页大小。

**测量方法**:
检查系统配置:
```bash
cat /proc/meminfo | grep Huge
```

**记录内容**:
- 是否启用: Yes/No
- 大页大小: 2MB / 1GB
- 可用大页数量
- 大页内存总量

**重要性**: 
- 大页内存可减少TLB缺失,提升性能5-15%
- 对内存密集型沙箱任务影响显著
- Firecracker官方推荐启用大页内存

**性能提升计算**:
```
大页内存性能提升 = (启用大页后性能 - 未启用性能) / 未启用性能 × 100%
```

---

### 5.3 存储I/O性能

#### 5.3.1 本地磁盘随机读IOPS (Local Disk Random Read IOPS)

**定义**: 宿主机本地磁盘每秒可执行的随机读操作次数。

**计算方法**:
使用fio测试:
```
随机读IOPS = fio_random_read_iops
```

**测试参数**:
- 块大小: 4KB
- 队列深度: 1, 4, 16, 32 (分别测试)
- 读写模式: randread
- 测试时长: 60秒

**单位**: IOPS

**参考基准**:
- SATA SSD: 10K-50K IOPS
- NVMe SSD: 100K-500K IOPS
- 云盘(如AWS EBS gp3): 3K-16K IOPS

---

#### 5.3.2 本地磁盘随机写IOPS (Local Disk Random Write IOPS)

**定义**: 宿主机本地磁盘每秒可执行的随机写操作次数。

**计算方法**:
```
随机写IOPS = fio_random_write_iops
```

**单位**: IOPS

---

#### 5.3.3 本地磁盘顺序读吞吐量 (Local Disk Sequential Read Throughput)

**定义**: 宿主机本地磁盘顺序读取的数据传输速率。

**计算方法**:
```
顺序读吞吐量 = fio_sequential_read_throughput
```

**测试参数**:
- 块大小: 1MB
- 读写模式: read
- 测试时长: 60秒

**单位**: MB/s 或 GB/s

**参考基准**:
- SATA SSD: 500-600 MB/s
- NVMe SSD: 2000-7000 MB/s

---

#### 5.3.4 本地磁盘顺序写吞吐量 (Local Disk Sequential Write Throughput)

**定义**: 宿主机本地磁盘顺序写入的数据传输速率。

**计算方法**:
```
顺序写吞吐量 = fio_sequential_write_throughput
```

**单位**: MB/s 或 GB/s

---

#### 5.3.5 磁盘延迟 (Disk Latency)

**定义**: 磁盘I/O操作的平均延迟。

**计算方法**:
```
磁盘延迟 = fio_average_latency
```

**统计维度**: 平均延迟、P50、P95、P99

**单位**: 微秒 (μs) 或 毫秒 (ms)

**参考基准**:
- NVMe SSD: 100-300 μs
- SATA SSD: 500-1000 μs
- 云盘: 1-10 ms

---

### 5.4 网络I/O性能

#### 5.4.1 宿主机内网带宽 (Host Internal Network Bandwidth)

**定义**: 宿主机到同区域内其他资源(如云存储、其他VM)的网络带宽。

**计算方法**:
使用iperf3测试:
```
内网带宽 = iperf3_bandwidth
```

**单位**: Gbps 或 MB/s

**测试场景**:
- 宿主机到同可用区VM
- 宿主机到区域内云存储(GCS/S3)

**参考基准**:
- AWS: 最高25 Gbps (取决于实例类型)
- GCP: 最高32 Gbps
- Azure: 最高30 Gbps

---

#### 5.4.2 宿主机公网带宽 (Host Internet Bandwidth)

**定义**: 宿主机到公网的上传和下载带宽。

**计算方法**:
```
公网下载带宽 = speedtest_download_bandwidth
公网上传带宽 = speedtest_upload_bandwidth
```

**单位**: Mbps 或 Gbps

**重要性**: 影响沙箱访问外部API和下载依赖包的速度。

---

#### 5.4.3 宿主机到云存储延迟 (Host to Cloud Storage Latency)

**定义**: 宿主机访问云存储(GCS/S3)的网络延迟。

**计算方法**:
使用ping或HTTP请求测试:
```
存储延迟 = ping_rtt_to_storage_endpoint
```

**单位**: 毫秒 (ms)

**重要性**: 影响模板和快照的下载速度。

**参考基准**:
- 同区域: 1-5 ms
- 跨区域: 10-100 ms

---

#### 5.4.4 宿主机网络PPS (Packets Per Second)

**定义**: 宿主机每秒可处理的网络数据包数量。

**计算方法**:
使用pktgen或iperf3测试:
```
PPS = packets_per_second
```

**单位**: PPS (packets/second)

**重要性**: 
- 影响高并发小数据包场景的性能
- 对WebSocket、gRPC等协议影响显著

**参考基准**: 现代云实例通常可达100K-1M PPS。

---

## 六、云存储集成性能指标

E2B依赖云存储(GCS/S3)保存模板和快照,存储性能至关重要。

### 6.1 对象存储上传性能

#### 6.1.1 小文件上传速度 (Small File Upload Speed)

**定义**: 上传小文件(如1MB)到云存储的速度。

**计算方法**:
```
小文件上传速度 = 文件大小 / 上传耗时
```

**测试文件大小**: 1MB, 10MB

**单位**: MB/s

**重要性**: 影响快照元数据和小型模板的上传。

---

#### 6.1.2 大文件上传速度 (Large File Upload Speed)

**定义**: 上传大文件(如1GB)到云存储的速度。

**计算方法**:
```
大文件上传速度 = 文件大小 / 上传耗时
```

**测试文件大小**: 100MB, 1GB

**单位**: MB/s

**优化策略**: 使用分块上传(Multipart Upload)。

---

#### 6.1.3 并行上传吞吐量 (Parallel Upload Throughput)

**定义**: 同时上传多个文件时的总吞吐量。

**计算方法**:
```
并行吞吐量 = 总上传数据量 / 总耗时
```

**测试场景**: 同时上传10个100MB文件。

**单位**: MB/s

---

### 6.2 对象存储下载性能

#### 6.2.1 小文件下载速度 (Small File Download Speed)

**定义**: 从云存储下载小文件的速度。

**计算方法**:
```
小文件下载速度 = 文件大小 / 下载耗时
```

**单位**: MB/s

---

#### 6.2.2 大文件下载速度 (Large File Download Speed)

**定义**: 从云存储下载大文件的速度。

**计算方法**:
```
大文件下载速度 = 文件大小 / 下载耗时
```

**单位**: MB/s

**重要性**: 直接影响冷启动时模板下载的速度。

---

#### 6.2.3 并行下载吞吐量 (Parallel Download Throughput)

**定义**: 同时下载多个文件时的总吞吐量。

**计算方法**:
```
并行吞吐量 = 总下载数据量 / 总耗时
```

**单位**: MB/s

---

### 6.3 对象存储操作延迟

#### 6.3.1 对象列举延迟 (Object List Latency)

**定义**: 列举存储桶中对象列表的延迟。

**计算方法**:
```
列举延迟 = T_list_complete - T_list_start
```

**单位**: 毫秒 (ms)

**影响因素**: 对象数量、分页大小。

---

#### 6.3.2 对象元数据读取延迟 (Object Metadata Read Latency)

**定义**: 读取对象元数据(如大小、修改时间)的延迟。

**计算方法**:
```
元数据延迟 = T_metadata_received - T_metadata_request
```

**单位**: 毫秒 (ms)

---

## 七、综合成本指标

### 7.1 基础设施成本

#### 7.1.1 实例计算成本 (Compute Cost)

**定义**: 运行E2B服务的虚拟机实例的月度成本。

**计算方法**:
```
月度计算成本 = 实例小时价格 × 730小时 × 实例数量
```

**定价模式**:
- 按需 (On-Demand)
- 1年预留 (1-Year Reserved)
- 3年预留 (3-Year Reserved)
- 竞价 (Spot/Preemptible)

**单位**: 美元/月 (USD/month)

---

#### 7.1.2 存储成本细分 (Storage Cost Breakdown)

**定义**: 所有存储相关的成本,包括本地磁盘、模板存储、快照存储。

**计算方法**:
```
总存储成本 = 本地磁盘成本 + 模板存储成本 + 快照存储成本
```

**各项计算**:
- **本地磁盘成本**: `磁盘容量(GB) × 本地磁盘单价`
- **模板存储成本**: `模板总大小(GB) × 对象存储单价`
- **快照存储成本**: `快照总大小(GB) × 对象存储单价`

**单位**: 美元/月 (USD/month)

---

### 7.2 单位成本指标

#### 7.2.1 每沙箱小时成本 (Cost Per Sandbox Hour)

**定义**: 运行一个沙箱一小时的平均成本。

**计算方法**:
```
每沙箱小时成本 = (实例小时成本 + 存储小时成本 + 网络小时成本) / 平均并发沙箱数
```

**单位**: 美元/沙箱/小时 (USD/sandbox/hour)

---

#### 7.2.2 单位算力成本 (Cost Per Performance Unit)

**定义**: 获得单位CPU性能所需的成本。

**计算方法**:
```
单位算力成本 = 实例月度成本 / CPU多核性能分数
```

**单位**: 美元/分 (USD/score)

**重要性**: 这是最直接的性价比指标,越低越好。

---

## 八、指标优先级与测试建议

### 8.1 核心指标(必测)

以下指标对E2B服务影响最大,必须测试:

1. **沙箱冷启动延迟(P95)** - 用户体验的关键
2. **沙箱热启动延迟(P50)** - 优化后的常态性能
3. ~~**快照恢复延迟**~~ - ⚠️ 当前无法测试(API不支持)
4. **沙箱内CPU性能** - 实际计算能力(含虚拟化开销)
5. **沙箱内磁盘随机读IOPS** - 实际I/O性能
6. **Python/Node.js代码执行性能** - 业务场景真实性能
7. **CPU/I/O隔离效果** - "吵闹邻居"影响程度
8. **云存储上传/下载速度** - 影响模板/快照传输的主要因素
9. **宿主机到云存储延迟** - 影响模板/快照访问
10. **大页内存性能提升** - 性能优化关键
11. **单位算力成本** - 性价比核心指标
12. **模板存储成本** - 长期运营成本

### 8.2 重要指标(建议测)

13. **本地磁盘顺序读吞吐量** - 大文件I/O
14. **宿主机内存带宽** - 内存密集型任务
15. **宿主机内网带宽** - 分布式场景
16. **沙箱网络带宽** - 下载依赖包速度
17. **包管理器安装速度** - 实际开发体验
18. **并发启动吞吐量** - 扩展能力
19. **单机沙箱密度** - 资源利用率

### 8.3 可选指标(按需测)

20. **快照创建时间** - 状态保存场景
21. **模板构建时间** - CI/CD场景
22. **对象存储并行吞吐量** - 大规模部署
23. **容器内容器性能** - 嵌套虚拟化场景

---

## 九、测试标准与前提条件

### 9.1 配置一致性

#### 9.1.1 宿主机配置一致性

所有云厂商测试环境应满足:
- **vCPU**: 96核(或等效)
- **内存**: 384GB
- **本地存储**: 6TB SSD
- **CPU代次**: 优先选择2023-2024年发布的最新代
- **区域**: 地理位置相近,优先美东

#### 9.1.2 沙箱模板一致性

**关键要求**: 所有沙箱内部性能测试必须使用**同一模板**构建的沙箱,以消除环境差异。

**模板基础**: 使用统一的Dockerfile.base构建

**模板验证命令**:
```bash
# 在沙箱内执行
uname -a                    # 验证内核版本
sysbench --version         # 验证sysbench版本
fio --version              # 验证fio版本
python3 --version          # 验证Python版本
node --version             # 验证Node.js版本
```

### 9.2 测试执行标准

- **测试次数**: 每项指标≥10次
- **统计方法**: 使用中位数,剔除异常值(±3σ)
- **测试间隔**: ≥1秒
- **测试时段**: 避开维护窗口和高峰期

### 9.3 环境配置

- **网络优化**: 记录TCP参数配置
- **存储优化**: 记录文件系统类型和挂载参数

---

## 附录: 完整指标速查表

| 类别 | 指标 | 单位 | 计算方法 | 优先级 |
|-----|------|------|---------|--------|
| **沙箱生命周期** | 冷启动延迟 | ms | T_ready - T_request | 🔴 核心 |
| | 热启动延迟 | ms | T_ready - T_request (预热) | 🔴 核心 |
| | ~~快照恢复延迟~~ | ms | ⚠️ 无法测试 | ⚠️ N/A |
| | 沙箱活跃成本 | USD/h | 实例成本/密度×占用比 | 🟡 重要 |
| **模板管理** | 模板构建时间 | s | T_complete - T_start | 🟢 可选 |
| | 模板存储成本 | USD/月 | 大小×单价×数量 | 🔴 核心 |
| **快照机制** | 快照创建时间 | ms | T_complete - T_start | 🟢 可选 |
| | 快照存储成本 | USD/月 | 大小×单价×数量 | 🟡 重要 |
| **沙箱内CPU** | 沙箱CPU单线程性能 | events/s | sysbench结果(沙箱内) | 🔴 核心 |
| | 沙箱CPU多线程性能 | events/s | sysbench结果(沙箱内) | 🔴 核心 |
| | 虚拟化开销 | % | (1-沙箱分数/宿主机分数)×100% | 🔴 核心 |
| | CPU频率稳定性 | - | 标准差/平均频率 | 🟡 重要 |
| **沙箱内存** | 沙箱内存带宽 | MiB/s | sysbench结果(沙箱内) | 🟡 重要 |
| | 内存分配延迟 | ms | malloc+memset耗时 | 🟢 可选 |
| **沙箱磁盘I/O** | 沙箱随机读IOPS | IOPS | fio结果(沙箱内) | 🔴 核心 |
| | 沙箱随机写IOPS | IOPS | fio结果(沙箱内) | 🟡 重要 |
| | 沙箱顺序读吞吐量 | MB/s | fio结果(沙箱内) | 🟡 重要 |
| | 沙箱顺序写吞吐量 | MB/s | fio结果(沙箱内) | 🟡 重要 |
| | 沙箱磁盘I/O延迟(P99) | μs | fio P99结果 | 🟡 重要 |
| **沙箱网络** | 沙箱对外网络延迟 | ms | ping RTT(沙箱内) | 🟡 重要 |
| | 沙箱下载带宽 | Mbps | curl下载速度 | 🟡 重要 |
| | 沙箱上传带宽 | Mbps | curl上传速度 | 🟡 重要 |
| | 网络吞吐量稳定性 | - | 标准差/平均带宽 | 🟢 可选 |
| **沙箱应用** | Python代码执行性能 | score | pyperformance结果 | 🔴 核心 |
| | Node.js代码执行性能 | score | benchmark结果 | 🟡 重要 |
| | 包管理器安装速度 | s | pip/npm install耗时 | 🟡 重要 |
| | 容器内容器性能 | s | docker run耗时 | 🟢 可选 |
| **资源隔离** | CPU隔离效果 | % | 负载下性能保持率 | 🔴 核心 |
| | 内存隔离效果 | % | 负载下带宽保持率 | 🟡 重要 |
| | 磁盘I/O隔离效果 | % | 负载下IOPS保持率 | 🟡 重要 |
| **宿主机CPU** | CPU单核性能 | score | benchmark结果 | 🟡 重要 |
| | CPU多核性能 | score | benchmark结果 | 🔴 核心 |
| | CPU架构型号 | - | 型号记录 | 🔴 核心 |
| **宿主机内存** | 内存带宽 | GB/s | STREAM结果 | 🟡 重要 |
| | 内存延迟 | ns | benchmark结果 | 🟢 可选 |
| | 大页内存性能提升 | % | (启用后-未启用)/未启用×100% | 🔴 核心 |
| **宿主机存储** | 随机读IOPS | IOPS | fio结果 | 🔴 核心 |
| | 随机写IOPS | IOPS | fio结果 | 🟡 重要 |
| | 顺序读吞吐量 | MB/s | fio结果 | 🟡 重要 |
| | 顺序写吞吐量 | MB/s | fio结果 | 🟡 重要 |
| | 磁盘延迟(P99) | μs | fio结果 | 🟡 重要 |
| **宿主机网络** | 内网带宽 | Gbps | iperf3结果 | 🟡 重要 |
| | 公网带宽 | Mbps | speedtest结果 | 🟢 可选 |
| | 到云存储延迟 | ms | ping RTT | 🔴 核心 |
| | 网络PPS | PPS | pktgen结果 | 🟢 可选 |
| **云存储** | 小文件上传速度 | MB/s | 大小/耗时 | 🟡 重要 |
| | 大文件上传速度 | MB/s | 大小/耗时 | 🟡 重要 |
| | 小文件下载速度 | MB/s | 大小/耗时 | 🟡 重要 |
| | 大文件下载速度 | MB/s | 大小/耗时 | 🟡 重要 |
| | 并行上传吞吐量 | MB/s | 总量/总耗时 | 🟢 可选 |
| | 并行下载吞吐量 | MB/s | 总量/总耗时 | 🟢 可选 |
| | 对象列举延迟 | ms | T_complete - T_start | 🟢 可选 |
| | 对象元数据读取延迟 | ms | T_received - T_request | 🟢 可选 |
| **成本** | 实例月度成本 | USD/月 | 小时价格×730 | 🔴 核心 |
| | 存储成本细分 | USD/月 | 本地+模板+快照 | 🔴 核心 |
| | 每沙箱小时成本 | USD/h | 总成本/并发数 | 🟡 重要 |
| | 单位算力成本 | USD/分 | 月成本/CPU分数 | 🔴 核心 |

---

**文档结束**
