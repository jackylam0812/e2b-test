#!/bin/bash

# 检查 fio 的尾延迟数据

FIO_RESULT="${1:-/tmp/fio_results/rand-write-4k.json}"

if [ ! -f "$FIO_RESULT" ]; then
    echo "错误: fio 结果文件不存在: $FIO_RESULT"
    echo ""
    echo "请先运行 fio 测试:"
    echo "  bash /home/ubuntu/io_test_scripts/fio_comprehensive_test.sh /orchestrator/sandbox"
    exit 1
fi

echo "======================================="
echo "FIO 尾延迟分析"
echo "======================================="
echo "文件: $FIO_RESULT"
echo ""

# 提取延迟百分位数
echo "--- 写入延迟百分位数 (纳秒) ---"
echo ""

P50=$(jq -r '.jobs[0].write.lat_ns.percentile."50.000000"' "$FIO_RESULT" 2>/dev/null)
P90=$(jq -r '.jobs[0].write.lat_ns.percentile."90.000000"' "$FIO_RESULT" 2>/dev/null)
P95=$(jq -r '.jobs[0].write.lat_ns.percentile."95.000000"' "$FIO_RESULT" 2>/dev/null)
P99=$(jq -r '.jobs[0].write.lat_ns.percentile."99.000000"' "$FIO_RESULT" 2>/dev/null)
P999=$(jq -r '.jobs[0].write.lat_ns.percentile."99.900000"' "$FIO_RESULT" 2>/dev/null)
P9999=$(jq -r '.jobs[0].write.lat_ns.percentile."99.990000"' "$FIO_RESULT" 2>/dev/null)
P99999=$(jq -r '.jobs[0].write.lat_ns.percentile."99.999000"' "$FIO_RESULT" 2>/dev/null)

# 转换为毫秒
P50_MS=$(echo "scale=2; $P50 / 1000000" | bc)
P90_MS=$(echo "scale=2; $P90 / 1000000" | bc)
P95_MS=$(echo "scale=2; $P95 / 1000000" | bc)
P99_MS=$(echo "scale=2; $P99 / 1000000" | bc)
P999_MS=$(echo "scale=2; $P999 / 1000000" | bc)
P9999_MS=$(echo "scale=2; $P9999 / 1000000" | bc)
P99999_MS=$(echo "scale=2; $P99999 / 1000000" | bc)

printf "%-10s %15s %15s\n" "百分位" "延迟 (ns)" "延迟 (ms)"
echo "-----------------------------------------------"
printf "%-10s %15s %15s\n" "P50" "$P50" "$P50_MS"
printf "%-10s %15s %15s\n" "P90" "$P90" "$P90_MS"
printf "%-10s %15s %15s\n" "P95" "$P95" "$P95_MS"
printf "%-10s %15s %15s\n" "P99" "$P99" "$P99_MS"
printf "%-10s %15s %15s\n" "P99.9" "$P999" "$P999_MS"
printf "%-10s %15s %15s\n" "P99.99" "$P9999" "$P9999_MS"
printf "%-10s %15s %15s\n" "P99.999" "$P99999" "$P99999_MS"

echo ""
echo "--- 分析 ---"
echo ""

# 分析 P99.9
if (( $(echo "$P999_MS > 1000" | bc -l) )); then
    echo "[严重] P99.9 延迟 > 1 秒 ($P999_MS ms)！"
    echo "这意味着每 1000 个请求中，至少有 1 个需要超过 1 秒。"
    echo "这会导致 NBD 超时。"
elif (( $(echo "$P999_MS > 100" | bc -l) )); then
    echo "[警告] P99.9 延迟 > 100 ms ($P999_MS ms)。"
    echo "这可能在高负载下导致 NBD 超时。"
else
    echo "[正常] P99.9 延迟 < 100 ms ($P999_MS ms)。"
fi

echo ""

# 分析 P99.99
if (( $(echo "$P9999_MS > 10000" | bc -l) )); then
    echo "[严重] P99.99 延迟 > 10 秒 ($P9999_MS ms)！"
    echo "这意味着每 10000 个请求中，至少有 1 个需要超过 10 秒。"
    echo "这会频繁触发 NBD 的 30 秒超时。"
elif (( $(echo "$P9999_MS > 1000" | bc -l) )); then
    echo "[警告] P99.99 延迟 > 1 秒 ($P9999_MS ms)。"
    echo "这可能导致偶尔的 NBD 超时。"
fi

echo ""
echo "======================================="
echo "建议"
echo "======================================="
echo ""

if (( $(echo "$P999_MS > 100" | bc -l) )); then
    echo "您的磁盘存在严重的尾延迟问题。"
    echo ""
    echo "可能的原因："
    echo "  1. AWS EBS 突发积分耗尽 (gp2)"
    echo "  2. IOPS 配额不足"
    echo "  3. 磁盘硬件故障"
    echo ""
    echo "建议："
    echo "  1. 运行 AWS EBS 监控:"
    echo "     bash aws_ebs_monitor.sh vol-0323a2d805288d8c7 60"
    echo ""
    echo "  2. 升级到更高 IOPS 的 EBS 卷:"
    echo "     aws ec2 modify-volume \\"
    echo "       --volume-id vol-0323a2d805288d8c7 \\"
    echo "       --volume-type gp3 \\"
    echo "       --iops 16000 \\"
    echo "       --throughput 500"
else
    echo "您的尾延迟在可接受范围内。"
    echo "NBD 超时可能由其他原因引起。"
fi

echo ""
