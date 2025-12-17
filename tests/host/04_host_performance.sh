#!/bin/bash
#
# E2B宿主机性能测试脚本
# 此脚本需要在宿主机上执行
#
# 测试指标:
# - CPU性能(单核/多核/架构)
# - 内存性能(带宽/延迟/大页内存)
# - 存储I/O性能(IOPS/吞吐量/延迟)
# - 网络I/O性能(内网带宽/公网带宽/到云存储延迟/PPS)

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 输出目录
OUTPUT_DIR="/tmp/e2b_host_benchmark_results"
mkdir -p "$OUTPUT_DIR"

# 日志函数
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查root权限
check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "此脚本需要root权限运行"
        log_info "请使用: sudo $0"
        exit 1
    fi
}

# 安装依赖
install_dependencies() {
    log_info "检查并安装测试工具..."
    
    # 检测包管理器
    if command -v apt-get &> /dev/null; then
        PKG_MANAGER="apt-get"
        apt-get update -qq
    elif command -v yum &> /dev/null; then
        PKG_MANAGER="yum"
    else
        log_error "不支持的包管理器"
        exit 1
    fi
    
    # 安装sysbench
    if ! command -v sysbench &> /dev/null; then
        $PKG_MANAGER install -y sysbench > /dev/null 2>&1
        log_info "✓ sysbench已安装"
    fi
    
    # 安装fio
    if ! command -v fio &> /dev/null; then
        $PKG_MANAGER install -y fio > /dev/null 2>&1
        log_info "✓ fio已安装"
    fi
    
    # 安装iperf3
    if ! command -v iperf3 &> /dev/null; then
        $PKG_MANAGER install -y iperf3 > /dev/null 2>&1
        log_info "✓ iperf3已安装"
    fi
    
    # 安装网络工具
    if ! command -v ping &> /dev/null; then
        $PKG_MANAGER install -y iputils-ping > /dev/null 2>&1
        log_info "✓ ping已安装"
    fi
    
    # 安装bc
    if ! command -v bc &> /dev/null; then
        $PKG_MANAGER install -y bc > /dev/null 2>&1
        log_info "✓ bc已安装"
    fi
    
    log_info "所有依赖已安装完成"
}

# 测试CPU性能
test_cpu_performance() {
    log_info "========================================="
    log_info "测试宿主机CPU性能"
    log_info "========================================="
    
    local output_file="$OUTPUT_DIR/host_cpu_performance.json"
    
    # 获取CPU信息
    local cpu_model=$(lscpu | grep "Model name" | sed 's/Model name://g' | xargs)
    local cpu_vendor=$(lscpu | grep "Vendor ID" | sed 's/Vendor ID://g' | xargs)
    local cpu_arch=$(lscpu | grep "Architecture" | sed 's/Architecture://g' | xargs)
    local cpu_cores=$(nproc)
    local cpu_threads=$(lscpu | grep "^CPU(s):" | awk '{print $2}')
    local cpu_freq_base=$(lscpu | grep "CPU MHz" | awk '{print $3}')
    local cpu_freq_max=$(lscpu | grep "CPU max MHz" | awk '{print $4}')
    
    log_info "CPU信息:"
    log_info "  厂商: $cpu_vendor"
    log_info "  型号: $cpu_model"
    log_info "  架构: $cpu_arch"
    log_info "  核心数: $cpu_cores"
    log_info "  线程数: $cpu_threads"
    log_info "  基础频率: $cpu_freq_base MHz"
    log_info "  最大频率: $cpu_freq_max MHz"
    
    # 单核性能测试
    log_info "运行CPU单核性能测试..."
    local single_core_result=$(sysbench cpu --threads=1 --time=30 run | grep "events per second:" | awk '{print $4}')
    log_info "✓ 单核性能: $single_core_result events/s"
    
    # 多核性能测试
    log_info "运行CPU多核性能测试..."
    local multi_core_result=$(sysbench cpu --threads=$cpu_cores --time=30 run | grep "events per second:" | awk '{print $4}')
    log_info "✓ 多核性能: $multi_core_result events/s ⭐"
    
    # 保存结果
    cat > "$output_file" <<EOF
{
  "cpu_vendor": "$cpu_vendor",
  "cpu_model": "$cpu_model",
  "cpu_architecture": "$cpu_arch",
  "cpu_cores": $cpu_cores,
  "cpu_threads": $cpu_threads,
  "cpu_freq_base_mhz": $cpu_freq_base,
  "cpu_freq_max_mhz": $cpu_freq_max,
  "single_core_events_per_sec": $single_core_result,
  "multi_core_events_per_sec": $multi_core_result
}
EOF
    
    log_info "结果已保存到: $output_file"
}

