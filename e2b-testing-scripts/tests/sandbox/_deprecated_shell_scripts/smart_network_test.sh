#!/bin/bash

# ==============================================================================
#
# 智能网络测试脚本
#
# 功能:
#   1. 优先使用 ping 测试网络连通性
#   2. 如果 ping 失败，自动切换到 curl 进行网络质量测试
#   3. 包含延迟测试和下载速度测试
#
# 用法:
#   ./smart_network_test.sh
#
# ==============================================================================

# --- 配置 ---
# ping 目标地址
PING_TARGET="8.8.8.8"
PING_COUNT=5
PING_TIMEOUT=3

# curl 延迟测试的目标地址
LATENCY_TARGET="https://www.google.com"

# 下载速度测试文件地址
# 其他可用测速文件:
# 100MB: http://cachefly.cachefly.net/100mb.test
# 1GB: http://cachefly.cachefly.net/1gb.test
SPEED_TEST_FILE="http://cachefly.cachefly.net/10mb.test"

# 备用下载源（国内网络可能更快）
SPEED_TEST_FILE_CN="http://mirror.azure.cn/speedtest/10mb.bin"

# --- 颜色定义 ---
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- curl 输出格式 ---
CURL_FORMAT="\n\
\t${YELLOW}DNS 解析时间:${NC}\t %{time_namelookup}s\n\
\t${YELLOW}TCP 连接时间:${NC}\t %{time_connect}s\n\
\t${YELLOW}SSL 握手时间:${NC}\t %{time_appconnect}s\n\
\t${YELLOW}服务器处理时间:${NC}\t %{time_pretransfer}s\n\
\t${YELLOW}总请求时间:${NC}\t\t %{time_total}s\n\
"

# --- 开始测试 ---
echo -e "${BLUE}=========================================="
echo -e "智能网络测试"
echo -e "==========================================${NC}"
echo ""

# --- 1. 尝试使用 ping 测试 ---
echo -e "${BLUE}--- 第一步: 尝试 ping 测试 (目标: ${PING_TARGET}) ---${NC}"

PING_SUCCESS=false
if command -v ping &> /dev/null; then
    echo -n "正在 ping ${PING_TARGET}..."

    if timeout ${PING_TIMEOUT} ping -c ${PING_COUNT} -W 2 ${PING_TARGET} &>/dev/null; then
        PING_SUCCESS=true
        echo -e " ${GREEN}✓ 成功${NC}"
        echo ""

        # 显示详细的 ping 结果
        echo -e "${BLUE}Ping 测试结果:${NC}"
        PING_RESULT=$(ping -c ${PING_COUNT} -W 2 ${PING_TARGET} 2>/dev/null | grep 'rtt min/avg/max')

        if [ ! -z "$PING_RESULT" ]; then
            AVG_LATENCY=$(echo "$PING_RESULT" | cut -d'=' -f2 | cut -d'/' -f2)
            MIN_LATENCY=$(echo "$PING_RESULT" | cut -d'=' -f2 | cut -d'/' -f1)
            MAX_LATENCY=$(echo "$PING_RESULT" | cut -d'=' -f2 | cut -d'/' -f3)

            echo -e "\t${YELLOW}最小延迟:${NC}\t ${MIN_LATENCY} ms"
            echo -e "\t${YELLOW}平均延迟:${NC}\t ${AVG_LATENCY} ms"
            echo -e "\t${YELLOW}最大延迟:${NC}\t ${MAX_LATENCY} ms"
        fi

        # Ping 成功，进行简单的下载速度测试
        echo ""
        echo -e "${BLUE}--- 下载速度测试 ---${NC}"

        # 尝试国内源
        echo "尝试国内测速源..."
        speed_info=$(curl -o /dev/null -s -w "%{speed_download}\n%{size_download}" --max-time 30 "${SPEED_TEST_FILE_CN}" 2>/dev/null)

        if [ $? -ne 0 ] || [ -z "$speed_info" ]; then
            echo "国内源失败，尝试国际源..."
            speed_info=$(curl -o /dev/null -s -w "%{speed_download}\n%{size_download}" --max-time 30 "${SPEED_TEST_FILE}" 2>/dev/null)
        fi

        if [ ! -z "$speed_info" ]; then
            download_speed_bps=$(echo "$speed_info" | sed -n 1p)
            download_size_b=$(echo "$speed_info" | sed -n 2p)

            if [ ! -z "$download_speed_bps" ] && [ "$download_speed_bps" != "0" ]; then
                download_speed_mbps=$(awk "BEGIN {printf \"%.2f\", ${download_speed_bps} / 1024 / 1024}")
                download_speed_mbitps=$(awk "BEGIN {printf \"%.2f\", ${download_speed_bps} * 8 / 1024 / 1024}")
                download_size_mb=$(awk "BEGIN {printf \"%.2f\", ${download_size_b} / 1024 / 1024}")

                echo -e "\t${YELLOW}下载文件大小:${NC}\t ${download_size_mb} MB"
                echo -e "\t${YELLOW}平均下载速度:${NC}\t ${download_speed_mbps} MB/s (${download_speed_mbitps} Mbps)"
            else
                echo -e "\t${RED}✗ 下载速度测试失败${NC}"
            fi
        else
            echo -e "\t${RED}✗ 下载速度测试失败${NC}"
        fi

    else
        echo -e " ${RED}✗ 失败${NC}"
        echo -e "${YELLOW}Ping ${PING_TARGET} 不通，切换到 curl 测试模式${NC}"
    fi
