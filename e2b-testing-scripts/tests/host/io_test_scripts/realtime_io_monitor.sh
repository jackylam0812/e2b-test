#!/bin/bash

# 实时 I/O 监控脚本
# 监控磁盘 I/O 性能指标

DEVICE="${1:-nvme1n1}"
DURATION="${2:-60}"
INTERVAL="${3:-1}"

echo "======================================="
echo "实时 I/O 监控"
echo "======================================="
echo "设备: $DEVICE"
echo "监控时长: ${DURATION}s"
echo "采样间隔: ${INTERVAL}s"
echo "======================================="
echo ""

# 检查必要的工具
if ! command -v iostat &> /dev/null; then
    echo "错误: iostat 未安装。正在安装 sysstat..."
    sudo apt update && sudo apt install -y sysstat
fi

# 创建输出文件
OUTPUT_DIR="/tmp/io_monitor_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

echo "输出目录: $OUTPUT_DIR"
echo ""

# 启动后台监控任务

# 1. iostat 监控
echo "启动 iostat 监控..."
iostat -x $DEVICE $INTERVAL $DURATION > "$OUTPUT_DIR/iostat.log" &
IOSTAT_PID=$!

# 2. 监控 /proc/diskstats
echo "启动 diskstats 监控..."
(
    for i in $(seq 1 $DURATION); do
        echo "=== $(date +%Y-%m-%d\ %H:%M:%S) ===" >> "$OUTPUT_DIR/diskstats.log"
        grep $DEVICE /proc/diskstats >> "$OUTPUT_DIR/diskstats.log"
        sleep $INTERVAL
    done
) &
DISKSTATS_PID=$!

# 3. 监控 I/O 队列长度
echo "启动队列长度监控..."
(
    for i in $(seq 1 $DURATION); do
        echo "$(date +%Y-%m-%d\ %H:%M:%S),$(cat /sys/block/$DEVICE/inflight 2>/dev/null || echo "N/A")" >> "$OUTPUT_DIR/queue_length.csv"
        sleep $INTERVAL
    done
) &
QUEUE_PID=$!

# 4. 监控 I/O 超时设置
echo "启动超时设置监控..."
(
    for i in $(seq 1 $DURATION); do
        echo "$(date +%Y-%m-%d\ %H:%M:%S),$(cat /sys/block/$DEVICE/queue/io_timeout 2>/dev/null || echo "N/A")" >> "$OUTPUT_DIR/io_timeout.csv"
        sleep $INTERVAL
    done
) &
TIMEOUT_PID=$!

# 5. 监控 dmesg 中的 I/O 错误
echo "启动 dmesg 错误监控..."
INITIAL_ERRORS=$(dmesg | grep -i "i/o error\|$DEVICE.*error" | wc -l)
(
    sleep $DURATION
    FINAL_ERRORS=$(dmesg | grep -i "i/o error\|$DEVICE.*error" | wc -l)
    NEW_ERRORS=$((FINAL_ERRORS - INITIAL_ERRORS))
    echo "新增 I/O 错误: $NEW_ERRORS" > "$OUTPUT_DIR/error_count.txt"
    if [ $NEW_ERRORS -gt 0 ]; then
        dmesg | grep -i "i/o error\|$DEVICE.*error" | tail -$NEW_ERRORS > "$OUTPUT_DIR/new_errors.log"
    fi
) &
ERROR_PID=$!

# 实时显示关键指标
echo ""
echo "正在监控... (Ctrl+C 提前结束)"
echo ""
printf "%-20s %10s %10s %10s %10s %10s\n" "时间" "r/s" "w/s" "rMB/s" "wMB/s" "await(ms)"
echo "--------------------------------------------------------------------------------"

for i in $(seq 1 $DURATION); do
    # 读取 iostat 的最新输出
    STATS=$(iostat -x $DEVICE 1 2 | tail -1)
    
    if [ -n "$STATS" ]; then
        TIMESTAMP=$(date +%H:%M:%S)
        RS=$(echo $STATS | awk '{print $4}')
        WS=$(echo $STATS | awk '{print $5}')
        RMB=$(echo $STATS | awk '{printf "%.2f", $6/1024}')
        WMB=$(echo $STATS | awk '{printf "%.2f", $7/1024}')
        AWAIT=$(echo $STATS | awk '{print $10}')
        
        printf "%-20s %10s %10s %10s %10s %10s\n" "$TIMESTAMP" "$RS" "$WS" "$RMB" "$WMB" "$AWAIT"
    fi
    
    sleep $INTERVAL
done