# 测试内存性能
test_memory_performance() {
    log_info "========================================="
    log_info "测试宿主机内存性能"
    log_info "========================================="
    
    local output_file="$OUTPUT_DIR/host_memory_performance.json"
    
    # 获取内存信息
    local total_mem=$(free -g | grep Mem | awk '{print $2}')
    log_info "总内存: ${total_mem}GB"
    
    # 内存带宽测试
    log_info "运行内存带宽测试..."
    local mem_bandwidth=$(sysbench memory --memory-block-size=1M --memory-total-size=10G --time=30 run | grep "transferred" | awk '{print $4}')
    log_info "✓ 内存带宽: $mem_bandwidth MiB/s"
    
    # 检查大页内存配置
    log_info "检查大页内存配置..."
    local hugepage_size=$(grep Hugepagesize /proc/meminfo | awk '{print $2}')
    local hugepage_total=$(grep HugePages_Total /proc/meminfo | awk '{print $2}')
    local hugepage_free=$(grep HugePages_Free /proc/meminfo | awk '{print $2}')
    
    local hugepage_enabled="No"
    if [ "$hugepage_total" -gt 0 ]; then
        hugepage_enabled="Yes"
    fi
    
    log_info "✓ 大页内存启用: $hugepage_enabled ⭐"
    log_info "  大页大小: $hugepage_size KB"
    log_info "  大页总数: $hugepage_total"
    log_info "  大页可用: $hugepage_free"
    
    # 保存结果
    cat > "$output_file" <<EOF
{
  "total_memory_gb": $total_mem,
  "memory_bandwidth_mibs": $mem_bandwidth,
  "hugepage_enabled": "$hugepage_enabled",
  "hugepage_size_kb": $hugepage_size,
  "hugepage_total": $hugepage_total,
  "hugepage_free": $hugepage_free
}
EOF
    
    log_info "结果已保存到: $output_file"
}

# 测试大页内存性能提升
test_hugepage_performance() {
    log_info "========================================="
    log_info "测试大页内存性能提升"
    log_info "========================================="
    
    local output_file="$OUTPUT_DIR/host_hugepage_performance.json"
    
    # 检查是否启用大页内存
    local hugepage_total=$(grep HugePages_Total /proc/meminfo | awk '{print $2}')
    
    if [ "$hugepage_total" -eq 0 ]; then
        log_warn "大页内存未启用,跳过性能提升测试"
        log_info "启用大页内存的方法:"
        log_info "  echo 1024 > /proc/sys/vm/nr_hugepages"
        return
    fi
    
    # 使用sysbench测试内存性能(启用大页)
    log_info "测试启用大页内存的性能..."
    local perf_with_hugepage=$(sysbench memory --memory-block-size=1M --memory-total-size=10G --time=30 run | grep "transferred" | awk '{print $4}')
    log_info "✓ 启用大页性能: $perf_with_hugepage MiB/s"
    
    # 临时禁用大页内存测试(需要重启或重新配置)
    # 这里只记录当前性能,实际对比需要手动配置
    
    log_info "注意: 要测试性能提升,需要分别在启用和未启用大页内存的情况下运行测试"
    
    # 保存结果
    cat > "$output_file" <<EOF
{
  "performance_with_hugepage_mibs": $perf_with_hugepage,
  "note": "需要分别测试启用和未启用大页内存的情况以计算性能提升"
}
EOF
    
    log_info "结果已保存到: $output_file"
}

