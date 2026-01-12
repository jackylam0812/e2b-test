#!/bin/bash

# 使用 fio 进行综合 I/O 性能测试
# fio 是业界标准的 I/O 性能测试工具

set -e

# 配置
TEST_DIR="${1:-/orchestrator/sandbox}"
TEST_SIZE="1G"
RUNTIME="60"  # 每个测试运行 60 秒
OUTPUT_DIR="/tmp/fio_results"

# 检查 fio 是否安装
if ! command -v fio &> /dev/null; then
    echo "错误: fio 未安装。正在安装..."
    sudo apt update && sudo apt install -y fio
fi

# 创建输出目录
mkdir -p "$OUTPUT_DIR"

echo "======================================="
echo "FIO 综合 I/O 性能测试"
echo "======================================="
echo "测试目录: $TEST_DIR"
echo "测试大小: $TEST_SIZE"
echo "运行时间: ${RUNTIME}s/测试"
echo "输出目录: $OUTPUT_DIR"
echo "======================================="

cd "$TEST_DIR"

# 测试 1: 顺序读
echo ""
echo "[1/8] 顺序读测试 (Sequential Read)..."
fio --name=seq-read \
    --ioengine=libaio \
    --direct=1 \
    --bs=1M \
    --iodepth=32 \
    --size=$TEST_SIZE \
    --rw=read \
    --runtime=$RUNTIME \
    --time_based \
    --group_reporting \
    --output="$OUTPUT_DIR/seq-read.json" \
    --output-format=json

# 测试 2: 顺序写
echo ""
echo "[2/8] 顺序写测试 (Sequential Write)..."
fio --name=seq-write \
    --ioengine=libaio \
    --direct=1 \
    --bs=1M \
    --iodepth=32 \
    --size=$TEST_SIZE \
    --rw=write \
    --runtime=$RUNTIME \
    --time_based \
    --group_reporting \
    --output="$OUTPUT_DIR/seq-write.json" \
    --output-format=json

# 测试 3: 4K 随机读
echo ""
echo "[3/8] 4K 随机读测试 (4K Random Read)..."
fio --name=rand-read-4k \
    --ioengine=libaio \
    --direct=1 \
    --bs=4K \
    --iodepth=64 \
    --size=$TEST_SIZE \
    --rw=randread \
    --runtime=$RUNTIME \
    --time_based \
    --group_reporting \
    --output="$OUTPUT_DIR/rand-read-4k.json" \
    --output-format=json

# 测试 4: 4K 随机写（关键测试）
echo ""
echo "[4/8] 4K 随机写测试 (4K Random Write) - 关键测试！"
fio --name=rand-write-4k \
    --ioengine=libaio \
    --direct=1 \
    --bs=4K \
    --iodepth=64 \
    --size=$TEST_SIZE \
    --rw=randwrite \
    --runtime=$RUNTIME \
    --time_based \
    --group_reporting \
    --output="$OUTPUT_DIR/rand-write-4k.json" \
    --output-format=json

# 测试 5: 混合随机读写 (70% 读, 30% 写)
echo ""
echo "[5/8] 混合随机读写测试 (Mixed Random R/W 70/30)..."
fio --name=mixed-rw \
    --ioengine=libaio \
    --direct=1 \
    --bs=4K \
    --iodepth=64 \
    --size=$TEST_SIZE \
    --rw=randrw \
    --rwmixread=70 \
    --runtime=$RUNTIME \
    --time_based \
    --group_reporting \
    --output="$OUTPUT_DIR/mixed-rw.json" \
    --output-format=json

# 测试 6: 延迟测试 (单队列深度)
echo ""
echo "[6/8] 延迟测试 (Latency Test, QD=1)..."
fio --name=latency-test \
    --ioengine=libaio \
    --direct=1 \
    --bs=4K \
    --iodepth=1 \
    --size=$TEST_SIZE \
    --rw=randwrite \
    --runtime=$RUNTIME \
    --time_based \
    --group_reporting \
    --output="$OUTPUT_DIR/latency-test.json" \
    --output-format=json

# 测试 7: 高队列深度测试
echo ""
echo "[7/8] 高队列深度测试 (High Queue Depth, QD=256)..."
fio --name=high-qd \
    --ioengine=libaio \
    --direct=1 \
    --bs=4K \
    --iodepth=256 \
    --size=$TEST_SIZE \
    --rw=randwrite \
    --runtime=$RUNTIME \
    --time_based \
    --group_reporting \
    --output="$OUTPUT_DIR/high-qd.json" \
    --output-format=json