# 等待所有后台任务完成
wait $IOSTAT_PID $DISKSTATS_PID $QUEUE_PID $TIMEOUT_PID $ERROR_PID

# 生成汇总报告
echo ""
echo "======================================="
echo "生成汇总报告..."
echo "======================================="

REPORT_FILE="$OUTPUT_DIR/summary_report.txt"

cat > "$REPORT_FILE" << EOF
======================================
I/O 监控汇总报告
======================================
设备: $DEVICE
监控时长: ${DURATION}s
采样间隔: ${INTERVAL}s
时间: $(date)
======================================

EOF

# 分析 iostat 结果
echo "--- iostat 统计 ---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 计算平均值
AVG_RS=$(awk '/^'$DEVICE'/ {sum+=$4; count++} END {if(count>0) print sum/count; else print 0}' "$OUTPUT_DIR/iostat.log")
AVG_WS=$(awk '/^'$DEVICE'/ {sum+=$5; count++} END {if(count>0) print sum/count; else print 0}' "$OUTPUT_DIR/iostat.log")
AVG_AWAIT=$(awk '/^'$DEVICE'/ {sum+=$10; count++} END {if(count>0) print sum/count; else print 0}' "$OUTPUT_DIR/iostat.log")
MAX_AWAIT=$(awk '/^'$DEVICE'/ {if($10>max) max=$10} END {print max}' "$OUTPUT_DIR/iostat.log")
AVG_UTIL=$(awk '/^'$DEVICE'/ {sum+=$14; count++} END {if(count>0) print sum/count; else print 0}' "$OUTPUT_DIR/iostat.log")

echo "平均读 IOPS: $AVG_RS" >> "$REPORT_FILE"
echo "平均写 IOPS: $AVG_WS" >> "$REPORT_FILE"
echo "平均等待时间: $AVG_AWAIT ms" >> "$REPORT_FILE"
echo "最大等待时间: $MAX_AWAIT ms" >> "$REPORT_FILE"
echo "平均磁盘利用率: $AVG_UTIL %" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 分析队列长度
echo "--- 队列长度统计 ---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if [ -f "$OUTPUT_DIR/queue_length.csv" ]; then
    AVG_QUEUE=$(awk -F',' '{split($2,a," "); sum+=a[1]; count++} END {if(count>0) print sum/count; else print 0}' "$OUTPUT_DIR/queue_length.csv")
    MAX_QUEUE=$(awk -F',' '{split($2,a," "); if(a[1]>max) max=a[1]} END {print max}' "$OUTPUT_DIR/queue_length.csv")
    
    echo "平均队列长度: $AVG_QUEUE" >> "$REPORT_FILE"
    echo "最大队列长度: $MAX_QUEUE" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
fi

# 分析错误
echo "--- I/O 错误统计 ---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if [ -f "$OUTPUT_DIR/error_count.txt" ]; then
    cat "$OUTPUT_DIR/error_count.txt" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
fi

# 性能评估
echo "--- 性能评估 ---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 评估等待时间
if (( $(echo "$AVG_AWAIT > 100" | bc -l) )); then
    echo "[严重] 平均 I/O 等待时间 ($AVG_AWAIT ms) 过高！" >> "$REPORT_FILE"
elif (( $(echo "$AVG_AWAIT > 20" | bc -l) )); then
    echo "[警告] 平均 I/O 等待时间 ($AVG_AWAIT ms) 较高。" >> "$REPORT_FILE"
else
    echo "[正常] 平均 I/O 等待时间 ($AVG_AWAIT ms) 正常。" >> "$REPORT_FILE"
fi

# 评估磁盘利用率
if (( $(echo "$AVG_UTIL > 90" | bc -l) )); then
    echo "[严重] 磁盘利用率 ($AVG_UTIL %) 接近饱和！" >> "$REPORT_FILE"
elif (( $(echo "$AVG_UTIL > 70" | bc -l) )); then
    echo "[警告] 磁盘利用率 ($AVG_UTIL %) 较高。" >> "$REPORT_FILE"
else
    echo "[正常] 磁盘利用率 ($AVG_UTIL %) 正常。" >> "$REPORT_FILE"
fi

# 显示报告
cat "$REPORT_FILE"

echo ""
echo "======================================="
echo "监控完成！"
echo "======================================="
echo "详细日志保存在: $OUTPUT_DIR"
echo "  - iostat.log: iostat 详细输出"
echo "  - diskstats.log: /proc/diskstats 记录"
echo "  - queue_length.csv: I/O 队列长度"
echo "  - io_timeout.csv: I/O 超时设置"
echo "  - error_count.txt: I/O 错误计数"
echo "  - summary_report.txt: 汇总报告"
echo ""
