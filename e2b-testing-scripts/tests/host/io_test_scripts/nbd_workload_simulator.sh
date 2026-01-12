#!/bin/bash

# 模拟 NBD 工作负载的测试脚本
# 模拟多个沙箱并发运行时的 I/O 模式

set -e

TEST_DIR="${1:-/orchestrator/sandbox}"
NUM_SANDBOXES="${2:-38}"
DURATION="${3:-300}"  # 5 分钟

echo "======================================="
echo "NBD 工作负载模拟器"
echo "======================================="
echo "测试目录: $TEST_DIR"
echo "模拟沙箱数: $NUM_SANDBOXES"
echo "运行时长: ${DURATION}s"
echo "======================================="
echo ""

# 检查 fio 是否安装
if ! command -v fio &> /dev/null; then
    echo "正在安装 fio..."
    sudo apt update && sudo apt install -y fio
fi

# 创建测试目录
WORKLOAD_DIR="$TEST_DIR/nbd_workload_test"
mkdir -p "$WORKLOAD_DIR"

# 创建 fio 配置文件
FIO_CONFIG="$WORKLOAD_DIR/nbd_workload.fio"

cat > "$FIO_CONFIG" << EOF
[global]
ioengine=libaio
direct=1
time_based=1
runtime=$DURATION
group_reporting=1
directory=$WORKLOAD_DIR

# 模拟文件系统元数据操作（小块随机写入）
[metadata_ops]
bs=4k
rw=randwrite
iodepth=4
numjobs=$NUM_SANDBOXES
size=100M
stonewall

# 模拟代码执行（随机读取）
[code_execution]
bs=64k
rw=randread
iodepth=8
numjobs=$NUM_SANDBOXES
size=500M
stonewall

# 模拟日志写入（顺序写入）
[log_writing]
bs=16k
rw=write
iodepth=2
numjobs=$NUM_SANDBOXES
size=200M
stonewall

# 模拟混合工作负载
[mixed_workload]
bs=4k-64k
rw=randrw
rwmixread=60
iodepth=16
numjobs=$NUM_SANDBOXES
size=300M
EOF

echo "FIO 配置文件已创建: $FIO_CONFIG"
echo ""
echo "开始模拟 NBD 工作负载..."
echo "这将模拟 $NUM_SANDBOXES 个沙箱同时运行的 I/O 模式。"
echo ""

# 启动后台监控
MONITOR_PID=""
if [ -f "/home/ubuntu/io_test_scripts/realtime_io_monitor.sh" ]; then
    echo "启动实时监控..."
    bash /home/ubuntu/io_test_scripts/realtime_io_monitor.sh nvme1n1 $((DURATION + 10)) 5 > "$WORKLOAD_DIR/monitor.log" 2>&1 &
    MONITOR_PID=$!
    sleep 5
fi

# 运行 fio 测试
START_TIME=$(date +%s)
fio "$FIO_CONFIG" --output="$WORKLOAD_DIR/fio_results.json" --output-format=json

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# 等待监控完成
if [ -n "$MONITOR_PID" ]; then
    wait $MONITOR_PID
fi

echo ""
echo "======================================="
echo "测试完成！"
echo "======================================="
echo "实际运行时间: ${ELAPSED}s"
echo ""

# 生成汇总报告
REPORT_FILE="$WORKLOAD_DIR/summary_report.txt"

cat > "$REPORT_FILE" << EOF
======================================
NBD 工作负载模拟测试报告
======================================
测试目录: $TEST_DIR
模拟沙箱数: $NUM_SANDBOXES
运行时长: ${DURATION}s
实际运行时间: ${ELAPSED}s
时间: $(date)
======================================

EOF

