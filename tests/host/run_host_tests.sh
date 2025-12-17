#!/bin/bash
# 宿主机性能测试 - 统一入口
# 在 orchestrator 宿主机上执行

set -e

echo "=========================================="
echo "宿主机性能测试"
echo "=========================================="
echo ""

# 输出目录
OUTPUT_DIR="${1:-../../outputs}"
mkdir -p "$OUTPUT_DIR"

echo "输出目录: $OUTPUT_DIR"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 1. 硬件性能测试
echo "[1/2] 硬件性能测试"
echo "------------------------------------------"
python3 "$SCRIPT_DIR/04_host_performance.py" \
  --test all \
  --output "$OUTPUT_DIR/04_host_performance.json"

if [ $? -eq 0 ]; then
    echo "✓ 硬件性能测试完成"
else
    echo "✗ 硬件性能测试失败"
fi
echo ""

# 2. 云存储性能测试(可选)
echo "[2/2] 云存储性能测试(可选)"
echo "------------------------------------------"

if [ -n "$S3_BUCKET" ]; then
    echo "测试 S3: $S3_BUCKET"
    python3 "$SCRIPT_DIR/05_cloud_storage.py" \
      --bucket "$S3_BUCKET" \
      --cloud s3 \
      --test all \
      --output "$OUTPUT_DIR/05_cloud_storage.json"

    if [ $? -eq 0 ]; then
        echo "✓ 云存储测试完成"
    else
        echo "✗ 云存储测试失败"
    fi
else
    echo "⚠️  跳过(未设置 S3_BUCKET 环境变量)"
    echo ""
    echo "如需测试云存储,请设置 S3_BUCKET 并重新运行:"
    echo "  export S3_BUCKET=your-bucket-name"
    echo "  bash run_host_tests.sh"
fi

echo ""
echo "=========================================="
echo "宿主机测试完成!"
echo "=========================================="
echo ""
echo "结果保存在: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"/*.json 2>/dev/null || true
echo ""
