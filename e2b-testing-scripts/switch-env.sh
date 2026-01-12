#!/bin/bash
# E2B 环境切换脚本
# 统一管理环境变量和E2B模板配置

set -e

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="$PROJECT_ROOT/env"
E2B_TEMPLATE_DIR="$PROJECT_ROOT/e2b-template"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 列出所有可用环境
list_environments() {
    echo -e "\n${BLUE}可用环境列表：${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    for env_file in "$ENV_DIR"/.e2b_env_*; do
        if [ -f "$env_file" ]; then
            env_name=$(basename "$env_file" | sed 's/^\.e2b_env_//')
            toml_file="$E2B_TEMPLATE_DIR/e2b.toml.$env_name"
            
            if [ -f "$toml_file" ]; then
                echo -e "  ${GREEN}✓${NC} $env_name"
            else
                echo -e "  ${YELLOW}⚠${NC} $env_name ${YELLOW}(缺少e2b.toml.$env_name)${NC}"
            fi
        fi
    done
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# 显示当前环境
show_current() {
    echo -e "\n${BLUE}当前环境信息：${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    if [ -f "$E2B_TEMPLATE_DIR/e2b.toml" ]; then
        print_success "E2B模板配置: e2b-template/e2b.toml"
        
        # 提取模板信息
        if command -v grep >/dev/null 2>&1; then
            template_name=$(grep "^template_name" "$E2B_TEMPLATE_DIR/e2b.toml" | cut -d'"' -f2 2>/dev/null || echo "未知")
            template_id=$(grep "^template_id" "$E2B_TEMPLATE_DIR/e2b.toml" | cut -d'"' -f2 2>/dev/null || echo "未知")
            echo "  模板名称: $template_name"
            echo "  模板ID: $template_id"
        fi
    else
        print_warning "E2B模板配置: 未设置"
    fi
    
    echo ""
    
    if [ -n "$E2B_DOMAIN" ]; then
        print_success "环境变量: 已加载"
        echo "  E2B_DOMAIN: $E2B_DOMAIN"
        echo "  E2B_TEMPLATE_NAME: ${E2B_TEMPLATE_NAME:-未设置}"
        echo "  CLOUD_PROVIDER: ${CLOUD_PROVIDER:-未设置}"
    else
        print_warning "环境变量: 未加载"
    fi
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# 切换环境
switch_environment() {
    local env_name="$1"
    
    # 检查环境文件是否存在
    local env_file="$ENV_DIR/.e2b_env_$env_name"
    local toml_file="$E2B_TEMPLATE_DIR/e2b.toml.$env_name"
    local env_template="$ENV_DIR/.e2b_env.template"

    # 检查环境文件是否存在
    local env_file="$ENV_DIR/.e2b_env_$env_name"
    local toml_file="$E2B_TEMPLATE_DIR/e2b.toml.$env_name"
    local env_template="$ENV_DIR/.e2b_env.template"

    # 1. 检查 E2B 配置文件（不自动创建）
    if [ ! -f "$toml_file" ]; then
        print_error "E2B配置文件不存在: $toml_file"
        echo ""
        print_info "请先创建 E2B 配置文件："
        echo "  1. 从模板复制: cp e2b-template/e2b.toml.template e2b-template/e2b.toml.$env_name"
        echo "  2. 或从现有配置复制: cp e2b-template/e2b.toml.azure e2b-template/e2b.toml.$env_name"
        echo "  3. 编辑配置: vim e2b-template/e2b.toml.$env_name"
        echo "  4. 再次切换: ./switch-env.sh $env_name"
        echo ""
        list_environments
        exit 1
    fi

    # 2. 检查环境变量文件（自动从模板创建）
    if [ ! -f "$env_file" ]; then
        if [ -f "$env_template" ]; then
            print_warning "环境变量文件不存在: $env_file"
            echo ""
            print_info "正在从模板自动创建..."
            cp "$env_template" "$env_file"
            print_success "已从模板创建: $env_file"
            echo ""
            print_warning "⚠️  请编辑此文件填入 $env_name 环境的实际配置："
            echo "  vim $env_file"
            echo ""
            read -p "是否现在编辑配置文件? [y/N] " -n 1 -r
            echo ""
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                ${EDITOR:-vim} "$env_file"
            fi
            echo ""
        else
            print_error "环境变量文件不存在: $env_file"
            print_error "模板文件也不存在: $env_template"
            echo ""
            exit 1
        fi
    fi
    
    echo ""
    print_info "正在切换到环境: $env_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    
    # 1. 复制E2B模板配置
    print_info "复制E2B模板配置..."
    cp "$toml_file" "$E2B_TEMPLATE_DIR/e2b.toml"
    print_success "已复制: e2b.toml.$env_name -> e2b.toml"

    # 2. 创建环境变量符号链接
    print_info "更新环境变量链接..."
    ln -sf ".e2b_env_$env_name" "$ENV_DIR/.e2b_env"
    print_success "已更新: .e2b_env -> .e2b_env_$env_name"
    
    # 3. 提示加载环境变量
    echo ""
    print_info "加载环境变量..."
    echo -e "${YELLOW}"
    echo "请在当前shell中运行以下命令来加载环境变量："
    echo ""
    echo "  source env/.e2b_env"
    echo ""
    echo "或者使用以下命令在新shell中自动加载："
    echo "  bash -c 'source env/.e2b_env && bash'"
    echo -e "${NC}"
    
    # 4. 显示环境信息
    echo ""
    print_success "环境切换完成！"
    echo ""

    # 显示模板信息
    if command -v grep >/dev/null 2>&1; then
        template_name=$(grep "^template_name" "$E2B_TEMPLATE_DIR/e2b.toml" | cut -d'"' -f2 2>/dev/null || echo "未知")
        template_id=$(grep "^template_id" "$E2B_TEMPLATE_DIR/e2b.toml" | cut -d'"' -f2 2>/dev/null || echo "未知")
        echo "当前E2B模板配置："
        echo "  模板名称: $template_name"
        echo "  模板ID: $template_id"
    fi

    echo ""
    print_info "下一步操作："
    echo "  1. 加载环境变量: source env/.e2b_env"
    echo "  2. 构建E2B模板: cd e2b-template && e2b template build"
    echo "  3. 运行测试: python3 tests/client/run_all_tests.py"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# 使用说明
show_usage() {
    cat << EOF

E2B 环境切换脚本
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

用法:
  ./switch-env.sh <环境名称>     切换到指定环境
  ./switch-env.sh --list         列出所有可用环境
  ./switch-env.sh --current      显示当前环境
  ./switch-env.sh --help         显示此帮助信息

示例:
  ./switch-env.sh awsdev         切换到AWS开发环境
  ./switch-env.sh azure          切换到Azure环境

环境配置对应关系:
  环境名称 → 环境变量文件                  → E2B模板配置
  ────────────────────────────────────────────────────
  awsdev  → env/.e2b_env_awsdev     → e2b-template/e2b.toml.awsdev
  azure   → env/.e2b_env_azure      → e2b-template/e2b.toml.azure

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF
}

# 主函数
main() {
    case "${1:-}" in
        --list|-l)
            list_environments
            ;;
        --current|-c)
            show_current
            ;;
        --help|-h|"")
            show_usage
            ;;
        *)
            switch_environment "$1"
            ;;
    esac
}

main "$@"