# 解析 fio 结果
if [ -f "$WORKLOAD_DIR/fio_results.json" ]; then
    echo "--- 元数据操作（4K 随机写）---" >> "$REPORT_FILE"
    # 使用 group_reporting=1 后,只有一个汇总的 job 条目,直接提取
    METADATA_IOPS=$(jq -r '[.jobs[] | select(.jobname=="metadata_ops") | .write.iops] | add // 0' "$WORKLOAD_DIR/fio_results.json" 2>/dev/null)
    METADATA_LAT=$(jq -r '[.jobs[] | select(.jobname=="metadata_ops") | .write.lat_ns.mean] | add // 0' "$WORKLOAD_DIR/fio_results.json" 2>/dev/null)
    echo "  总 IOPS: $(printf "%.2f" $METADATA_IOPS)" >> "$REPORT_FILE"
    echo "  平均延迟: $(printf "%.2f" $METADATA_LAT) ns" >> "$REPORT_FILE"
    if [ "$METADATA_IOPS" != "0" ] && [ "$METADATA_IOPS" != "0.00" ]; then
        echo "  每个沙箱 IOPS: $(echo "scale=2; $METADATA_IOPS / $NUM_SANDBOXES" | bc)" >> "$REPORT_FILE"
    fi
    echo "" >> "$REPORT_FILE"

    echo "--- 代码执行（64K 随机读）---" >> "$REPORT_FILE"
    CODE_IOPS=$(jq -r '[.jobs[] | select(.jobname=="code_execution") | .read.iops] | add // 0' "$WORKLOAD_DIR/fio_results.json" 2>/dev/null)
    CODE_BW=$(jq -r '[.jobs[] | select(.jobname=="code_execution") | .read.bw] | add // 0' "$WORKLOAD_DIR/fio_results.json" 2>/dev/null)
    echo "  总 IOPS: $(printf "%.2f" $CODE_IOPS)" >> "$REPORT_FILE"
    echo "  总带宽: $(printf "%.0f" $CODE_BW) KB/s ($(echo "scale=2; $CODE_BW / 1024" | bc) MB/s)" >> "$REPORT_FILE"
    if [ "$CODE_IOPS" != "0" ] && [ "$CODE_IOPS" != "0.00" ]; then
        echo "  每个沙箱 IOPS: $(echo "scale=2; $CODE_IOPS / $NUM_SANDBOXES" | bc)" >> "$REPORT_FILE"
    fi
    echo "" >> "$REPORT_FILE"

    echo "--- 日志写入（16K 顺序写）---" >> "$REPORT_FILE"
    LOG_IOPS=$(jq -r '[.jobs[] | select(.jobname=="log_writing") | .write.iops] | add // 0' "$WORKLOAD_DIR/fio_results.json" 2>/dev/null)
    LOG_BW=$(jq -r '[.jobs[] | select(.jobname=="log_writing") | .write.bw] | add // 0' "$WORKLOAD_DIR/fio_results.json" 2>/dev/null)
    echo "  总 IOPS: $(printf "%.2f" $LOG_IOPS)" >> "$REPORT_FILE"
    echo "  总带宽: $(printf "%.0f" $LOG_BW) KB/s ($(echo "scale=2; $LOG_BW / 1024" | bc) MB/s)" >> "$REPORT_FILE"
    if [ "$LOG_IOPS" != "0" ] && [ "$LOG_IOPS" != "0.00" ]; then
        echo "  每个沙箱 IOPS: $(echo "scale=2; $LOG_IOPS / $NUM_SANDBOXES" | bc)" >> "$REPORT_FILE"
    fi
    echo "" >> "$REPORT_FILE"

    echo "--- 混合工作负载 ---" >> "$REPORT_FILE"
    MIXED_READ_IOPS=$(jq -r '[.jobs[] | select(.jobname=="mixed_workload") | .read.iops] | add // 0' "$WORKLOAD_DIR/fio_results.json" 2>/dev/null)
    MIXED_WRITE_IOPS=$(jq -r '[.jobs[] | select(.jobname=="mixed_workload") | .write.iops] | add // 0' "$WORKLOAD_DIR/fio_results.json" 2>/dev/null)
    MIXED_TOTAL=$(echo "$MIXED_READ_IOPS + $MIXED_WRITE_IOPS" | bc)
    echo "  读 IOPS: $(printf "%.2f" $MIXED_READ_IOPS)" >> "$REPORT_FILE"
    echo "  写 IOPS: $(printf "%.2f" $MIXED_WRITE_IOPS)" >> "$REPORT_FILE"
    echo "  总 IOPS: $(printf "%.2f" $MIXED_TOTAL)" >> "$REPORT_FILE"
    if [ "$MIXED_READ_IOPS" != "0" ] && [ "$MIXED_READ_IOPS" != "0.00" ]; then
        echo "  每个沙箱读 IOPS: $(echo "scale=2; $MIXED_READ_IOPS / $NUM_SANDBOXES" | bc)" >> "$REPORT_FILE"
        echo "  每个沙箱写 IOPS: $(echo "scale=2; $MIXED_WRITE_IOPS / $NUM_SANDBOXES" | bc)" >> "$REPORT_FILE"
    fi
    echo "" >> "$REPORT_FILE"
