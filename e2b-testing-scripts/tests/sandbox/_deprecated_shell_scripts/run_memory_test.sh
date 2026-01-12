#!/bin/bash
# 沙箱内内存性能测试脚本
# 在沙箱内运行此脚本

echo "=========================================="
echo "沙箱内内存性能测试"
echo "=========================================="
echo ""

# 安装 sysbench
echo "安装 sysbench..."
apt-get update -qq && apt-get install -y -qq sysbench bc
echo "✓ 安装完成"
echo ""

# 1. 内存带宽测试 (顺序读写)
echo "内存带宽测试 (顺序读写, 10秒)..."
MEMORY_OUTPUT=$(sysbench memory --memory-block-size=1M --memory-total-size=10G \
    --memory-oper=write --time=10 run)
MEMORY_BANDWIDTH=$(echo "$MEMORY_OUTPUT" | grep "transferred" | awk '{print $(NF-1)}')
MEMORY_BANDWIDTH_UNIT=$(echo "$MEMORY_OUTPUT" | grep "transferred" | awk '{print $NF}' | tr -d '()')

# 转换为 MB/s
if [ "$MEMORY_BANDWIDTH_UNIT" = "GiB/sec" ]; then
    MEMORY_BANDWIDTH_MBS=$(echo "$MEMORY_BANDWIDTH * 1024" | bc)
elif [ "$MEMORY_BANDWIDTH_UNIT" = "MiB/sec" ]; then
    MEMORY_BANDWIDTH_MBS=$MEMORY_BANDWIDTH
else
    MEMORY_BANDWIDTH_MBS=$MEMORY_BANDWIDTH
fi

echo "✓ 内存写带宽: $MEMORY_BANDWIDTH_MBS MB/s"
echo ""

# 2. 内存读带宽测试
echo "内存读带宽测试 (10秒)..."
MEMORY_READ_OUTPUT=$(sysbench memory --memory-block-size=1M --memory-total-size=10G \
    --memory-oper=read --time=10 run)
MEMORY_READ_BANDWIDTH=$(echo "$MEMORY_READ_OUTPUT" | grep "transferred" | awk '{print $(NF-1)}')
MEMORY_READ_BANDWIDTH_UNIT=$(echo "$MEMORY_READ_OUTPUT" | grep "transferred" | awk '{print $NF}' | tr -d '()')

# 转换为 MB/s
if [ "$MEMORY_READ_BANDWIDTH_UNIT" = "GiB/sec" ]; then
    MEMORY_READ_BANDWIDTH_MBS=$(echo "$MEMORY_READ_BANDWIDTH * 1024" | bc)
elif [ "$MEMORY_READ_BANDWIDTH_UNIT" = "MiB/sec" ]; then
    MEMORY_READ_BANDWIDTH_MBS=$MEMORY_READ_BANDWIDTH
else
    MEMORY_READ_BANDWIDTH_MBS=$MEMORY_READ_BANDWIDTH
fi

echo "✓ 内存读带宽: $MEMORY_READ_BANDWIDTH_MBS MB/s"
echo ""

# 3. 随机内存访问测试
echo "随机内存访问测试 (10秒)..."
RANDOM_ACCESS_OUTPUT=$(sysbench memory --memory-block-size=4K --memory-total-size=1G \
    --memory-oper=read --memory-access-mode=rnd --time=10 run)
RANDOM_OPS=$(echo "$RANDOM_ACCESS_OUTPUT" | grep "total number of events" | awk '{print $NF}')
RANDOM_OPS_PER_SEC=$(echo "scale=2; $RANDOM_OPS / 10" | bc)
echo "✓ 随机访问: $RANDOM_OPS_PER_SEC ops/s"
echo ""

# 4. 内存分配延迟测试 (使用 Python)
echo "内存分配延迟测试..."
WORK_DIR="${HOME:-/home/user}"
cat > "${WORK_DIR}/memory_alloc_test.py" << 'PYEOF'
import time
import sys

# 测试大量内存分配和释放
iterations = 10000
sizes = [1024, 4096, 16384, 65536, 262144]  # 1KB, 4KB, 16KB, 64KB, 256KB

results = {}
for size in sizes:
    start = time.time()
    for _ in range(iterations):
        data = bytearray(size)
        del data
    elapsed = time.time() - start
    latency_us = (elapsed / iterations) * 1000000
    results[size] = latency_us

# 输出结果
for size, latency in results.items():
    print(f"{size},{latency:.3f}")
PYEOF

ALLOC_RESULTS=$(python3 "${WORK_DIR}/memory_alloc_test.py" 2>/dev/null)
rm -f "${WORK_DIR}/memory_alloc_test.py"

# 解析分配延迟结果
ALLOC_1KB=$(echo "$ALLOC_RESULTS" | grep "^1024," | cut -d',' -f2)
ALLOC_4KB=$(echo "$ALLOC_RESULTS" | grep "^4096," | cut -d',' -f2)
ALLOC_16KB=$(echo "$ALLOC_RESULTS" | grep "^16384," | cut -d',' -f2)
ALLOC_64KB=$(echo "$ALLOC_RESULTS" | grep "^65536," | cut -d',' -f2)
ALLOC_256KB=$(echo "$ALLOC_RESULTS" | grep "^262144," | cut -d',' -f2)

echo "✓ 内存分配延迟 (1KB): $ALLOC_1KB μs"
echo "✓ 内存分配延迟 (4KB): $ALLOC_4KB μs"
echo "✓ 内存分配延迟 (16KB): $ALLOC_16KB μs"
echo "✓ 内存分配延迟 (64KB): $ALLOC_64KB μs"
echo "✓ 内存分配延迟 (256KB): $ALLOC_256KB μs"
echo ""

# 5. 内存拷贝性能测试
echo "内存拷贝性能测试..."
cat > "${WORK_DIR}/memory_copy_test.py" << 'PYEOF'
import time

# 测试内存拷贝速度
size = 100 * 1024 * 1024  # 100MB
iterations = 50

start = time.time()
for _ in range(iterations):
    src = bytearray(size)
    dst = bytearray(src)
    del src, dst
elapsed = time.time() - start

total_mb = (size * iterations) / (1024 * 1024)
throughput = total_mb / elapsed
print(f"{throughput:.2f}")
PYEOF

COPY_THROUGHPUT=$(python3 "${WORK_DIR}/memory_copy_test.py" 2>/dev/null)
rm -f "${WORK_DIR}/memory_copy_test.py"

echo "✓ 内存拷贝吞吐量: $COPY_THROUGHPUT MB/s"
echo ""

# 生成 JSON 结果
cat > /tmp/sandbox_memory_result.json << EOF
{
  "memory_bandwidth": {
    "write_mbs": $MEMORY_BANDWIDTH_MBS,
    "read_mbs": $MEMORY_READ_BANDWIDTH_MBS,
    "random_access_ops_per_sec": $RANDOM_OPS_PER_SEC
  },
  "memory_allocation_latency_us": {
    "size_1kb": $ALLOC_1KB,
    "size_4kb": $ALLOC_4KB,
    "size_16kb": $ALLOC_16KB,
    "size_64kb": $ALLOC_64KB,
    "size_256kb": $ALLOC_256KB
  },
  "memory_copy_throughput_mbs": $COPY_THROUGHPUT,
  "test_date": "$(date -Iseconds)"
}
EOF

echo "=========================================="
echo "测试完成!"
echo "=========================================="
echo ""
echo "结果已保存到: /tmp/sandbox_memory_result.json"
echo ""
cat /tmp/sandbox_memory_result.json
echo ""
echo "请复制以上 JSON 内容保存到本地"
