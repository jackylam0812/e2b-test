#!/bin/bash
# 沙箱内完整性能测试脚本
# 在沙箱内运行此脚本,一次性执行所有测试

echo "=========================================="
echo "沙箱内完整性能测试"
echo "=========================================="
echo ""

# 安装工具
echo "安装测试工具..."
apt-get update -qq
apt-get install -y -qq sysbench fio curl iputils-ping bc jq
echo "✓ 工具安装完成"
echo ""

# 1. CPU 测试
echo "1. CPU 性能测试"
echo "----------------------------------------"
THREADS=$(nproc)
echo "  单线程测试..."
SINGLE=$(sysbench cpu --threads=1 --time=10 run | grep "events per second" | awk '{print $NF}')
echo "  ✓ 单线程: $SINGLE events/s"

echo "  多线程测试 (${THREADS}线程)..."
MULTI=$(sysbench cpu --threads=${THREADS} --time=10 run | grep "events per second" | awk '{print $NF}')
echo "  ✓ 多线程: $MULTI events/s"
echo ""

# 2. 磁盘 I/O 测试
echo "2. 磁盘 I/O 性能测试"
echo "----------------------------------------"
WORK_DIR="${HOME:-/home/user}"

echo "  随机读 IOPS 测试..."
fio --name=randread --ioengine=libaio --iodepth=1 --rw=randread \
    --bs=4k --direct=1 --size=100M --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json > "${WORK_DIR}/fio_randread.json" 2>/dev/null
if [ -f "${WORK_DIR}/fio_randread.json" ]; then
    RAND_READ_IOPS=$(cat "${WORK_DIR}/fio_randread.json" | jq '.jobs[0].read.iops' 2>/dev/null || echo "null")
    rm -f "${WORK_DIR}/fio_randread.json"
else
    RAND_READ_IOPS="null"
fi
echo "  ✓ 随机读 IOPS: $RAND_READ_IOPS"

echo "  顺序读吞吐量测试..."
fio --name=seqread --ioengine=libaio --iodepth=16 --rw=read \
    --bs=1m --direct=1 --size=200M --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json > "${WORK_DIR}/fio_seqread.json" 2>/dev/null
if [ -f "${WORK_DIR}/fio_seqread.json" ]; then
    SEQ_READ_THROUGHPUT=$(cat "${WORK_DIR}/fio_seqread.json" | jq '.jobs[0].read.bw / 1024' 2>/dev/null || echo "null")
    rm -f "${WORK_DIR}/fio_seqread.json"
else
    SEQ_READ_THROUGHPUT="null"
fi
echo "  ✓ 顺序读吞吐量: $SEQ_READ_THROUGHPUT MB/s"

echo "  随机写 IOPS 测试..."
fio --name=randwrite --ioengine=libaio --iodepth=1 --rw=randwrite \
    --bs=4k --direct=1 --size=100M --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json > "${WORK_DIR}/fio_randwrite.json" 2>/dev/null
if [ -f "${WORK_DIR}/fio_randwrite.json" ]; then
    RAND_WRITE_IOPS=$(cat "${WORK_DIR}/fio_randwrite.json" | jq '.jobs[0].write.iops' 2>/dev/null || echo "null")
    rm -f "${WORK_DIR}/fio_randwrite.json"
else
    RAND_WRITE_IOPS="null"
fi
echo "  ✓ 随机写 IOPS: $RAND_WRITE_IOPS"

echo "  顺序写吞吐量测试..."
fio --name=seqwrite --ioengine=libaio --iodepth=16 --rw=write \
    --bs=1m --direct=1 --size=200M --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json > "${WORK_DIR}/fio_seqwrite.json" 2>/dev/null
if [ -f "${WORK_DIR}/fio_seqwrite.json" ]; then
    SEQ_WRITE_THROUGHPUT=$(cat "${WORK_DIR}/fio_seqwrite.json" | jq '.jobs[0].write.bw / 1024' 2>/dev/null || echo "null")
    rm -f "${WORK_DIR}/fio_seqwrite.json"
else
    SEQ_WRITE_THROUGHPUT="null"
fi
echo "  ✓ 顺序写吞吐量: $SEQ_WRITE_THROUGHPUT MB/s"

echo "  读延迟测试..."
fio --name=readlat --ioengine=libaio --iodepth=1 --rw=randread \
    --bs=4k --direct=1 --size=100M --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json --lat_percentiles=1 > "${WORK_DIR}/fio_readlat.json" 2>/dev/null
