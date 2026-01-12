#!/bin/bash

# AWS EBS 特定的监控脚本
# 使用 AWS CloudWatch 获取 EBS 性能指标

set -e

VOLUME_ID="${1}"
DURATION="${2:-60}"  # 默认监控 60 分钟

if [ -z "$VOLUME_ID" ]; then
    echo "用法: $0 <volume-id> [duration-in-minutes]"
    echo "示例: $0 vol-0323a2d805288d8c7 60"
    exit 1
fi

# 检查 AWS CLI 是否安装
if ! command -v aws &> /dev/null; then
    echo "错误: AWS CLI 未安装。"
    echo "安装方法: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
    exit 1
fi

# 检查 AWS CLI 是否配置
if ! aws sts get-caller-identity &> /dev/null; then
    echo "错误: AWS CLI 未配置。请运行 'aws configure'"
    exit 1
fi

echo "======================================="
echo "AWS EBS 性能监控"
echo "======================================="
echo "卷 ID: $VOLUME_ID"
echo "监控时长: ${DURATION} 分钟"
echo "======================================="
echo ""

# 创建输出目录
OUTPUT_DIR="/tmp/aws_ebs_monitor_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUTPUT_DIR"

# 获取卷信息
echo "正在获取卷信息..."
aws ec2 describe-volumes --volume-ids $VOLUME_ID > "$OUTPUT_DIR/volume_info.json"

VOLUME_TYPE=$(jq -r '.Volumes[0].VolumeType' "$OUTPUT_DIR/volume_info.json")
VOLUME_SIZE=$(jq -r '.Volumes[0].Size' "$OUTPUT_DIR/volume_info.json")
VOLUME_IOPS=$(jq -r '.Volumes[0].Iops' "$OUTPUT_DIR/volume_info.json")
VOLUME_THROUGHPUT=$(jq -r '.Volumes[0].Throughput' "$OUTPUT_DIR/volume_info.json")

echo "卷类型: $VOLUME_TYPE"
echo "卷大小: ${VOLUME_SIZE} GB"
echo "配置 IOPS: $VOLUME_IOPS"
echo "配置吞吐量: $VOLUME_THROUGHPUT MB/s"
echo ""

# 计算时间范围
END_TIME=$(date -u +%Y-%m-%dT%H:%M:%S)
START_TIME=$(date -u -d "$DURATION minutes ago" +%Y-%m-%dT%H:%M:%S)

echo "时间范围: $START_TIME 到 $END_TIME (UTC)"
echo ""

# 定义要监控的指标
declare -A METRICS=(
    ["VolumeReadOps"]="读操作数"
    ["VolumeWriteOps"]="写操作数"
    ["VolumeReadBytes"]="读字节数"
    ["VolumeWriteBytes"]="写字节数"
    ["VolumeTotalReadTime"]="总读时间"
    ["VolumeTotalWriteTime"]="总写时间"
    ["VolumeIdleTime"]="空闲时间"
    ["VolumeQueueLength"]="队列长度"
    ["VolumeThroughputPercentage"]="吞吐量百分比"
    ["VolumeConsumedReadWriteOps"]="消耗的读写操作"
    ["BurstBalance"]="突发余额"
)

echo "正在获取 CloudWatch 指标..."

# 获取每个指标
for metric in "${!METRICS[@]}"; do
    echo "  - $metric (${METRICS[$metric]})..."
    
    aws cloudwatch get-metric-statistics \
        --namespace AWS/EBS \
        --metric-name $metric \
        --dimensions Name=VolumeId,Value=$VOLUME_ID \
        --start-time $START_TIME \
        --end-time $END_TIME \
        --period 60 \
        --statistics Average,Maximum,Minimum \
        --output json > "$OUTPUT_DIR/${metric}.json" 2>/dev/null || true
done

echo ""
echo "======================================="
echo "生成汇总报告..."
echo "======================================="

REPORT_FILE="$OUTPUT_DIR/summary_report.txt"

cat > "$REPORT_FILE" << EOF
======================================
AWS EBS 性能监控报告
======================================
卷 ID: $VOLUME_ID
卷类型: $VOLUME_TYPE
卷大小: ${VOLUME_SIZE} GB
配置 IOPS: $VOLUME_IOPS
配置吞吐量: $VOLUME_THROUGHPUT MB/s
监控时间: $START_TIME 到 $END_TIME (UTC)
======================================

EOF

# 分析 IOPS
echo "--- IOPS 统计 ---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if [ -f "$OUTPUT_DIR/VolumeReadOps.json" ]; then
    READ_OPS_AVG=$(jq -r '[.Datapoints[].Average] | add / length' "$OUTPUT_DIR/VolumeReadOps.json" 2>/dev/null || echo "0")
    READ_OPS_MAX=$(jq -r '[.Datapoints[].Maximum] | max' "$OUTPUT_DIR/VolumeReadOps.json" 2>/dev/null || echo "0")
    
    echo "平均读 IOPS: $READ_OPS_AVG" >> "$REPORT_FILE"
    echo "峰值读 IOPS: $READ_OPS_MAX" >> "$REPORT_FILE"
