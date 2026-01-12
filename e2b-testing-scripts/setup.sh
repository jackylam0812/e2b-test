#!/bin/bash
# E2B 性能测试环境设置脚本

set -e

echo "=========================================="
echo "E2B 性能测试环境设置"
echo "=========================================="
echo ""

# 检查 Python 版本
echo "[1/5] 检查 Python 版本..."
if ! python3 --version; then
    echo "错误: Python 3 未安装"
    exit 1
fi
echo "✓ Python 已安装"
echo ""

# 安装 Python 依赖
echo "[2/5] 安装 Python 依赖..."

# 检查 pip3 是否存在
if ! command -v pip3 &> /dev/null; then
    echo "⚠️  pip3 未安装"
    echo ""
    echo "请先安装 pip3:"
    echo "  Ubuntu/Debian:"
    echo "    sudo apt-get update"
    echo "    sudo apt-get install python3-pip"
    echo ""
    echo "  或使用 python3 -m pip:"
    echo "    python3 -m pip install --user -r requirements.txt"
    echo ""
    read -p "是否尝试使用 python3 -m pip 安装? [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ -f "tests/requirements.txt" ]; then
            python3 -m pip install --user -r tests/requirements.txt
            echo "✓ Python 依赖已安装 (使用 python3 -m pip)"
        else
            python3 -m pip install --user e2b pyyaml
            echo "✓ 核心依赖已安装 (使用 python3 -m pip)"
        fi
    else
        echo "⚠️  跳过依赖安装，请手动安装:"
        echo "    pip3 install -r tests/requirements.txt"
        echo "  或:"
        echo "    python3 -m pip install -r tests/requirements.txt"
    fi
else
    # pip3 存在，正常安装
    if [ -f "tests/requirements.txt" ]; then
        pip3 install -q -r tests/requirements.txt
        echo "✓ Python 依赖已安装"
    else
        echo "⚠️  未找到 tests/requirements.txt，手动安装核心依赖..."
        pip3 install -q e2b pyyaml
        echo "✓ 核心依赖已安装"
    fi
fi
echo ""

# 检查 Node.js 和 npm
echo "[3/7] 检查 Node.js 和 npm..."
REQUIRED_NODE_VERSION="18.20.8"
REQUIRED_NPM_VERSION="10.8.2"

# 检测实际用户 home 目录（处理 sudo 情况）
if [ -n "$SUDO_USER" ]; then
    REAL_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    REAL_USER="$SUDO_USER"
else
    REAL_HOME="$HOME"
    REAL_USER="$USER"
fi

# 检查并安装/更新 Node.js
if ! command -v node &> /dev/null; then
    echo "⚠️  Node.js 未安装，正在安装..."
    
    # 检查 nvm 是否安装（在用户目录下）
    NVM_DIR="$REAL_HOME/.nvm"
    if [ ! -s "$NVM_DIR/nvm.sh" ]; then
        echo "安装 nvm..."
        if [ -n "$SUDO_USER" ]; then
            # 以实际用户身份安装 nvm
            sudo -u "$REAL_USER" bash -c "export NVM_DIR=\"$NVM_DIR\" && curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
        else
            export NVM_DIR="$NVM_DIR"
            curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
        fi
    fi
    
    # 加载 nvm 并安装 Node.js
    if [ -s "$NVM_DIR/nvm.sh" ]; then
        export NVM_DIR="$NVM_DIR"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        
        echo "安装 Node.js v${REQUIRED_NODE_VERSION}..."
        if [ -n "$SUDO_USER" ]; then
            sudo -u "$REAL_USER" bash -c "export NVM_DIR=\"$NVM_DIR\" && [ -s \"\$NVM_DIR/nvm.sh\" ] && . \"\$NVM_DIR/nvm.sh\" && nvm install ${REQUIRED_NODE_VERSION} && nvm use ${REQUIRED_NODE_VERSION} && nvm alias default ${REQUIRED_NODE_VERSION}"
        else
            nvm install ${REQUIRED_NODE_VERSION}
            nvm use ${REQUIRED_NODE_VERSION}
            nvm alias default ${REQUIRED_NODE_VERSION}
        fi
        
        # 重新加载环境
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        
        if command -v node &> /dev/null; then
            NODE_VERSION=$(node --version | sed 's/v//')
            echo "✓ Node.js v${NODE_VERSION} 已安装"
            
            # 在 nvm 的 bin 目录中创建 nodejs 符号链接（如果不存在）
            NVM_NODE_BIN="$NVM_DIR/versions/node/v${NODE_VERSION}/bin"
            if [ -d "$NVM_NODE_BIN" ] && [ ! -f "$NVM_NODE_BIN/nodejs" ]; then
                if [ -n "$SUDO_USER" ]; then
                    sudo -u "$REAL_USER" ln -sf node "$NVM_NODE_BIN/nodejs" 2>/dev/null || true
                else
                    ln -sf node "$NVM_NODE_BIN/nodejs" 2>/dev/null || true
                fi
                echo "✓ 已创建 nodejs 符号链接指向 nvm 的 node"
            fi
        else
            echo "⚠️  Node.js 已安装，但当前 shell 中不可用"
            echo "    请运行: source $NVM_DIR/nvm.sh"
            echo "    或重新打开终端"
        fi
    else
        echo "✗ nvm 安装失败，请手动安装 Node.js"
        exit 1
    fi