fi

# 性能评估
echo "--- 性能评估 ---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 计算总 IOPS 需求
if [ -n "$METADATA_IOPS" ] && [ -n "$CODE_IOPS" ] && [ -n "$LOG_IOPS" ] && [ -n "$MIXED_READ_IOPS" ] && [ -n "$MIXED_WRITE_IOPS" ]; then
    TOTAL_IOPS=$(echo "$METADATA_IOPS + $CODE_IOPS + $LOG_IOPS + $MIXED_READ_IOPS + $MIXED_WRITE_IOPS" | bc 2>/dev/null || echo "0")
else
    TOTAL_IOPS=0
fi

echo "估算的总 IOPS 需求: $(printf "%.2f" $TOTAL_IOPS)" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 详细 IOPS 分解
echo "IOPS 分解:" >> "$REPORT_FILE"
echo "  - 元数据操作 (4K 随机写): $(printf "%.2f" ${METADATA_IOPS:-0}) IOPS" >> "$REPORT_FILE"
echo "  - 代码执行 (64K 随机读): $(printf "%.2f" ${CODE_IOPS:-0}) IOPS" >> "$REPORT_FILE"
echo "  - 日志写入 (16K 顺序写): $(printf "%.2f" ${LOG_IOPS:-0}) IOPS" >> "$REPORT_FILE"
echo "  - 混合负载 (读): $(printf "%.2f" ${MIXED_READ_IOPS:-0}) IOPS" >> "$REPORT_FILE"
echo "  - 混合负载 (写): $(printf "%.2f" ${MIXED_WRITE_IOPS:-0}) IOPS" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 给出建议
TOTAL_IOPS_INT=$(printf "%.0f" $TOTAL_IOPS)
if [ "$TOTAL_IOPS_INT" -gt 10000 ]; then
    echo "[建议] 您的工作负载需要 > 10,000 IOPS。" >> "$REPORT_FILE"
    echo "推荐配置: gp3 with 16,000 IOPS 或 io2。" >> "$REPORT_FILE"
elif [ "$TOTAL_IOPS_INT" -gt 6000 ]; then
    echo "[建议] 您的工作负载需要 6,000-10,000 IOPS。" >> "$REPORT_FILE"
    echo "推荐配置: gp3 with 10,000 IOPS。" >> "$REPORT_FILE"
elif [ "$TOTAL_IOPS_INT" -gt 3000 ]; then
    echo "[建议] 您的工作负载需要 3,000-6,000 IOPS。" >> "$REPORT_FILE"
    echo "推荐配置: gp3 with 6,000 IOPS 或 gp2 (2TB+)。" >> "$REPORT_FILE"
else
    echo "[建议] 您的工作负载需求较低 (< 3,000 IOPS)。" >> "$REPORT_FILE"
    echo "推荐配置: gp3 (默认 3,000 IOPS) 即可。" >> "$REPORT_FILE"
fi

# 显示报告
cat "$REPORT_FILE"

echo ""
echo "详细结果保存在: $WORKLOAD_DIR"
echo "  - fio_results.json: FIO 详细输出"
echo "  - monitor.log: 实时监控日志"
echo "  - summary_report.txt: 汇总报告"
echo ""

# 清理测试文件
echo "清理测试文件..."
rm -rf "$WORKLOAD_DIR"/*.0.*

echo "完成！"