fi

if [ -f "$OUTPUT_DIR/VolumeWriteOps.json" ]; then
    WRITE_OPS_AVG=$(jq -r '[.Datapoints[].Average] | add / length' "$OUTPUT_DIR/VolumeWriteOps.json" 2>/dev/null || echo "0")
    WRITE_OPS_MAX=$(jq -r '[.Datapoints[].Maximum] | max' "$OUTPUT_DIR/VolumeWriteOps.json" 2>/dev/null || echo "0")
    
    echo "平均写 IOPS: $WRITE_OPS_AVG" >> "$REPORT_FILE"
    echo "峰值写 IOPS: $WRITE_OPS_MAX" >> "$REPORT_FILE"
fi

TOTAL_IOPS_AVG=$(echo "$READ_OPS_AVG + $WRITE_OPS_AVG" | bc)
TOTAL_IOPS_MAX=$(echo "$READ_OPS_MAX + $WRITE_OPS_MAX" | bc)

echo "平均总 IOPS: $TOTAL_IOPS_AVG" >> "$REPORT_FILE"
echo "峰值总 IOPS: $TOTAL_IOPS_MAX" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 分析吞吐量
echo "--- 吞吐量统计 ---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if [ -f "$OUTPUT_DIR/VolumeReadBytes.json" ]; then
    READ_BYTES_AVG=$(jq -r '[.Datapoints[].Average] | add / length' "$OUTPUT_DIR/VolumeReadBytes.json" 2>/dev/null || echo "0")
    READ_MB_AVG=$(echo "scale=2; $READ_BYTES_AVG / 1024 / 1024" | bc)
    
    echo "平均读吞吐量: $READ_MB_AVG MB/s" >> "$REPORT_FILE"
fi

if [ -f "$OUTPUT_DIR/VolumeWriteBytes.json" ]; then
    WRITE_BYTES_AVG=$(jq -r '[.Datapoints[].Average] | add / length' "$OUTPUT_DIR/VolumeWriteBytes.json" 2>/dev/null || echo "0")
    WRITE_MB_AVG=$(echo "scale=2; $WRITE_BYTES_AVG / 1024 / 1024" | bc)
    
    echo "平均写吞吐量: $WRITE_MB_AVG MB/s" >> "$REPORT_FILE"
fi

echo "" >> "$REPORT_FILE"

# 分析延迟
echo "--- 延迟统计 ---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if [ -f "$OUTPUT_DIR/VolumeTotalReadTime.json" ] && [ -f "$OUTPUT_DIR/VolumeReadOps.json" ]; then
    READ_TIME_AVG=$(jq -r '[.Datapoints[].Average] | add / length' "$OUTPUT_DIR/VolumeTotalReadTime.json" 2>/dev/null || echo "0")
    READ_OPS_AVG=$(jq -r '[.Datapoints[].Average] | add / length' "$OUTPUT_DIR/VolumeReadOps.json" 2>/dev/null || echo "1")
    
    if [ "$READ_OPS_AVG" != "0" ]; then
        READ_LATENCY=$(echo "scale=2; $READ_TIME_AVG / $READ_OPS_AVG * 1000" | bc)
        echo "平均读延迟: $READ_LATENCY ms" >> "$REPORT_FILE"
    fi
fi

if [ -f "$OUTPUT_DIR/VolumeTotalWriteTime.json" ] && [ -f "$OUTPUT_DIR/VolumeWriteOps.json" ]; then
    WRITE_TIME_AVG=$(jq -r '[.Datapoints[].Average] | add / length' "$OUTPUT_DIR/VolumeTotalWriteTime.json" 2>/dev/null || echo "0")
    WRITE_OPS_AVG=$(jq -r '[.Datapoints[].Average] | add / length' "$OUTPUT_DIR/VolumeWriteOps.json" 2>/dev/null || echo "1")
    
    if [ "$WRITE_OPS_AVG" != "0" ]; then
        WRITE_LATENCY=$(echo "scale=2; $WRITE_TIME_AVG / $WRITE_OPS_AVG * 1000" | bc)
        echo "平均写延迟: $WRITE_LATENCY ms" >> "$REPORT_FILE"
    fi
fi

echo "" >> "$REPORT_FILE"

# 分析队列长度
echo "--- 队列长度统计 ---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if [ -f "$OUTPUT_DIR/VolumeQueueLength.json" ]; then
    QUEUE_AVG=$(jq -r '[.Datapoints[].Average] | add / length' "$OUTPUT_DIR/VolumeQueueLength.json" 2>/dev/null || echo "0")
    QUEUE_MAX=$(jq -r '[.Datapoints[].Maximum] | max' "$OUTPUT_DIR/VolumeQueueLength.json" 2>/dev/null || echo "0")
    
    echo "平均队列长度: $QUEUE_AVG" >> "$REPORT_FILE"
    echo "最大队列长度: $QUEUE_MAX" >> "$REPORT_FILE"
