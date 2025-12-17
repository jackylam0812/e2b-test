#!/bin/bash
# E2B 模板构建测试脚本
# 测试指标：模板构建时间

set -e

echo "=========================================="
echo "E2B 模板构建测试"
echo "=========================================="
echo ""

# 配置参数
TEMPLATE_NAME="agent_test"
MEMORY_MB=4096
CPU_COUNT=6
DOCKERFILE="e2b.Dockerfile"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "配置信息:"
echo "  模板名称: $TEMPLATE_NAME"
echo "  内存配置: ${MEMORY_MB}MB"
echo "  CPU核心: $CPU_COUNT"
echo "  Dockerfile: $DOCKERFILE"
echo "  项目目录: $PROJECT_ROOT"
echo ""

# 切换到项目根目录
cd "$PROJECT_ROOT"

# 检查 Dockerfile 是否存在
if [ ! -f "$DOCKERFILE" ]; then
    echo "✗ 错误: Dockerfile 不存在: $DOCKERFILE"
    exit 1
fi

# 检查 e2b CLI 是否安装
if ! command -v e2b &> /dev/null; then
    echo "✗ 错误: e2b CLI 未安装"
    echo "请运行: npm install -g @e2b/cli"
    exit 1
fi

echo "✓ 环境检查通过"
echo ""

# 创建临时配置文件
TEMP_CONFIG="e2b.test.toml"
echo "创建测试配置文件: $TEMP_CONFIG"
cat > "$TEMP_CONFIG" << EOF
# E2B 测试模板配置
# 自动生成 - 请勿手动编辑

memory_mb = ${MEMORY_MB}
cpu_count = ${CPU_COUNT}
dockerfile = "${DOCKERFILE}"
template_name = "${TEMPLATE_NAME}"
EOF

echo "✓ 配置文件已创建"
echo ""

# 显示配置内容
echo "配置文件内容:"
cat "$TEMP_CONFIG"
echo ""

# 开始构建
echo "=========================================="
echo "开始构建模板..."
echo "=========================================="
echo ""

BUILD_START=$(date +%s)

# 执行构建命令
echo "执行命令: e2b template build --config $TEMP_CONFIG"
echo ""

if e2b template build --config "$TEMP_CONFIG"; then
    BUILD_END=$(date +%s)
    BUILD_TIME=$((BUILD_END - BUILD_START))

    echo ""
    echo "=========================================="
    echo "✓ 模板构建成功!"
    echo "=========================================="
    echo ""
    echo "构建耗时: ${BUILD_TIME} 秒 ($(echo "scale=2; $BUILD_TIME / 60" | bc) 分钟)"
    echo ""

    # 获取模板信息
    echo "模板信息:"
    e2b template list | grep "$TEMPLATE_NAME" || echo "  (无法获取模板列表)"
    echo ""

    # 生成测试结果 JSON
    RESULT_FILE="outputs/template_build_${TEMPLATE_NAME}.json"
    mkdir -p outputs
    cat > "$RESULT_FILE" << EOFJ
{
  "template_name": "${TEMPLATE_NAME}",
  "build_time_seconds": ${BUILD_TIME},
  "memory_mb": ${MEMORY_MB},
  "cpu_count": ${CPU_COUNT},
  "dockerfile": "${DOCKERFILE}",
  "build_date": "$(date -Iseconds)",
  "status": "success"
}
EOFJ

    echo "测试结果已保存到: $RESULT_FILE"
    echo ""
    cat "$RESULT_FILE"
    echo ""

    # 可选：测试创建沙箱
    echo "=========================================="
    echo "测试创建沙箱..."
    echo "=========================================="
    echo ""

    CREATE_SCRIPT=$(cat << 'EOFPY'
import sys
import time
from e2b import Sandbox

template_name = sys.argv[1]

print(f"正在创建沙箱: {template_name}")
start = time.time()

try:
    sandbox = Sandbox(template_name)
    create_time = time.time() - start

    print(f"✓ 沙箱创建成功!")
    print(f"  Sandbox ID: {sandbox.sandbox_id}")
    print(f"  创建耗时: {create_time:.2f} 秒")

    # 简单测试
    result = sandbox.commands.run("echo 'Hello from agent_test!'")
    print(f"  测试输出: {result.stdout.strip()}")

    sandbox.kill()
    print(f"✓ 沙箱已关闭")

except Exception as e:
    print(f"✗ 沙箱创建失败: {e}")
    sys.exit(1)
EOFPY
)

    echo "$CREATE_SCRIPT" | python3 - "$TEMPLATE_NAME"

else
    BUILD_END=$(date +%s)
    BUILD_TIME=$((BUILD_END - BUILD_START))

    echo ""
    echo "=========================================="
    echo "✗ 模板构建失败"
    echo "=========================================="
    echo ""
    echo "构建耗时: ${BUILD_TIME} 秒"

    # 生成失败结果 JSON
    RESULT_FILE="outputs/template_build_${TEMPLATE_NAME}_failed.json"
    mkdir -p outputs
    cat > "$RESULT_FILE" << EOFJ
{
  "template_name": "${TEMPLATE_NAME}",
  "build_time_seconds": ${BUILD_TIME},
  "memory_mb": ${MEMORY_MB},
  "cpu_count": ${CPU_COUNT},
  "dockerfile": "${DOCKERFILE}",
  "build_date": "$(date -Iseconds)",
  "status": "failed"
}
EOFJ

    echo "失败日志已保存到: $RESULT_FILE"

    # 清理临时文件
    rm -f "$TEMP_CONFIG"
    exit 1
fi

# 清理临时文件
echo "清理临时文件..."
rm -f "$TEMP_CONFIG"
echo "✓ 清理完成"
echo ""

echo "=========================================="
echo "测试完成!"
echo "=========================================="
