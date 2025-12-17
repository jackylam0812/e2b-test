#!/bin/bash
# 沙箱内磁盘 I/O 性能测试脚本
# 在沙箱内运行此脚本

echo "=========================================="
echo "沙箱内磁盘 I/O 性能测试"
echo "=========================================="
echo ""

# 安装 fio
echo "安装 fio..."
apt-get update -qq && apt-get install -y -qq fio
echo "✓ 安装完成"
echo ""

# 随机读 IOPS 测试
echo "随机读 IOPS 测试 (10秒)..."
fio --name=randread --ioengine=libaio --iodepth=1 --rw=randread \
    --bs=4k --direct=1 --size=100M --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json > /tmp/fio_randread.json

RAND_READ_IOPS=$(cat /tmp/fio_randread.json | python3 -c "import sys, json; print(json.load(sys.stdin)['jobs'][0]['read']['iops'])")
echo "✓ 随机读 IOPS: $RAND_READ_IOPS"
echo ""

# 顺序读吞吐量测试
echo "顺序读吞吐量测试 (10秒)..."
fio --name=seqread --ioengine=libaio --iodepth=16 --rw=read \
    --bs=1m --direct=1 --size=200M --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json > /tmp/fio_seqread.json

SEQ_READ_BW=$(cat /tmp/fio_seqread.json | python3 -c "import sys, json; print(json.load(sys.stdin)['jobs'][0]['read']['bw'] / 1024)")
echo "✓ 顺序读吞吐量: $SEQ_READ_BW MB/s"
echo ""

# 随机写 IOPS 测试
echo "随机写 IOPS 测试 (10秒)..."
fio --name=randwrite --ioengine=libaio --iodepth=1 --rw=randwrite \
    --bs=4k --direct=1 --size=100M --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json > /tmp/fio_randwrite.json

RAND_WRITE_IOPS=$(cat /tmp/fio_randwrite.json | python3 -c "import sys, json; print(json.load(sys.stdin)['jobs'][0]['write']['iops'])")
echo "✓ 随机写 IOPS: $RAND_WRITE_IOPS"
echo ""

# 顺序写吞吐量测试
echo "顺序写吞吐量测试 (10秒)..."
fio --name=seqwrite --ioengine=libaio --iodepth=16 --rw=write \
    --bs=1m --direct=1 --size=200M --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json > /tmp/fio_seqwrite.json

SEQ_WRITE_BW=$(cat /tmp/fio_seqwrite.json | python3 -c "import sys, json; print(json.load(sys.stdin)['jobs'][0]['write']['bw'] / 1024)")
echo "✓ 顺序写吞吐量: $SEQ_WRITE_BW MB/s"
echo ""

# 读延迟测试 (带延迟分位数)
echo "读延迟测试 (10秒)..."
fio --name=readlat --ioengine=libaio --iodepth=1 --rw=randread \
    --bs=4k --direct=1 --size=100M --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json --lat_percentiles=1 > /tmp/fio_readlat.json

READ_LAT_P50=$(cat /tmp/fio_readlat.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['jobs'][0]['read']['clat_ns']['percentile'].get('50.000000', 0) / 1000)")
READ_LAT_P95=$(cat /tmp/fio_readlat.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['jobs'][0]['read']['clat_ns']['percentile'].get('95.000000', 0) / 1000)")
READ_LAT_P99=$(cat /tmp/fio_readlat.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['jobs'][0]['read']['clat_ns']['percentile'].get('99.000000', 0) / 1000)")
echo "✓ 读延迟 P50: $READ_LAT_P50 μs"
echo "✓ 读延迟 P95: $READ_LAT_P95 μs"
echo "✓ 读延迟 P99: $READ_LAT_P99 μs"
echo ""

# 写延迟测试 (带延迟分位数)
echo "写延迟测试 (10秒)..."
fio --name=writelat --ioengine=libaio --iodepth=1 --rw=randwrite \
    --bs=4k --direct=1 --size=100M --numjobs=1 --runtime=10 --time_based \
    --group_reporting --output-format=json --lat_percentiles=1 > /tmp/fio_writelat.json

WRITE_LAT_P50=$(cat /tmp/fio_writelat.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['jobs'][0]['write']['clat_ns']['percentile'].get('50.000000', 0) / 1000)")
WRITE_LAT_P95=$(cat /tmp/fio_writelat.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['jobs'][0]['write']['clat_ns']['percentile'].get('95.000000', 0) / 1000)")
WRITE_LAT_P99=$(cat /tmp/fio_writelat.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['jobs'][0]['write']['clat_ns']['percentile'].get('99.000000', 0) / 1000)")
echo "✓ 写延迟 P50: $WRITE_LAT_P50 μs"
echo "✓ 写延迟 P95: $WRITE_LAT_P95 μs"
echo "✓ 写延迟 P99: $WRITE_LAT_P99 μs"
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
