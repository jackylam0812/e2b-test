#!/bin/bash
# 沙箱网络诊断脚本

echo "=========================================="
echo "沙箱网络诊断"
echo "=========================================="
echo ""

# 1. 检查网络接口
echo "1. 网络接口信息:"
ip addr show 2>/dev/null || ifconfig 2>/dev/null
echo ""

# 2. 检查路由
echo "2. 路由信息:"
ip route show 2>/dev/null || route -n 2>/dev/null
echo ""

# 3. 检查DNS
echo "3. DNS配置:"
cat /etc/resolv.conf 2>/dev/null
echo ""

# 4. 测试连通性
echo "4. 连通性测试:"
TARGETS=("8.8.8.8" "1.1.1.1" "223.5.5.5" "www.baidu.com" "www.google.com")

for TARGET in "${TARGETS[@]}"; do
    echo -n "  测试 $TARGET ... "
    if timeout 3 ping -c 1 -W 2 $TARGET &>/dev/null; then
        echo "✓ 可达"
    else
        echo "✗ 不可达"
    fi
done
echo ""

# 5. 测试HTTP(S)访问
echo "5. HTTP(S)访问测试:"
HTTP_TARGETS=(
    "http://www.baidu.com"
    "https://www.google.com"
    "http://httpbin.org/ip"
)

for URL in "${HTTP_TARGETS[@]}"; do
    echo -n "  测试 $URL ... "
    if timeout 5 curl -s -o /dev/null -w "%{http_code}" "$URL" | grep -q "200"; then
        echo "✓ 可访问"
    else
        echo "✗ 无法访问"
    fi
done
echo ""

# 6. 检查防火墙/iptables
echo "6. 防火墙规则:"
iptables -L -n 2>/dev/null | head -20 || echo "  无权限查看或未安装iptables"
echo ""

# 7. 检查带宽限制
echo "7. 网络统计:"
cat /proc/net/dev 2>/dev/null || echo "  无法读取网络统计"
echo ""

echo "=========================================="
echo "诊断完成"
echo "=========================================="