if [ -f "${WORK_DIR}/fio_readlat.json" ]; then
    READ_LAT_P50=$(cat "${WORK_DIR}/fio_readlat.json" | jq '.jobs[0].read.clat_ns.percentile."50.000000" / 1000' 2>/dev/null || echo "null")
    READ_LAT_P95=$(cat "${WORK_DIR}/fio_readlat.json" | jq '.jobs[0].read.clat_ns.percentile."95.000000" / 1000' 2>/dev/null || echo "null")
    READ_LAT_P99=$(cat "${WORK_DIR}/fio_readlat.json" | jq '.jobs[0].read.clat_ns.percentile."99.000000" / 1000' 2>/dev/null || echo "null")
    rm -f "${WORK_DIR}/fio_readlat.json"
else
    READ_LAT_P50="null"
    READ_LAT_P95="null"
    READ_LAT_P99="null"
fi
echo "  ✓ 读延迟 P50/P95/P99: $READ_LAT_P50 / $READ_LAT_P95 / $READ_LAT_P99 μs"

echo "  写延迟测试..."
fio --name=writelat --ioengine=libaio --iodepth=1 --rw=randwrite \
    --bs=4k --direct=1 --size=100M --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json --lat_percentiles=1 > "${WORK_DIR}/fio_writelat.json" 2>/dev/null
if [ -f "${WORK_DIR}/fio_writelat.json" ]; then
    WRITE_LAT_P50=$(cat "${WORK_DIR}/fio_writelat.json" | jq '.jobs[0].write.clat_ns.percentile."50.000000" / 1000' 2>/dev/null || echo "null")
    WRITE_LAT_P95=$(cat "${WORK_DIR}/fio_writelat.json" | jq '.jobs[0].write.clat_ns.percentile."95.000000" / 1000' 2>/dev/null || echo "null")
    WRITE_LAT_P99=$(cat "${WORK_DIR}/fio_writelat.json" | jq '.jobs[0].write.clat_ns.percentile."99.000000" / 1000' 2>/dev/null || echo "null")
    rm -f "${WORK_DIR}/fio_writelat.json"
else
    WRITE_LAT_P50="null"
    WRITE_LAT_P95="null"
    WRITE_LAT_P99="null"
fi
echo "  ✓ 写延迟 P50/P95/P99: $WRITE_LAT_P50 / $WRITE_LAT_P95 / $WRITE_LAT_P99 μs"
echo ""

# 3. 内存性能测试
echo "3. 内存性能测试"
echo "----------------------------------------"
echo "  内存写带宽测试..."
MEMORY_WRITE_OUTPUT=$(sysbench memory --memory-block-size=1M --memory-total-size=5G \
    --memory-oper=write --time=10 run 2>/dev/null)
MEMORY_WRITE_BW=$(echo "$MEMORY_WRITE_OUTPUT" | grep "transferred" | awk '{print $(NF-1)}')
MEMORY_WRITE_UNIT=$(echo "$MEMORY_WRITE_OUTPUT" | grep "transferred" | awk '{print $NF}' | tr -d '()')
# 转换为 MB/s
if [ "$MEMORY_WRITE_UNIT" = "GiB/sec" ]; then
    MEMORY_WRITE_MBS=$(echo "$MEMORY_WRITE_BW * 1024" | bc 2>/dev/null || echo "$MEMORY_WRITE_BW")
elif [ "$MEMORY_WRITE_UNIT" = "MiB/sec" ]; then
    MEMORY_WRITE_MBS=$MEMORY_WRITE_BW
else
    MEMORY_WRITE_MBS=$MEMORY_WRITE_BW
fi
echo "  ✓ 内存写带宽: $MEMORY_WRITE_MBS MB/s"

echo "  内存读带宽测试..."
MEMORY_READ_OUTPUT=$(sysbench memory --memory-block-size=1M --memory-total-size=5G \
    --memory-oper=read --time=10 run 2>/dev/null)
MEMORY_READ_BW=$(echo "$MEMORY_READ_OUTPUT" | grep "transferred" | awk '{print $(NF-1)}')
MEMORY_READ_UNIT=$(echo "$MEMORY_READ_OUTPUT" | grep "transferred" | awk '{print $NF}' | tr -d '()')
# 转换为 MB/s
if [ "$MEMORY_READ_UNIT" = "GiB/sec" ]; then
    MEMORY_READ_MBS=$(echo "$MEMORY_READ_BW * 1024" | bc 2>/dev/null || echo "$MEMORY_READ_BW")
elif [ "$MEMORY_READ_UNIT" = "MiB/sec" ]; then
    MEMORY_READ_MBS=$MEMORY_READ_BW
else
    MEMORY_READ_MBS=$MEMORY_READ_BW
fi
echo "  ✓ 内存读带宽: $MEMORY_READ_MBS MB/s"

echo "  随机内存访问测试..."
RANDOM_MEM_OUTPUT=$(sysbench memory --memory-block-size=4K --memory-total-size=1G \
    --memory-oper=read --memory-access-mode=rnd --time=10 run 2>/dev/null)