fi

echo "" >> "$REPORT_FILE"

# 分析突发余额 (仅 gp2)
if [ "$VOLUME_TYPE" = "gp2" ]; then
    echo "--- 突发余额 (Burst Balance) ---" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    
    if [ -f "$OUTPUT_DIR/BurstBalance.json" ]; then
        BURST_AVG=$(jq -r '[.Datapoints[].Average] | add / length' "$OUTPUT_DIR/BurstBalance.json" 2>/dev/null || echo "0")
        BURST_MIN=$(jq -r '[.Datapoints[].Minimum] | min' "$OUTPUT_DIR/BurstBalance.json" 2>/dev/null || echo "0")
        
        echo "平均突发余额: $BURST_AVG %" >> "$REPORT_FILE"
        echo "最低突发余额: $BURST_MIN %" >> "$REPORT_FILE"
        
        if (( $(echo "$BURST_MIN < 10" | bc -l) )); then
            echo "" >> "$REPORT_FILE"
            echo "[严重警告] 突发余额接近耗尽！这是性能下降的主要原因。" >> "$REPORT_FILE"
        fi
    fi
    
    echo "" >> "$REPORT_FILE"
fi

# 性能评估
echo "--- 性能评估 ---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 评估 IOPS 使用率
IOPS_USAGE=$(echo "scale=2; $TOTAL_IOPS_AVG / $VOLUME_IOPS * 100" | bc)
echo "IOPS 使用率: $IOPS_USAGE %" >> "$REPORT_FILE"

if (( $(echo "$IOPS_USAGE > 90" | bc -l) )); then
    echo "[严重] IOPS 使用率超过 90%，已接近配额上限！" >> "$REPORT_FILE"
    echo "建议：升级到更高 IOPS 的卷类型。" >> "$REPORT_FILE"
elif (( $(echo "$IOPS_USAGE > 70" | bc -l) )); then
    echo "[警告] IOPS 使用率超过 70%，可能在高峰时段触及上限。" >> "$REPORT_FILE"
    echo "建议：考虑升级 IOPS 配额。" >> "$REPORT_FILE"
else
    echo "[正常] IOPS 使用率正常。" >> "$REPORT_FILE"
fi

echo "" >> "$REPORT_FILE"

# 评估队列长度
if [ -n "$QUEUE_AVG" ] && (( $(echo "$QUEUE_AVG > 1" | bc -l) )); then
    echo "[警告] 平均队列长度 > 1，说明 I/O 请求在排队等待。" >> "$REPORT_FILE"
    echo "这表明磁盘无法及时处理所有请求。" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
fi

# 升级建议
echo "--- 升级建议 ---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

if [ "$VOLUME_TYPE" = "gp2" ]; then
    echo "当前卷类型: gp2" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "建议升级到 gp3:" >> "$REPORT_FILE"
    echo "  - 固定 3000 IOPS 基准（不依赖突发积分）" >> "$REPORT_FILE"
    echo "  - 可按需购买额外 IOPS（最高 16,000）" >> "$REPORT_FILE"
    echo "  - 价格更低（比 gp2 便宜约 20%）" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "推荐配置:" >> "$REPORT_FILE"
    echo "  - IOPS: 10,000" >> "$REPORT_FILE"
    echo "  - 吞吐量: 500 MB/s" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    echo "升级命令:" >> "$REPORT_FILE"
    echo "  aws ec2 modify-volume \\" >> "$REPORT_FILE"
    echo "    --volume-id $VOLUME_ID \\" >> "$REPORT_FILE"
    echo "    --volume-type gp3 \\" >> "$REPORT_FILE"
    echo "    --iops 10000 \\" >> "$REPORT_FILE"
    echo "    --throughput 500" >> "$REPORT_FILE"
elif [ "$VOLUME_TYPE" = "gp3" ]; then
    if (( $(echo "$VOLUME_IOPS < 10000" | bc -l) )); then
        echo "当前卷类型: gp3 ($VOLUME_IOPS IOPS)" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
        echo "建议增加 IOPS 配额到 10,000:" >> "$REPORT_FILE"
        echo "  aws ec2 modify-volume \\" >> "$REPORT_FILE"
        echo "    --volume-id $VOLUME_ID \\" >> "$REPORT_FILE"
        echo "    --iops 10000" >> "$REPORT_FILE"
    else
        echo "当前配置已经很好 (gp3, $VOLUME_IOPS IOPS)。" >> "$REPORT_FILE"
    fi
fi

# 显示报告
cat "$REPORT_FILE"

echo ""
echo "======================================="
echo "监控完成！"
echo "======================================="
echo "详细数据保存在: $OUTPUT_DIR"
echo "汇总报告: $REPORT_FILE"
echo ""
