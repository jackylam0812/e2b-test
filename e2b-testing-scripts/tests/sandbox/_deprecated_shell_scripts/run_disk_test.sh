#!/bin/bash
# 沙箱内磁盘 I/O 性能测试脚本
# 在沙箱内运行此脚本

echo "=========================================="
echo "沙箱内磁盘 I/O 性能测试"
echo "=========================================="
echo ""

# 清理函数 - 删除 fio 测试文件以节省磁盘空间
cleanup_fio_files() {
    rm -f randread.*.0 seqread.*.0 randwrite.*.0 seqwrite.*.0 readlat.*.0 writelat.*.0 2>/dev/null
    rm -f /tmp/fio_test_* 2>/dev/null
    rm -f $TEST_DIR/randread.*.0 $TEST_DIR/seqread.*.0 $TEST_DIR/randwrite.*.0 $TEST_DIR/seqwrite.*.0 2>/dev/null
}

# 安装 fio
echo "安装 fio..."
apt-get update -qq && apt-get install -y -qq fio
echo "✓ 安装完成"
echo ""

# 测试文件大小（减小以避免磁盘空间不足）
TEST_SIZE="50M"
SEQ_TEST_SIZE="100M"

# 选择测试目录：优先使用支持 O_DIRECT 的目录
# /tmp 可能是 tmpfs，不支持 O_DIRECT
if [ -d "/home" ] && touch /home/.fio_test 2>/dev/null; then
    TEST_DIR="/home"
    rm -f /home/.fio_test
elif [ -d "/var/tmp" ] && touch /var/tmp/.fio_test 2>/dev/null; then
    TEST_DIR="/var/tmp"
    rm -f /var/tmp/.fio_test
else
    TEST_DIR="/tmp"
fi

# 检测是否支持 O_DIRECT
DIRECT_FLAG="1"
echo "测试 O_DIRECT 支持..."
cd $TEST_DIR
fio --name=test_direct --ioengine=libaio --iodepth=1 --rw=read \
    --bs=4k --direct=1 --size=1M --numjobs=1 --runtime=1 \
    --group_reporting --output-format=json > /tmp/fio_test_direct.json 2>&1

if grep -q "does not support O_DIRECT\|does not support direct" /tmp/fio_test_direct.json 2>/dev/null || \
   grep -q '"error" : 22' /tmp/fio_test_direct.json 2>/dev/null; then
    echo "⚠ 文件系统不支持 O_DIRECT，将使用 buffered I/O 模式"
    echo "  注意：buffered I/O 结果会受到缓存影响，不代表真实磁盘性能"
    DIRECT_FLAG="0"
else
    echo "✓ 文件系统支持 O_DIRECT"
fi
cleanup_fio_files
echo "测试目录: $TEST_DIR"
echo ""

# 随机读 IOPS 测试
echo "随机读 IOPS 测试 (10秒)..."
fio --name=randread --ioengine=libaio --iodepth=1 --rw=randread \
    --bs=4k --direct=$DIRECT_FLAG --size=$TEST_SIZE --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json --directory=$TEST_DIR > /tmp/fio_randread.json 2>&1

RAND_READ_IOPS=$(cat /tmp/fio_randread.json | python3 -c "import sys, json; print(json.load(sys.stdin)['jobs'][0]['read']['iops'])" 2>/dev/null || echo "0")
echo "✓ 随机读 IOPS: $RAND_READ_IOPS"
cleanup_fio_files
echo ""

# 顺序读吞吐量测试
echo "顺序读吞吐量测试 (10秒)..."
fio --name=seqread --ioengine=libaio --iodepth=16 --rw=read \
    --bs=1m --direct=$DIRECT_FLAG --size=$SEQ_TEST_SIZE --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json --directory=$TEST_DIR > /tmp/fio_seqread.json 2>&1

SEQ_READ_BW=$(cat /tmp/fio_seqread.json | python3 -c "import sys, json; print(json.load(sys.stdin)['jobs'][0]['read']['bw'] / 1024)" 2>/dev/null || echo "0")
echo "✓ 顺序读吞吐量: $SEQ_READ_BW MB/s"
cleanup_fio_files
echo ""

# 随机写 IOPS 测试
echo "随机写 IOPS 测试 (10秒)..."
fio --name=randwrite --ioengine=libaio --iodepth=1 --rw=randwrite \
    --bs=4k --direct=$DIRECT_FLAG --size=$TEST_SIZE --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json --directory=$TEST_DIR > /tmp/fio_randwrite.json 2>&1