else
    echo -e "${RED}✗ 系统未安装 ping 命令${NC}"
    echo -e "${YELLOW}切换到 curl 测试模式${NC}"
fi

# --- 2. 如果 ping 失败，使用 curl 测试 ---
if [ "$PING_SUCCESS" = false ]; then
    echo ""
    echo -e "${BLUE}--- 第二步: 使用 curl 进行网络质量测试 ---${NC}"
    echo ""

    # 检查 curl 是否可用
    if ! command -v curl &> /dev/null; then
        echo -e "${RED}✗ 错误: 系统未安装 curl 命令${NC}"
        echo -e "${RED}无法进行网络测试，请安装 curl 或 ping 工具${NC}"
        exit 1
    fi

    # 2.1 网络延迟测试（使用 curl）
    echo -e "${BLUE}--- curl 网络延迟测试 (目标: ${LATENCY_TARGET}) ---${NC}"

    # 尝试多个目标
    CURL_TARGETS=(
        "https://www.google.com"
        "https://www.baidu.com"
        "https://httpbin.org/get"
    )

    CURL_TEST_SUCCESS=false
    for TARGET in "${CURL_TARGETS[@]}"; do
        echo "尝试连接 ${TARGET}..."
        if timeout 10 curl -o /dev/null -s -w "${CURL_FORMAT}" "${TARGET}" 2>/dev/null; then
            CURL_TEST_SUCCESS=true
            break
        else
            echo -e "${RED}✗ 连接失败，尝试下一个...${NC}"
        fi
    done

    if [ "$CURL_TEST_SUCCESS" = false ]; then
        echo -e "${RED}✗ 所有 curl 延迟测试失败${NC}"
        echo -e "${RED}网络可能完全不可用${NC}"
    fi

    echo ""

    # 2.2 下载速度测试
    echo -e "${BLUE}--- 下载速度测试 ---${NC}"

    # 尝试多个下载源
    DOWNLOAD_SOURCES=(
        "${SPEED_TEST_FILE_CN}|国内源"
        "${SPEED_TEST_FILE}|国际源"
        "http://speedtest.tele2.net/10MB.zip|欧洲源"
    )

    DOWNLOAD_SUCCESS=false
    for SOURCE in "${DOWNLOAD_SOURCES[@]}"; do
        URL=$(echo "$SOURCE" | cut -d'|' -f1)
        NAME=$(echo "$SOURCE" | cut -d'|' -f2)

        echo "尝试 ${NAME}: ${URL}..."
        speed_info=$(curl -o /dev/null -s -w "%{speed_download}\n%{size_download}\n%{time_total}" --max-time 30 "${URL}" 2>/dev/null)

        if [ $? -eq 0 ] && [ ! -z "$speed_info" ]; then
            download_speed_bps=$(echo "$speed_info" | sed -n 1p)
            download_size_b=$(echo "$speed_info" | sed -n 2p)
            download_time=$(echo "$speed_info" | sed -n 3p)

            if [ ! -z "$download_speed_bps" ] && [ "$download_speed_bps" != "0" ]; then
                download_speed_mbps=$(awk "BEGIN {printf \"%.2f\", ${download_speed_bps} / 1024 / 1024}")
                download_speed_mbitps=$(awk "BEGIN {printf \"%.2f\", ${download_speed_bps} * 8 / 1024 / 1024}")
                download_size_mb=$(awk "BEGIN {printf \"%.2f\", ${download_size_b} / 1024 / 1024}")

                echo -e "\t${GREEN}✓ 下载成功${NC}"
                echo -e "\t${YELLOW}下载文件大小:${NC}\t ${download_size_mb} MB"
                echo -e "\t${YELLOW}下载耗时:${NC}\t\t ${download_time} s"
                echo -e "\t${YELLOW}平均下载速度:${NC}\t ${download_speed_mbps} MB/s (${download_speed_mbitps} Mbps)"

                DOWNLOAD_SUCCESS=true
                break
            fi
        fi

        echo -e "\t${RED}✗ 下载失败，尝试下一个源...${NC}"
    done

    if [ "$DOWNLOAD_SUCCESS" = false ]; then
        echo -e "${RED}✗ 所有下载测试失败${NC}"
        echo -e "${RED}网络可能存在严重问题或防火墙限制${NC}"
    fi
fi

# --- 测试完成 ---
echo ""
echo -e "${GREEN}=========================================="
echo -e "测试完成"
echo -e "==========================================${NC}"