# 测试存储I/O性能
test_storage_performance() {
    log_info "========================================="
    log_info "测试宿主机存储I/O性能"
    log_info "========================================="
    
    local output_file="$OUTPUT_DIR/host_storage_performance.json"
    local test_file="/tmp/fio_host_test_file"
    
    # 随机读IOPS测试(QD=1)
    log_info "运行随机读IOPS测试(QD=1)..."
    local rand_read_iops_qd1=$(fio --name=randread --ioengine=libaio --iodepth=1 --rw=randread --bs=4k --direct=1 --size=1G --numjobs=1 --runtime=30 --time_based --group_reporting --filename=$test_file 2>/dev/null | grep "IOPS=" | awk -F'IOPS=' '{print $2}' | awk -F',' '{print $1}')
    log_info "✓ 随机读IOPS(QD=1): $rand_read_iops_qd1 ⭐"
    
    # 随机读IOPS测试(QD=16)
    log_info "运行随机读IOPS测试(QD=16)..."
    local rand_read_iops_qd16=$(fio --name=randread --ioengine=libaio --iodepth=16 --rw=randread --bs=4k --direct=1 --size=1G --numjobs=1 --runtime=30 --time_based --group_reporting --filename=$test_file 2>/dev/null | grep "IOPS=" | awk -F'IOPS=' '{print $2}' | awk -F',' '{print $1}')
    log_info "✓ 随机读IOPS(QD=16): $rand_read_iops_qd16"
    
    # 随机写IOPS测试
    log_info "运行随机写IOPS测试..."
    local rand_write_iops=$(fio --name=randwrite --ioengine=libaio --iodepth=1 --rw=randwrite --bs=4k --direct=1 --size=1G --numjobs=1 --runtime=30 --time_based --group_reporting --filename=$test_file 2>/dev/null | grep "IOPS=" | awk -F'IOPS=' '{print $2}' | awk -F',' '{print $1}')
    log_info "✓ 随机写IOPS: $rand_write_iops"
    
    # 顺序读吞吐量测试
    log_info "运行顺序读吞吐量测试..."
    local seq_read_bw=$(fio --name=seqread --ioengine=libaio --iodepth=16 --rw=read --bs=1M --direct=1 --size=1G --numjobs=1 --runtime=30 --time_based --group_reporting --filename=$test_file 2>/dev/null | grep "BW=" | awk -F'BW=' '{print $2}' | awk -F',' '{print $1}' | sed 's/MiB\/s//g')
    log_info "✓ 顺序读吞吐量: $seq_read_bw MB/s"
    
    # 顺序写吞吐量测试
    log_info "运行顺序写吞吐量测试..."
    local seq_write_bw=$(fio --name=seqwrite --ioengine=libaio --iodepth=16 --rw=write --bs=1M --direct=1 --size=1G --numjobs=1 --runtime=30 --time_based --group_reporting --filename=$test_file 2>/dev/null | grep "BW=" | awk -F'BW=' '{print $2}' | awk -F',' '{print $1}' | sed 's/MiB\/s//g')
    log_info "✓ 顺序写吞吐量: $seq_write_bw MB/s"
    
    # 清理测试文件
    rm -f $test_file
    
    # 保存结果
    cat > "$output_file" <<EOF
{
  "random_read_iops_qd1": $rand_read_iops_qd1,
  "random_read_iops_qd16": $rand_read_iops_qd16,
  "random_write_iops": $rand_write_iops,
  "sequential_read_throughput_mbs": $seq_read_bw,
  "sequential_write_throughput_mbs": $seq_write_bw
}
EOF
    
    log_info "结果已保存到: $output_file"
}

# 测试网络性能
test_network_performance() {
    log_info "========================================="
    log_info "测试宿主机网络性能"
    log_info "========================================="
    
    local output_file="$OUTPUT_DIR/host_network_performance.json"
    
    # 测试到云存储的延迟
    log_info "测试到云存储的延迟..."
    
    # AWS S3 (us-east-1)
    local s3_latency=$(ping -c 10 s3.amazonaws.com 2>/dev/null | tail -1 | awk -F'/' '{print $5}')
    log_info "✓ 到AWS S3延迟: $s3_latency ms ⭐"
    
    # GCP GCS
    local gcs_latency=$(ping -c 10 storage.googleapis.com 2>/dev/null | tail -1 | awk -F'/' '{print $5}')
    log_info "✓ 到GCP GCS延迟: $gcs_latency ms"
    
    # 公网带宽测试
    log_info "测试公网下载带宽..."
    local download_speed=$(curl -s -w '%{speed_download}' -o /dev/null http://speedtest.tele2.net/10MB.zip)
    local download_speed_mbps=$(echo "scale=2; $download_speed * 8 / 1000000" | bc)
    log_info "✓ 公网下载带宽: $download_speed_mbps Mbps"
    
    # 保存结果
    cat > "$output_file" <<EOF
{
  "latency_to_s3_ms": $s3_latency,
  "latency_to_gcs_ms": $gcs_latency,
  "public_download_bandwidth_mbps": $download_speed_mbps
}
EOF
    
    log_info "结果已保存到: $output_file"
}

# 主函数
main() {
    log_info "========================================="
    log_info "E2B宿主机性能测试"
    log_info "========================================="
    log_info "输出目录: $OUTPUT_DIR"
    log_info ""
    
    # 检查root权限
    check_root
    
    # 安装依赖
    install_dependencies
    echo ""
    
    # 运行测试
    test_cpu_performance
    echo ""
    
    test_memory_performance
    echo ""
    
    test_hugepage_performance
    echo ""
    
    test_storage_performance
    echo ""
    
    test_network_performance
    echo ""
    
    log_info "========================================="
    log_info "所有测试完成!"
    log_info "结果保存在: $OUTPUT_DIR"
    log_info "========================================="
}

# 运行主函数
main "$@"