RAND_WRITE_IOPS=$(cat /tmp/fio_randwrite.json | python3 -c "import sys, json; print(json.load(sys.stdin)['jobs'][0]['write']['iops'])" 2>/dev/null || echo "0")
echo "✓ 随机写 IOPS: $RAND_WRITE_IOPS"
cleanup_fio_files
echo ""

# 顺序写吞吐量测试
echo "顺序写吞吐量测试 (10秒)..."
fio --name=seqwrite --ioengine=libaio --iodepth=16 --rw=write \
    --bs=1m --direct=$DIRECT_FLAG --size=$SEQ_TEST_SIZE --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json --directory=$TEST_DIR > /tmp/fio_seqwrite.json 2>&1

SEQ_WRITE_BW=$(cat /tmp/fio_seqwrite.json | python3 -c "import sys, json; print(json.load(sys.stdin)['jobs'][0]['write']['bw'] / 1024)" 2>/dev/null || echo "0")
echo "✓ 顺序写吞吐量: $SEQ_WRITE_BW MB/s"
cleanup_fio_files
echo ""

# 读延迟测试 (带延迟分位数)
echo "读延迟测试 (10秒)..."
fio --name=readlat --ioengine=libaio --iodepth=1 --rw=randread \
    --bs=4k --direct=$DIRECT_FLAG --size=$TEST_SIZE --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json --lat_percentiles=1 --directory=$TEST_DIR > /tmp/fio_readlat.json 2>&1

READ_LAT_P50=$(cat /tmp/fio_readlat.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['jobs'][0]['read']['clat_ns']['percentile'].get('50.000000', 0) / 1000)" 2>/dev/null || echo "0")
READ_LAT_P95=$(cat /tmp/fio_readlat.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['jobs'][0]['read']['clat_ns']['percentile'].get('95.000000', 0) / 1000)" 2>/dev/null || echo "0")
READ_LAT_P99=$(cat /tmp/fio_readlat.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['jobs'][0]['read']['clat_ns']['percentile'].get('99.000000', 0) / 1000)" 2>/dev/null || echo "0")
echo "✓ 读延迟 P50: $READ_LAT_P50 μs"
echo "✓ 读延迟 P95: $READ_LAT_P95 μs"
echo "✓ 读延迟 P99: $READ_LAT_P99 μs"
cleanup_fio_files
echo ""

# 写延迟测试 (带延迟分位数)
echo "写延迟测试 (10秒)..."
fio --name=writelat --ioengine=libaio --iodepth=1 --rw=randwrite \
    --bs=4k --direct=$DIRECT_FLAG --size=$TEST_SIZE --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json --lat_percentiles=1 --directory=$TEST_DIR > /tmp/fio_writelat.json 2>&1

WRITE_LAT_P50=$(cat /tmp/fio_writelat.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['jobs'][0]['write']['clat_ns']['percentile'].get('50.000000', 0) / 1000)" 2>/dev/null || echo "0")
WRITE_LAT_P95=$(cat /tmp/fio_writelat.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['jobs'][0]['write']['clat_ns']['percentile'].get('95.000000', 0) / 1000)" 2>/dev/null || echo "0")
WRITE_LAT_P99=$(cat /tmp/fio_writelat.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['jobs'][0]['write']['clat_ns']['percentile'].get('99.000000', 0) / 1000)" 2>/dev/null || echo "0")
echo "✓ 写延迟 P50: $WRITE_LAT_P50 μs"
echo "✓ 写延迟 P95: $WRITE_LAT_P95 μs"
echo "✓ 写延迟 P99: $WRITE_LAT_P99 μs"
cleanup_fio_files
echo ""

# 生成 JSON 结果
cat > /tmp/sandbox_disk_result.json << EOF
{
  "random_read_iops": $RAND_READ_IOPS,
  "random_write_iops": $RAND_WRITE_IOPS,
  "sequential_read_throughput_mbs": $SEQ_READ_BW,
  "sequential_write_throughput_mbs": $SEQ_WRITE_BW,
  "read_latency_us": {
    "p50": $READ_LAT_P50,
    "p95": $READ_LAT_P95,
    "p99": $READ_LAT_P99
  },
  "write_latency_us": {
    "p50": $WRITE_LAT_P50,
    "p95": $WRITE_LAT_P95,
    "p99": $WRITE_LAT_P99
  },
  "test_date": "$(date -Iseconds)"
}
EOF

echo "=========================================="
echo "测试完成!"
echo "=========================================="
echo ""
echo "结果已保存到: /tmp/sandbox_disk_result.json"
echo ""
cat /tmp/sandbox_disk_result.json
echo ""
echo "请复制以上 JSON 内容保存到本地"
