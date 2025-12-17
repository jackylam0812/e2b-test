#!/bin/bash
# 沙箱内 CPU 性能测试脚本
# 在沙箱内运行此脚本

echo "=========================================="
echo "沙箱内 CPU 性能测试"
echo "=========================================="
echo ""

# 安装 sysbench
echo "安装 sysbench..."
apt-get update -qq && apt-get install -y -qq sysbench
echo "✓ 安装完成"
echo ""

# 单线程测试
echo "CPU 单线程测试 (10秒)..."
sysbench cpu --threads=1 --time=10 run | tee /tmp/cpu_single.txt
SINGLE_SCORE=$(grep "events per second" /tmp/cpu_single.txt | awk '{print $NF}')
echo ""
echo "✓ 单线程分数: $SINGLE_SCORE events/s"
echo ""

# 多线程测试
THREADS=$(nproc)
echo "CPU 多线程测试 (${THREADS}线程, 10秒)..."
sysbench cpu --threads=${THREADS} --time=10 run | tee /tmp/cpu_multi.txt
MULTI_SCORE=$(grep "events per second" /tmp/cpu_multi.txt | awk '{print $NF}')
echo ""
echo "✓ 多线程分数: $MULTI_SCORE events/s"
echo ""

# 生成 JSON 结果
cat > /tmp/sandbox_cpu_result.json << EOF
{
  "single_thread_events_per_sec": $SINGLE_SCORE,
  "multi_thread_events_per_sec": $MULTI_SCORE,
  "cpu_threads": $THREADS,
  "test_date": "$(date -Iseconds)"
}
EOF

echo "=========================================="
echo "测试完成!"
echo "=========================================="
echo ""
echo "结果已保存到: /tmp/sandbox_cpu_result.json"
echo ""
cat /tmp/sandbox_cpu_result.json
echo ""
echo "请复制以上 JSON 内容保存到本地"