RANDOM_MEM_OPS=$(echo "$RANDOM_MEM_OUTPUT" | grep "total number of events" | awk '{print $NF}')
RANDOM_MEM_OPS_PER_SEC=$(echo "scale=2; $RANDOM_MEM_OPS / 10" | bc 2>/dev/null || echo "$RANDOM_MEM_OPS")
echo "  ✓ 随机访问: $RANDOM_MEM_OPS_PER_SEC ops/s"
echo ""

# 4. 网络测试 (智能切换: ping 优先,失败则使用 curl)
echo "4. 网络性能测试"
echo "----------------------------------------"

# 初始化变量
LATENCY="null"
DOWNLOAD_BW="null"
UPLOAD_BW="null"
PING_SUCCESS=false

# 4.1 尝试 ping 测试
echo "  网络延迟测试 (ping 8.8.8.8)..."
if timeout 5 ping -c 10 -W 2 8.8.8.8 &>/dev/null; then
    PING_SUCCESS=true
    LATENCY=$(ping -c 10 -W 2 8.8.8.8 2>/dev/null | grep 'rtt min/avg/max' | cut -d'=' -f2 | cut -d'/' -f2)
    if [ ! -z "$LATENCY" ]; then
        echo "  ✓ 平均延迟: $LATENCY ms (通过 ping)"
    else
        LATENCY="null"
        echo "  ⚠ 无法获取延迟数据"
    fi
else
    echo "  ✗ ping 8.8.8.8 失败，切换到 curl 测试模式"
fi

# 4.2 如果 ping 失败，使用 curl 测试延迟
if [ "$PING_SUCCESS" = false ]; then
    echo "  使用 curl 测试网络延迟..."

    # 尝试多个目标
    CURL_TARGETS=("https://www.google.com" "https://www.baidu.com" "https://httpbin.org/get")

    for TARGET in "${CURL_TARGETS[@]}"; do
        if CURL_TIME=$(curl -o /dev/null -s -w '%{time_total}' --max-time 10 "$TARGET" 2>/dev/null) && [ ! -z "$CURL_TIME" ]; then
            # 将秒转换为毫秒
            LATENCY=$(echo "$CURL_TIME * 1000" | bc 2>/dev/null)
            echo "  ✓ 请求延迟: $LATENCY ms (通过 curl 到 $TARGET)"
            break
        fi
    done

    if [ "$LATENCY" = "null" ]; then
        echo "  ✗ curl 延迟测试也失败，网络可能不可用"
    fi
fi

# 4.3 下载带宽测试
echo "  下载带宽测试 (10MB文件)..."

# 尝试多个下载源
DOWNLOAD_SOURCES=(
    "http://mirror.azure.cn/speedtest/10mb.bin|国内源"
    "http://speedtest.tele2.net/10MB.zip|国际源"
    "http://ipv4.download.thinkbroadband.com/10MB.zip|欧洲源"
)

for SOURCE in "${DOWNLOAD_SOURCES[@]}"; do
    URL=$(echo "$SOURCE" | cut -d'|' -f1)
    NAME=$(echo "$SOURCE" | cut -d'|' -f2)

    DOWNLOAD_START=$(date +%s.%N)

    if timeout 30 curl -o /tmp/test_download.bin -s --max-time 30 "$URL" 2>/dev/null; then
        DOWNLOAD_END=$(date +%s.%N)

        # 验证文件是否下载成功
        if [ -f /tmp/test_download.bin ] && [ -s /tmp/test_download.bin ]; then
            FILE_SIZE=$(stat -c%s /tmp/test_download.bin 2>/dev/null)
            DOWNLOAD_TIME=$(echo "$DOWNLOAD_END - $DOWNLOAD_START" | bc 2>/dev/null)

            # 避免除以0
            if [ "$(echo "$DOWNLOAD_TIME > 0" | bc)" -eq 1 ]; then
                # 转换为 MB/s
                DOWNLOAD_BW=$(echo "scale=2; $FILE_SIZE / 1024 / 1024 / $DOWNLOAD_TIME" | bc 2>/dev/null)
                echo "  ✓ 下载带宽: $DOWNLOAD_BW MB/s (从 $NAME)"
                rm -f /tmp/test_download.bin
                break
            fi
        fi
    fi

    rm -f /tmp/test_download.bin
done

if [ "$DOWNLOAD_BW" = "null" ]; then
    echo "  ✗ 所有下载测试失败"
fi

# 4.4 上传带宽测试
echo "  上传带宽测试 (5MB文件)..."

# 创建测试文件
dd if=/dev/zero of=/tmp/test_upload.bin bs=1M count=5 2>/dev/null