else
    NODE_VERSION=$(node --version | sed 's/v//')
    echo "当前 Node.js 版本: v${NODE_VERSION}"
    if [ "$NODE_VERSION" != "$REQUIRED_NODE_VERSION" ]; then
        echo "⚠️  版本不匹配，需要 v${REQUIRED_NODE_VERSION}，正在更新..."
        
        # 检查 nvm 是否可用
        NVM_DIR="$REAL_HOME/.nvm"
        if [ ! -s "$NVM_DIR/nvm.sh" ]; then
            echo "未找到 nvm，正在安装..."
            if [ -n "$SUDO_USER" ]; then
                # 以实际用户身份安装 nvm
                sudo -u "$REAL_USER" bash -c "export NVM_DIR=\"$NVM_DIR\" && curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
            else
                export NVM_DIR="$NVM_DIR"
                curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
            fi
        fi
        
        if [ -s "$NVM_DIR/nvm.sh" ]; then
            export NVM_DIR="$NVM_DIR"
            [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
            
            # 使用 nvm 安装并切换版本
            echo "使用 nvm 安装 Node.js v${REQUIRED_NODE_VERSION}..."
            if [ -n "$SUDO_USER" ]; then
                sudo -u "$REAL_USER" bash -c "export NVM_DIR=\"$NVM_DIR\" && [ -s \"\$NVM_DIR/nvm.sh\" ] && . \"\$NVM_DIR/nvm.sh\" && nvm install ${REQUIRED_NODE_VERSION} && nvm use ${REQUIRED_NODE_VERSION} && nvm alias default ${REQUIRED_NODE_VERSION}"
            else
                nvm install ${REQUIRED_NODE_VERSION}
                nvm use ${REQUIRED_NODE_VERSION}
                nvm alias default ${REQUIRED_NODE_VERSION}
            fi
            
            # 重新加载环境
            [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
            
            # 验证新版本（需要重新检查，因为可能使用了新的 node）
            if command -v node &> /dev/null; then
                NEW_NODE_VERSION=$(node --version | sed 's/v//')
                if [ "$NEW_NODE_VERSION" = "$REQUIRED_NODE_VERSION" ]; then
                    echo "✓ Node.js 已更新到 v${NEW_NODE_VERSION}"
                    
                    # 在 nvm 的 bin 目录中创建 nodejs 符号链接（如果不存在）
                    NVM_NODE_BIN="$NVM_DIR/versions/node/v${REQUIRED_NODE_VERSION}/bin"
                    if [ -d "$NVM_NODE_BIN" ] && [ ! -f "$NVM_NODE_BIN/nodejs" ]; then
                        if [ -n "$SUDO_USER" ]; then
                            sudo -u "$REAL_USER" ln -sf node "$NVM_NODE_BIN/nodejs" 2>/dev/null || true
                        else
                            ln -sf node "$NVM_NODE_BIN/nodejs" 2>/dev/null || true
                        fi
                        echo "✓ 已创建 nodejs 符号链接指向 nvm 的 node"
                    fi
                else
                    echo "⚠️  Node.js 更新后版本为 v${NEW_NODE_VERSION}，期望 v${REQUIRED_NODE_VERSION}"
                    echo "    可能需要运行: source $NVM_DIR/nvm.sh"
                fi
            else
                echo "⚠️  更新完成，但当前 shell 中 node 命令不可用"
                echo "    请运行: source $NVM_DIR/nvm.sh"
            fi
        else
            echo "✗ nvm 安装失败，无法自动更新 Node.js"
            echo "    请手动安装 nvm 或使用其他方式更新 Node.js"
            echo "    推荐: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash"
            exit 1
        fi
    else
        echo "✓ Node.js 版本正确"
        
        # 确保 nodejs 符号链接存在
        NVM_NODE_BIN="$NVM_DIR/versions/node/v${REQUIRED_NODE_VERSION}/bin"
        if [ -s "$NVM_DIR/nvm.sh" ] && [ -d "$NVM_NODE_BIN" ] && [ ! -f "$NVM_NODE_BIN/nodejs" ]; then
            if [ -n "$SUDO_USER" ]; then
                sudo -u "$REAL_USER" ln -sf node "$NVM_NODE_BIN/nodejs" 2>/dev/null || true
            else
                ln -sf node "$NVM_NODE_BIN/nodejs" 2>/dev/null || true
            fi
            echo "✓ 已创建 nodejs 符号链接指向 nvm 的 node"
        fi
    fi
fi

# 检查并更新 npm
if ! command -v npm &> /dev/null; then
    echo "✗ npm 未安装"
    echo "  这通常不应该发生，因为 npm 随 Node.js 一起安装"
    echo "  请确保 Node.js 已正确安装"
    exit 1
else
    # 如果使用 nvm，确保加载了 nvm 环境（重新加载以确保使用最新版本）
    NVM_DIR="$REAL_HOME/.nvm"
    if [ -s "$NVM_DIR/nvm.sh" ]; then
        export NVM_DIR="$NVM_DIR"
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
        # 如果设置了默认版本，使用它
        if [ -n "$REQUIRED_NODE_VERSION" ]; then
            nvm use ${REQUIRED_NODE_VERSION} 2>/dev/null || true
        fi
    fi
    
    # 检查当前 Node.js 版本是否满足 npm 要求
    CURRENT_NODE_VERSION=$(node --version 2>/dev/null | sed 's/v//' || echo "")
    if [ -z "$CURRENT_NODE_VERSION" ]; then
        echo "⚠️  无法获取 Node.js 版本，跳过 npm 更新"
    else
        NODE_MAJOR=$(echo "$CURRENT_NODE_VERSION" | cut -d. -f1)
        NODE_MINOR=$(echo "$CURRENT_NODE_VERSION" | cut -d. -f2)
        
        # npm 10.8.2 需要 Node.js >= 18.17.0 或 >= 20.5.0
        NODE_VERSION_OK=false
        if [ "$NODE_MAJOR" -gt 18 ] 2>/dev/null || ([ "$NODE_MAJOR" -eq 18 ] 2>/dev/null && [ "$NODE_MINOR" -ge 17 ] 2>/dev/null) || [ "$NODE_MAJOR" -ge 20 ] 2>/dev/null; then
            NODE_VERSION_OK=true
        fi
        
        if [ "$NODE_VERSION_OK" = false ]; then
            echo "⚠️  当前 Node.js 版本 v${CURRENT_NODE_VERSION} 不满足 npm v${REQUIRED_NPM_VERSION} 的要求"
            echo "    npm v${REQUIRED_NPM_VERSION} 需要 Node.js >= 18.17.0 或 >= 20.5.0"
            echo "    请先更新 Node.js 到 v${REQUIRED_NODE_VERSION}"
            echo "    跳过 npm 更新"
        else
            NPM_VERSION=$(npm --version)
            echo "当前 npm 版本: ${NPM_VERSION}"
            if [ "$NPM_VERSION" != "$REQUIRED_NPM_VERSION" ]; then
                echo "⚠️  版本不匹配，需要 v${REQUIRED_NPM_VERSION}，正在更新..."
                
                # 更新 npm（如果使用 nvm，不需要 sudo）
                if [ -n "$SUDO_USER" ] && [ -s "$NVM_DIR/nvm.sh" ]; then
                    # 使用 nvm 时，以实际用户身份更新
                    sudo -u "$REAL_USER" bash -c "export NVM_DIR=\"$NVM_DIR\" && [ -s \"\$NVM_DIR/nvm.sh\" ] && . \"\$NVM_DIR/nvm.sh\" && npm install -g npm@${REQUIRED_NPM_VERSION}"
                else
                    npm install -g npm@${REQUIRED_NPM_VERSION}
                fi
                
                # 重新加载环境（如果使用 nvm）
                if [ -s "$NVM_DIR/nvm.sh" ]; then
                    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
                fi
                
                # 验证新版本
                if command -v npm &> /dev/null; then
                    NEW_NPM_VERSION=$(npm --version)
                    if [ "$NEW_NPM_VERSION" = "$REQUIRED_NPM_VERSION" ]; then
                        echo "✓ npm 已更新到 v${NEW_NPM_VERSION}"
                    else
                        echo "⚠️  npm 更新后版本为 v${NEW_NPM_VERSION}，期望 v${REQUIRED_NPM_VERSION}"
                        if [ -s "$NVM_DIR/nvm.sh" ]; then
                            echo "    可能需要运行: source $NVM_DIR/nvm.sh"
                        fi
                    fi
                else
                    echo "⚠️  npm 更新完成，但当前 shell 中不可用"
                    if [ -s "$NVM_DIR/nvm.sh" ]; then
                        echo "    请运行: source $NVM_DIR/nvm.sh"
                    fi
                fi
            else
                echo "✓ npm 版本正确"
            fi
        fi
    fi
fi
echo ""

# 安装 e2b CLI
echo "[4/7] 安装 e2b CLI..."
E2B_VERSION="1.4.1"

# 确保使用 nvm 的 Node.js（如果可用）
NVM_DIR="$REAL_HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    export NVM_DIR="$NVM_DIR"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    # 使用 nvm 的默认版本
    if [ -n "$REQUIRED_NODE_VERSION" ]; then
        nvm use ${REQUIRED_NODE_VERSION} 2>/dev/null || true
    fi
fi

# 检查 e2b 是否已安装且可用
E2B_AVAILABLE=false
E2B_WORKS=false
CURRENT_E2B_VERSION="unknown"
NEED_REINSTALL=false

if command -v e2b &> /dev/null; then
    E2B_AVAILABLE=true
    E2B_PATH=$(which e2b)
    
    # 尝试运行 e2b --version 检查是否正常工作
    if e2b --version >/dev/null 2>&1; then
        E2B_WORKS=true
        CURRENT_E2B_VERSION=$(e2b --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "unknown")
        echo "当前 e2b CLI 版本: ${CURRENT_E2B_VERSION}"
    else
        echo "⚠️  e2b CLI 已安装但无法运行（可能是 Node.js 版本问题）"
        NEED_REINSTALL=true
    fi
    
    # 如果使用 nvm，检查 e2b 是否在系统路径（需要重新安装）
    if [ -s "$NVM_DIR/nvm.sh" ] && [ -f "$E2B_PATH" ]; then
        # 如果 e2b 在 /usr/local/bin，说明是系统安装的，需要重新安装
        if echo "$E2B_PATH" | grep -q "/usr/local/bin"; then
            echo "⚠️  检测到 e2b CLI 使用系统 Node.js，需要重新安装以使用 nvm 的 Node.js"
            NEED_REINSTALL=true
        fi
    fi
fi

# 如果版本不匹配或需要重新安装，则安装/更新
if [ "$NEED_REINSTALL" = true ] || [ "$E2B_AVAILABLE" = false ] || [ "$CURRENT_E2B_VERSION" != "$E2B_VERSION" ]; then
    if [ "$E2B_AVAILABLE" = true ] && [ "$NEED_REINSTALL" = false ]; then
        echo "更新 e2b CLI 到 v${E2B_VERSION}..."
    else
        if [ "$NEED_REINSTALL" = true ]; then
            echo "重新安装 e2b CLI 以使用正确的 Node.js 版本..."
        else
            echo "安装 e2b CLI v${E2B_VERSION}..."
        fi
    fi
    
    # 如果使用 nvm 或需要重新安装，先卸载旧版本
    if [ -s "$NVM_DIR/nvm.sh" ] && [ "$NEED_REINSTALL" = true ]; then
        echo "卸载旧的 e2b CLI..."
        # 使用 nvm 的 npm 卸载（如果可用）
        if [ -n "$SUDO_USER" ]; then
            sudo -u "$REAL_USER" bash -c "export NVM_DIR=\"$NVM_DIR\" && [ -s \"\$NVM_DIR/nvm.sh\" ] && . \"\$NVM_DIR/nvm.sh\" && nvm use ${REQUIRED_NODE_VERSION} 2>/dev/null && npm uninstall -g @e2b/cli 2>/dev/null || true"
        else
            export NVM_DIR="$NVM_DIR"
            [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
            nvm use ${REQUIRED_NODE_VERSION} 2>/dev/null || true
            npm uninstall -g @e2b/cli 2>/dev/null || true
        fi
        # 也尝试删除系统安装的版本和目录
        if [ -f "/usr/local/bin/e2b" ]; then
            sudo rm -f /usr/local/bin/e2b 2>/dev/null || true
        fi
        if [ -d "/usr/local/lib/node_modules/@e2b" ]; then
            sudo rm -rf /usr/local/lib/node_modules/@e2b 2>/dev/null || true
        fi
    elif [ "$E2B_AVAILABLE" = true ] && [ "$CURRENT_E2B_VERSION" != "$E2B_VERSION" ]; then
        # 只是版本更新，也先卸载
        echo "卸载旧版本..."
        if [ -n "$SUDO_USER" ] && [ -s "$NVM_DIR/nvm.sh" ]; then
            sudo -u "$REAL_USER" bash -c "export NVM_DIR=\"$NVM_DIR\" && [ -s \"\$NVM_DIR/nvm.sh\" ] && . \"\$NVM_DIR/nvm.sh\" && nvm use ${REQUIRED_NODE_VERSION} 2>/dev/null && npm uninstall -g @e2b/cli 2>/dev/null || true"
        else
            npm uninstall -g @e2b/cli 2>/dev/null || true
        fi
    fi
    
    # 使用 nvm 的 npm 安装（如果可用）
    if [ -n "$SUDO_USER" ] && [ -s "$NVM_DIR/nvm.sh" ]; then
        # 以实际用户身份安装，使用 nvm 的 Node.js
        sudo -u "$REAL_USER" bash -c "export NVM_DIR=\"$NVM_DIR\" && [ -s \"\$NVM_DIR/nvm.sh\" ] && . \"\$NVM_DIR/nvm.sh\" && nvm use ${REQUIRED_NODE_VERSION} 2>/dev/null && npm install -g @e2b/cli@${E2B_VERSION}"
    else
        npm install -g @e2b/cli@${E2B_VERSION}
    fi
    
    # 重新加载环境
    if [ -s "$NVM_DIR/nvm.sh" ]; then
        [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    fi
    
    # 验证安装
    if command -v e2b &> /dev/null && e2b --version >/dev/null 2>&1; then
        NEW_VERSION=$(e2b --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1 || echo "unknown")
        echo "✓ e2b CLI 已安装/更新 (版本: ${NEW_VERSION})"
    else
        echo "⚠️  e2b CLI 安装完成，但可能需要重新加载环境"
        echo "    请运行: source $NVM_DIR/nvm.sh"
        echo "    或重新打开终端"
    fi
else
    echo "✓ e2b CLI 版本正确"
fi
echo ""

# 检查系统工具
echo "[5/7] 检查系统工具..."

# 检查是否为 root 或有 sudo 权限
if [ "$EUID" -ne 0 ]; then
    echo "注意: 某些系统工具需要 root 权限安装"
    SUDO="sudo"
else
    SUDO=""
fi

# 询问是否安装系统工具
echo ""
read -p "是否安装系统性能测试工具 (sysbench, fio, iperf3)? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "安装系统工具..."
    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq sysbench fio iperf3
    echo "✓ 系统工具已安装"
else
    echo "跳过系统工具安装"
    echo "注意: 宿主机性能测试将需要这些工具"
fi
echo ""

# 检查 Nomad CLI
echo "[6/7] 检查 Nomad CLI..."
if command -v nomad &> /dev/null; then
    echo "✓ Nomad CLI 已安装"
    nomad version
else
    echo "⚠️  Nomad CLI 未安装"
    echo ""
    read -p "是否安装 Nomad CLI? (用于冷启动测试) [y/N] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "下载并安装 Nomad CLI..."
        NOMAD_VERSION="1.9.7"
        wget -q "https://releases.hashicorp.com/nomad/${NOMAD_VERSION}/nomad_${NOMAD_VERSION}_linux_amd64.zip"
        unzip -q "nomad_${NOMAD_VERSION}_linux_amd64.zip"
        $SUDO mv nomad /usr/local/bin/
        rm "nomad_${NOMAD_VERSION}_linux_amd64.zip"
        echo "✓ Nomad CLI 已安装"
        nomad version
    else
        echo "跳过 Nomad CLI 安装"
        echo "注意: 冷启动测试将需要 Nomad CLI"
    fi
fi
echo ""

# 创建必要的目录
echo "[7/7] 创建目录结构..."
mkdir -p env
mkdir -p outputs
mkdir -p reports
echo "✓ 目录结构已创建"
echo ""

# 检查环境变量配置
echo "检查环境变量配置..."
if [ -f "env/.e2b_env.template" ]; then
    echo "✓ 找到环境变量模板: env/.e2b_env.template"

    if [ ! -f "env/.e2b_env" ]; then
        echo ""
        echo "⚠️  未找到环境变量配置文件"
        echo ""
        echo "请按以下步骤配置环境变量："
        echo "  1. 复制模板文件:"
        echo "     cp env/.e2b_env.template env/.e2b_env"
        echo ""
        echo "  2. 编辑配置文件填入你的实际配置:"
        echo "     vim env/.e2b_env"
        echo ""
        echo "  3. 加载环境变量:"
        echo "     source env/.e2b_env"
        echo ""
    else
        echo "✓ 环境变量配置文件已存在: env/.e2b_env"
    fi
else
    echo "⚠️  未找到环境变量模板: env/.e2b_env.template"
fi
echo ""

# 设置脚本可执行权限
echo "设置脚本可执行权限..."
if [ -d "tests" ]; then
    # 设置 Python 脚本权限
    if ls tests/*.py 1> /dev/null 2>&1; then
        chmod +x tests/*.py
    fi
    # 设置 shell 脚本权限
    if ls tests/*.sh 1> /dev/null 2>&1; then
        chmod +x tests/*.sh
    fi
    # 递归设置子目录中的脚本权限
    find tests -type f -name "*.py" -exec chmod +x {} \; 2>/dev/null || true
    find tests -type f -name "*.sh" -exec chmod +x {} \; 2>/dev/null || true
    echo "✓ 权限已设置"
else
    echo "⚠️  tests 目录不存在，跳过权限设置"
fi
echo ""

# 完成
echo "=========================================="
echo "✅ 环境设置完成!"
echo "=========================================="
echo ""

# 检查 nvm 环境
NVM_DIR="$REAL_HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    echo "⚠️  重要提示: Node.js 环境配置"
    echo ""
    echo "nvm 已安装 Node.js v${REQUIRED_NODE_VERSION}，但当前 shell 可能未加载 nvm 环境。"
    echo ""
    echo "要使用正确的 Node.js 版本，请执行以下操作之一:"
    echo ""
    echo "  方法 1 (推荐): 重新打开终端，nvm 会自动加载"
    echo ""
    echo "  方法 2: 在当前终端运行:"
    echo "    source ~/.nvm/nvm.sh"
    echo "    nvm use ${REQUIRED_NODE_VERSION}"
    echo ""
    echo "  方法 3: 运行以下命令加载环境:"
    echo "    source ~/.bashrc"
    echo ""
    echo "验证 Node.js 版本:"
    echo "    node -v    # 应该显示 v${REQUIRED_NODE_VERSION}"
    echo ""
    echo "注意: 'nodejs' 命令可能仍指向系统版本，建议使用 'node' 命令"
    echo ""
fi

echo "下一步:"
echo "  1. 编辑 env/.e2b_env 文件填入你的配置"
echo "  2. 运行: source env/.e2b_env"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    echo "  3. 确保已加载 nvm 环境 (运行: source ~/.nvm/nvm.sh)"
    echo "  4. 运行测试: python3 tests/client/run_all_tests.py"
else
    echo "  3. 运行测试: python3 tests/client/run_all_tests.py"
fi
echo ""
echo "查看完整文档: README.md"
echo ""
