#!/bin/bash
# 改进的网络性能测试脚本

echo "=========================================="
echo "网络性能测试 (改进版)"
echo "=========================================="

# 1. 网络延迟测试 - 改进版
echo "1. 网络延迟测试..."
LATENCY=""
# 尝试多个公共DNS
for DNS in "8.8.8.8" "1.1.1.1" "223.5.5.5"; do
    echo "  尝试 ping $DNS..."
    if ping -c 3 -W 2 $DNS &>/dev/null; then
        LATENCY=$(ping -c 10 -W 2 $DNS 2>/dev/null | grep 'rtt min/avg/max' | cut -d'=' -f2 | cut -d'/' -f2)
        if [ ! -z "$LATENCY" ]; then
            echo "  ✓ 平均延迟: $LATENCY ms (via $DNS)"
            break
        fi
    fi
done

if [ -z "$LATENCY" ]; then
    echo "  ✗ 无法测试网络延迟（可能无外网访问）"
    LATENCY="null"
fi

# 2. 下载带宽测试 - 改进版
echo ""
echo "2. 下载带宽测试..."
DOWNLOAD_BW="null"

# 尝试多个下载源
DOWNLOAD_URLS=(
    "http://speedtest.tele2.net/10MB.zip"
    "http://ipv4.download.thinkbroadband.com/10MB.zip"
    "http://mirror.azure.cn/speedtest/10mb.bin"
)

for URL in "${DOWNLOAD_URLS[@]}"; do
    echo "  尝试从 $URL 下载..."
    DOWNLOAD_START=$(date +%s.%N)

    # 设置超时为30秒
    if timeout 30 curl -o /tmp/test_download.bin -s --max-time 30 "$URL" 2>/dev/null; then
        DOWNLOAD_END=$(date +%s.%N)

        # 验证文件是否下载成功
        if [ -f /tmp/test_download.bin ] && [ -s /tmp/test_download.bin ]; then
            FILE_SIZE=$(stat -f%z /tmp/test_download.bin 2>/dev/null || stat -c%s /tmp/test_download.bin 2>/dev/null)
            DOWNLOAD_TIME=$(echo "$DOWNLOAD_END - $DOWNLOAD_START" | bc 2>/dev/null)

            # 避免除以0
            if [ $(echo "$DOWNLOAD_TIME > 0" | bc) -eq 1 ]; then
                # 转换为 MB/s
                DOWNLOAD_BW=$(echo "scale=2; $FILE_SIZE / 1024 / 1024 / $DOWNLOAD_TIME" | bc 2>/dev/null)
                echo "  ✓ 下载带宽: $DOWNLOAD_BW MB/s (文件大小: $(echo "scale=2; $FILE_SIZE / 1024 / 1024" | bc) MB, 耗时: $DOWNLOAD_TIME 秒)"
                rm -f /tmp/test_download.bin
                break
            fi
        fi
    fi

    rm -f /tmp/test_download.bin
    echo "  ✗ 从 $URL 下载失败，尝试下一个..."
done

if [ "$DOWNLOAD_BW" = "null" ]; then
    echo "  ✗ 所有下载测试失败（可能无外网访问或网络不稳定）"
fi

# 3. 上传带宽测试 - 改进版
echo ""
echo "3. 上传带宽测试..."
UPLOAD_BW="null"

# 创建测试文件
dd if=/dev/zero of=/tmp/test_upload.bin bs=1M count=5 2>/dev/null

if [ -f /tmp/test_upload.bin ]; then
    # 尝试多个上传目标
    UPLOAD_URLS=(
        "https://httpbin.org/post"
        "https://postman-echo.com/post"
    )

    for URL in "${UPLOAD_URLS[@]}"; do
        echo "  尝试上传到 $URL..."
        UPLOAD_START=$(date +%s.%N)

        # 设置超时为60秒
        if timeout 60 curl -X POST -F "file=@/tmp/test_upload.bin" "$URL" -o /dev/null -s --max-time 60 2>/dev/null; then
            UPLOAD_END=$(date +%s.%N)
            UPLOAD_TIME=$(echo "$UPLOAD_END - $UPLOAD_START" | bc 2>/dev/null)

            # 避免除以0
            if [ $(echo "$UPLOAD_TIME > 0" | bc) -eq 1 ]; then
                UPLOAD_BW=$(echo "scale=2; 5 / $UPLOAD_TIME" | bc 2>/dev/null)
                echo "  ✓ 上传带宽: $UPLOAD_BW MB/s (耗时: $UPLOAD_TIME 秒)"
                break
            fi
        fi

        echo "  ✗ 上传到 $URL 失败，尝试下一个..."
    done

    rm -f /tmp/test_upload.bin
fi

if [ "$UPLOAD_BW" = "null" ]; then
    echo "  ✗ 所有上传测试失败（可能无外网访问或网络不稳定）"
fi

# 4. 生成结果
echo ""
echo "=========================================="
echo "网络测试结果汇总"
echo "=========================================="
cat << EOF
{
  "network": {
    "latency_ms": ${LATENCY:-null},
    "download_bandwidth_mbs": ${DOWNLOAD_BW:-null},
    "upload_bandwidth_mbs": ${UPLOAD_BW:-null}
  },
  "test_date": "$(date -Iseconds)"
}
EOF

echo ""
echo "✓ 网络测试完成"