if [ -f /tmp/test_upload.bin ]; then
    # 尝试多个上传目标
    UPLOAD_URLS=(
        "https://httpbin.org/post"
        "https://postman-echo.com/post"
    )

    for URL in "${UPLOAD_URLS[@]}"; do
        UPLOAD_START=$(date +%s.%N)

        if timeout 60 curl -X POST -F "file=@/tmp/test_upload.bin" "$URL" -o /dev/null -s --max-time 60 2>/dev/null; then
            UPLOAD_END=$(date +%s.%N)
            UPLOAD_TIME=$(echo "$UPLOAD_END - $UPLOAD_START" | bc 2>/dev/null)

            # 避免除以0
            if [ "$(echo "$UPLOAD_TIME > 0" | bc)" -eq 1 ]; then
                UPLOAD_BW=$(echo "scale=2; 5 / $UPLOAD_TIME" | bc 2>/dev/null)
                echo "  ✓ 上传带宽: $UPLOAD_BW MB/s (到 $URL)"
                break
            fi
        fi
    done

    rm -f /tmp/test_upload.bin
fi

if [ "$UPLOAD_BW" = "null" ]; then
    echo "  ✗ 所有上传测试失败"
fi

echo ""

# 5. Python 性能测试
echo "5. Python 性能测试"
echo "----------------------------------------"
WORK_DIR="${HOME:-/home/user}"
cat > "${WORK_DIR}/python_bench.py" << 'PYEOF'
import time
import math

start = time.time()

# 数学计算
result = 0
for i in range(1000000):
    result += math.sqrt(i) * math.sin(i)

# 字符串操作
text = ""
for i in range(10000):
    text += str(i)

# 列表操作
data = [i for i in range(100000)]
data.sort(reverse=True)

elapsed = time.time() - start
score = 1000 / elapsed
print(f"{score:.2f}")
PYEOF

if [ -f "${WORK_DIR}/python_bench.py" ]; then
    PYTHON_SCORE=$(python3 "${WORK_DIR}/python_bench.py" 2>/dev/null || echo "null")
    rm -f "${WORK_DIR}/python_bench.py"
else
    PYTHON_SCORE="null"
fi
echo "  ✓ Python 性能: $PYTHON_SCORE 分"
echo ""

# 6. 包管理器速度测试
echo "6. 包管理器安装速度测试"
echo "----------------------------------------"
echo "  测试 pip 安装 requests..."
START_TIME=$(date +%s.%N)
pip install -q requests > /dev/null 2>&1
END_TIME=$(date +%s.%N)
PIP_TIME=$(echo "$END_TIME - $START_TIME" | bc)
echo "  ✓ pip 安装时间: $PIP_TIME 秒"
echo ""

# 生成完整的 JSON 结果
WORK_DIR="${HOME:-/home/user}"
RESULT_FILE="${WORK_DIR}/sandbox_complete_result.json"

cat > "$RESULT_FILE" << EOF
{
  "cpu": {
    "single_thread_events_per_sec": $SINGLE,
    "multi_thread_events_per_sec": $MULTI,
    "cpu_threads": $THREADS
  },
  "disk_io": {
    "random_read_iops": $RAND_READ_IOPS,
    "random_write_iops": $RAND_WRITE_IOPS,
    "sequential_read_throughput_mbs": $SEQ_READ_THROUGHPUT,
    "sequential_write_throughput_mbs": $SEQ_WRITE_THROUGHPUT,
    "read_latency_us": {
      "p50": $READ_LAT_P50,
      "p95": $READ_LAT_P95,
      "p99": $READ_LAT_P99
    },
    "write_latency_us": {
      "p50": $WRITE_LAT_P50,
      "p95": $WRITE_LAT_P95,
      "p99": $WRITE_LAT_P99
    }
  },
  "memory": {
    "write_bandwidth_mbs": $MEMORY_WRITE_MBS,
    "read_bandwidth_mbs": $MEMORY_READ_MBS,
    "random_access_ops_per_sec": $RANDOM_MEM_OPS_PER_SEC
  },
  "network": {
    "latency_ms": $LATENCY,
    "download_bandwidth_mbs": $DOWNLOAD_BW,
    "upload_bandwidth_mbs": $UPLOAD_BW
  },
  "python": {
    "performance_score": $PYTHON_SCORE
  },
  "package_manager": {
    "pip_install_time_sec": $PIP_TIME
  },
  "test_date": "$(date -Iseconds)"
}
EOF

echo "=========================================="
echo "所有测试完成!"
echo "=========================================="
echo ""
echo "完整结果:"
echo ""
if [ -f "$RESULT_FILE" ]; then
    cat "$RESULT_FILE"
    echo ""
    echo "结果已保存到: $RESULT_FILE"
else
    echo "警告: 无法保存结果文件"
fi
echo ""
echo "请将以上 JSON 保存为: outputs/sandbox_performance_manual.json"