# 测试 8: fsync 测试
echo ""
echo "[8/8] fsync 性能测试..."
fio --name=fsync-test \
    --ioengine=sync \
    --direct=0 \
    --bs=4K \
    --size=100M \
    --rw=write \
    --fsync=1 \
    --group_reporting \
    --output="$OUTPUT_DIR/fsync-test.json" \
    --output-format=json

# 生成汇总报告
echo ""
echo "======================================="
echo "测试完成！正在生成汇总报告..."
echo "======================================="

REPORT_FILE="$OUTPUT_DIR/summary_report.txt"

cat > "$REPORT_FILE" << 'EOF'
======================================
FIO I/O 性能测试汇总报告
======================================

EOF

# 解析 JSON 结果
for test in seq-read seq-write rand-read-4k rand-write-4k mixed-rw latency-test high-qd fsync-test; do
    json_file="$OUTPUT_DIR/${test}.json"
    if [ -f "$json_file" ]; then
        echo "--- $test ---" >> "$REPORT_FILE"
        
        # 提取关键指标
        if [ "$test" = "fsync-test" ]; then
            # fsync 测试的指标不同
            iops=$(jq -r '.jobs[0].write.iops' "$json_file" 2>/dev/null || echo "N/A")
            bw=$(jq -r '.jobs[0].write.bw' "$json_file" 2>/dev/null || echo "N/A")
            lat_avg=$(jq -r '.jobs[0].write.lat_ns.mean' "$json_file" 2>/dev/null || echo "N/A")
            
            echo "  IOPS: $iops" >> "$REPORT_FILE"
            echo "  带宽: $bw KB/s" >> "$REPORT_FILE"
            echo "  平均延迟: $lat_avg ns" >> "$REPORT_FILE"
        else
            # 读写测试
            read_iops=$(jq -r '.jobs[0].read.iops' "$json_file" 2>/dev/null || echo "0")
            write_iops=$(jq -r '.jobs[0].write.iops' "$json_file" 2>/dev/null || echo "0")
            read_bw=$(jq -r '.jobs[0].read.bw' "$json_file" 2>/dev/null || echo "0")
            write_bw=$(jq -r '.jobs[0].write.bw' "$json_file" 2>/dev/null || echo "0")
            read_lat=$(jq -r '.jobs[0].read.lat_ns.mean' "$json_file" 2>/dev/null || echo "0")
            write_lat=$(jq -r '.jobs[0].write.lat_ns.mean' "$json_file" 2>/dev/null || echo "0")
            
            if [ "$read_iops" != "0" ] && [ "$read_iops" != "null" ]; then
                echo "  读 IOPS: $read_iops" >> "$REPORT_FILE"
                echo "  读带宽: $read_bw KB/s" >> "$REPORT_FILE"
                echo "  读延迟: $read_lat ns" >> "$REPORT_FILE"
            fi
            
            if [ "$write_iops" != "0" ] && [ "$write_iops" != "null" ]; then
                echo "  写 IOPS: $write_iops" >> "$REPORT_FILE"
                echo "  写带宽: $write_bw KB/s" >> "$REPORT_FILE"
                echo "  写延迟: $write_lat ns" >> "$REPORT_FILE"
            fi
        fi
        
        echo "" >> "$REPORT_FILE"
    fi
done

# 添加性能基准对比
cat >> "$REPORT_FILE" << 'EOF'
======================================
性能基准对比 (AWS EBS)
======================================

gp2 (3000-16000 IOPS):
  - 4K 随机写 IOPS: 3000-16000
  - 延迟: 1-3 ms

gp3 (3000 基准, 最高 16000):
  - 4K 随机写 IOPS: 3000-16000
  - 延迟: 1-3 ms

io2 (最高 256000 IOPS):
  - 4K 随机写 IOPS: 可配置
  - 延迟: < 1 ms

本地 NVMe SSD:
  - 4K 随机写 IOPS: 100000+
  - 延迟: < 0.1 ms

======================================
EOF

# 显示汇总报告
cat "$REPORT_FILE"

echo ""
echo "详细结果已保存到: $OUTPUT_DIR"
echo "汇总报告: $REPORT_FILE"
echo ""
echo "关键指标："
echo "  - 4K 随机写 IOPS: $(jq -r '.jobs[0].write.iops' "$OUTPUT_DIR/rand-write-4k.json" 2>/dev/null || echo "N/A")"
echo "  - 4K 随机写延迟: $(jq -r '.jobs[0].write.lat_ns.mean' "$OUTPUT_DIR/rand-write-4k.json" 2>/dev/null || echo "N/A") ns"
