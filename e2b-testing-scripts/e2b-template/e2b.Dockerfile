# syntax=docker/dockerfile:1
#
# 文件管理服务 Dockerfile - 多阶段构建（优化版）
# 优化内容：
#   - 删除 apt 缓存保留，减少 2-3GB
#   - 合并 RUN 命令，减少 layer 数量
#   - 移除重复的 chromium-browser，只保留 Playwright Chromium
#   - 添加完整的清理步骤
#   - 优化 Python 包安装缓存
#
# 构建命令：
#   docker build -t file-manager-service:latest .

# ============================================
# 第一阶段：构建 e2b 基础环境
# ============================================
FROM --platform=linux/amd64 ubuntu:22.04 AS base

ARG RUNTIME_USER=ubuntu

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:0 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC \
    UV_LINK_MODE=copy \
    UV_PYTHON_CACHE_DIR=/tmp/uv-cache \
    PLAYWRIGHT_BROWSERS_PATH=/home/ubuntu/.cache/ms-playwright

# 🎯 优化点 1：删除 apt 缓存保留配置（原 line 24-25）
# 这是导致 3.9GB layer 的主要原因

# 🎯 优化点 2：在同一个 RUN 中完成所有 apt 操作并清理
# 合并源添加和软件包安装，最后清理缓存
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    wget \
    git \
    gnupg \
    gnupg2 \
    apt-transport-https \
    && \
    # 添加 Chromium PPA 源（虽然我们不安装 chromium-browser，但保留源以防需要）
    echo "deb http://ppa.launchpad.net/savoury1/chromium/ubuntu jammy main" > /etc/apt/sources.list.d/savoury1-chromium.list && \
    curl -fsSL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0xE996735927E427A733BB653E374C7797FB006459" | gpg --dearmor -o /etc/apt/trusted.gpg.d/savoury1-chromium.gpg && \
    # 添加 GitHub CLI 源
    install -d -m 0755 /etc/apt/keyrings && \
    curl -fsSL -o /etc/apt/keyrings/githubcli-archive-keyring.gpg https://cli.github.com/packages/githubcli-archive-keyring.gpg && \
    chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg && \
    install -d -m 0755 /etc/apt/sources.list.d && \
    printf 'deb [arch=%s signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main\n' "$(dpkg --print-architecture)" > /etc/apt/sources.list.d/github-cli.list && \
    # 更新源列表并安装所有软件包
    apt-get update && apt-get install -y --no-install-recommends \
    sudo \
    net-tools \
    less \
    psmisc \
    poppler-utils \
    unzip \
    zip \
    tar \
    supervisor \
    gzip \
    vim \
    nano \
    tini \
    libgtk2.0-0 \
    libgtk-3-0 \
    libgbm-dev \
    libnotify-dev \
    libnss3 libxss1 libasound2 libxtst6 xauth \
    python3.11 \
    python3.11-venv \
    python3-pip \
    openbox \
    xvfb \
    x11vnc \
    xterm \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    libxshmfence1 \
    xdg-utils \
    mesa-utils \
    mesa-vulkan-drivers \
    vulkan-tools \
    dbus \
    dbus-x11 \
    x11-xserver-utils \
    fonts-liberation \
    fonts-noto-cjk \
    fonts-noto-cjk-extra \
    fonts-ipafont-gothic \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    fonts-droid-fallback \
    fonts-noto \
    fonts-noto-extra \
    fonts-noto-color-emoji \
    fonts-sil-abyssinica \
    fonts-sil-padauk \
    fonts-lohit-deva \
    fonts-lohit-gujr \
    fonts-lohit-taml \
    fonts-hosny-amiri \
    fonts-sil-scheherazade \
    fonts-thai-tlwg \
    socat \
    bc \
    make \
    file \
    xdotool \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libharfbuzz0b \
    default-jre \
    graphviz \
    libreoffice \
    libffi-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    ffmpeg \
    lsof \
    patch \
    tree \
    mysql-client \
    gh \
    jq \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-tools \
    pulseaudio \
    pulseaudio-utils \
    libxcvt0 \
    libxcb-xinerama0 \
    libxcb-shape0 \
    libxcb-randr0 \
    libx11-xcb1 \
    libxcursor1 \
    xclip \
    xserver-xorg-core \
    xserver-xorg-video-dummy \
    xserver-xorg-input-evdev \
    xserver-xorg-input-libinput \
    xinit \
    xauth \
    xutils-dev \
    libx11-dev xorg-dev libxi-dev libxrandr-dev libxfixes-dev libxtst-dev \
    && \
    # 🎯 优化点 3：移除 chromium-browser（~300MB），只保留 Playwright Chromium
    # 🎯 优化点 4：清理 apt 缓存和临时文件（减少 2-3GB）
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* \
           /var/cache/apt/archives/* \
           /tmp/* \
           /var/tmp/*

# 🎯 优化点 5：合并工具安装到一个 RUN 命令中
# 安装 uv, D2, plantuml, code-server, rclone
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN set -ex && \
    # 安装 D2 图表渲染工具
    curl -fsSL https://d2lang.com/install.sh | sh -s -- && \
    # 下载 plantuml jar
    wget -O /usr/local/bin/plantuml-1.2025.4.jar https://github.com/plantuml/plantuml/releases/download/v1.2025.4/plantuml-1.2025.4.jar && \
    chmod 755 /usr/local/bin/plantuml-1.2025.4.jar && \
    # 安装 code-server
    curl -fsSL https://code-server.dev/install.sh | sh && \
    which code-server && \
    test -f $(which code-server) && \
    # 安装 rclone
    curl https://rclone.org/install.sh | bash && \
    # 安装 Node Exporter
    NODE_EXPORTER_VERSION=1.8.2 && \
    wget https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz && \
    tar xvfz node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz && \
    mv node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64/node_exporter /usr/local/bin/ && \
    chmod +x /usr/local/bin/node_exporter && \
    # 🎯 优化点 6：清理下载的临时文件
    rm -rf node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64* \
           /tmp/* \
           /var/tmp/* \
           /root/.cache

# create python to python3 link
RUN ln -s /usr/bin/python3.11 /usr/bin/python && \
    ln -sf /usr/bin/python3.11 /usr/bin/python3

# 🎯 优化点 7：Python 包安装后清理缓存
# 注意：fastapi 和 uvicorn 已移到 requirements.txt 中管理，避免版本冲突
RUN UV_SYSTEM_PYTHON=true uv pip install --no-cache --only-binary=pycairo \
    requests matplotlib \
    reportlab xhtml2pdf fpdf fpdf2 weasyprint pandas numpy playwright \
    beautifulsoup4 flask markdown openpyxl pdf2image pillow plotly seaborn tabulate tqdm \
    git-remote-s3 openai && \
    rm -rf /tmp/uv-cache \
           /root/.cache/uv \
           /tmp/* \
           /var/tmp/*

# Create ubuntu user and setup sudo
RUN useradd -m -s /bin/bash ubuntu && \
    echo "ubuntu ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu && \
    chmod 0440 /etc/sudoers.d/ubuntu && \
    mkdir -p /home/ubuntu/.cache/uv && \
    touch /home/ubuntu/.bashrc /home/ubuntu/.user_env && \
    chown -R ubuntu:ubuntu /home/ubuntu

# 🎯 优化点 8：安装 Playwright Chromium 并清理缓存
# 只保留 Playwright Chromium，不安装系统 chromium-browser
RUN su - ubuntu -c "PLAYWRIGHT_BROWSERS_PATH=/home/ubuntu/.cache/ms-playwright playwright install chromium" && \
    chown -R ubuntu:ubuntu /home/ubuntu/.cache && \
    rm -rf /tmp/* /var/tmp/* /home/ubuntu/.cache/uv

# ============================================
# 第二阶段：构建应用镜像
# ============================================
FROM base AS app

# 切换到 root 用户安装依赖
USER root

# 设置工作目录
WORKDIR /home/ubuntu

# 复制 requirements.txt 并安装应用特定的 Python 依赖
COPY requirements.txt .

# 🎯 优化点 9：使用 --no-cache 安装依赖并清理
RUN UV_SYSTEM_PYTHON=true uv pip install --no-cache -r requirements.txt && \
    rm -rf /tmp/uv-cache \
           /root/.cache/uv \
           /tmp/* \
           /var/tmp/*

# 复制应用代码
COPY app.py .
COPY load_controller.py .

# 设置执行权限
RUN chmod +x load_controller.py

# 🎯 优化点 10：合并 supervisor 配置创建到一个 RUN 命令
RUN mkdir -p /etc/supervisor/conf.d /var/log/supervisor && \
    # 创建 supervisor 主配置
    echo '[supervisord]' > /etc/supervisor/supervisord.conf && \
    echo 'nodaemon=true' >> /etc/supervisor/supervisord.conf && \
    echo 'user=root' >> /etc/supervisor/supervisord.conf && \
    echo 'logfile=/var/log/supervisor/supervisord.log' >> /etc/supervisor/supervisord.conf && \
    echo 'pidfile=/var/run/supervisord.pid' >> /etc/supervisor/supervisord.conf && \
    echo '' >> /etc/supervisor/supervisord.conf && \
    echo '[supervisorctl]' >> /etc/supervisor/supervisord.conf && \
    echo 'serverurl=unix:///var/run/supervisor.sock' >> /etc/supervisor/supervisord.conf && \
    echo '' >> /etc/supervisor/supervisord.conf && \
    echo '[unix_http_server]' >> /etc/supervisor/supervisord.conf && \
    echo 'file=/var/run/supervisor.sock' >> /etc/supervisor/supervisord.conf && \
    echo '' >> /etc/supervisor/supervisord.conf && \
    echo '[rpcinterface:supervisor]' >> /etc/supervisor/supervisord.conf && \
    echo 'supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface' >> /etc/supervisor/supervisord.conf && \
    echo '' >> /etc/supervisor/supervisord.conf && \
    echo '[include]' >> /etc/supervisor/supervisord.conf && \
    echo 'files=/etc/supervisor/conf.d/*.conf' >> /etc/supervisor/supervisord.conf && \
    # FastAPI 应用配置（OOM score 从 supervisor 继承）
    echo '[program:fastapi]' > /etc/supervisor/conf.d/fastapi.conf && \
    echo 'command=/usr/bin/python3 -m uvicorn app:app --host 0.0.0.0 --port 8080' >> /etc/supervisor/conf.d/fastapi.conf && \
    echo 'directory=/home/ubuntu' >> /etc/supervisor/conf.d/fastapi.conf && \
    echo 'user=ubuntu' >> /etc/supervisor/conf.d/fastapi.conf && \
    echo 'environment=PLAYWRIGHT_BROWSERS_PATH="/home/ubuntu/.cache/ms-playwright"' >> /etc/supervisor/conf.d/fastapi.conf && \
    echo 'autostart=true' >> /etc/supervisor/conf.d/fastapi.conf && \
    echo 'autorestart=true' >> /etc/supervisor/conf.d/fastapi.conf && \
    echo 'stdout_logfile=/var/log/fastapi.log' >> /etc/supervisor/conf.d/fastapi.conf && \
    echo 'stderr_logfile=/var/log/fastapi.err.log' >> /etc/supervisor/conf.d/fastapi.conf && \
    echo 'priority=100' >> /etc/supervisor/conf.d/fastapi.conf && \
    # Node Exporter 配置（OOM score 从 supervisor 继承）
    echo '[program:node_exporter]' > /etc/supervisor/conf.d/node_exporter.conf && \
    echo 'command=/usr/local/bin/node_exporter' >> /etc/supervisor/conf.d/node_exporter.conf && \
    echo 'user=root' >> /etc/supervisor/conf.d/node_exporter.conf && \
    echo 'autostart=true' >> /etc/supervisor/conf.d/node_exporter.conf && \
    echo 'autorestart=true' >> /etc/supervisor/conf.d/node_exporter.conf && \
    echo 'stdout_logfile=/var/log/node_exporter.log' >> /etc/supervisor/conf.d/node_exporter.conf && \
    echo 'stderr_logfile=/var/log/node_exporter.err.log' >> /etc/supervisor/conf.d/node_exporter.conf && \
    echo 'priority=50' >> /etc/supervisor/conf.d/node_exporter.conf && \
    # Load Controller 配置（OOM score 从 supervisor 继承）
    echo '[program:load_controller]' > /etc/supervisor/conf.d/load_controller.conf && \
    echo 'command=/usr/bin/python3 /home/ubuntu/load_controller.py' >> /etc/supervisor/conf.d/load_controller.conf && \
    echo 'directory=/home/ubuntu' >> /etc/supervisor/conf.d/load_controller.conf && \
    echo 'user=root' >> /etc/supervisor/conf.d/load_controller.conf && \
    echo 'autostart=true' >> /etc/supervisor/conf.d/load_controller.conf && \
    echo 'autorestart=true' >> /etc/supervisor/conf.d/load_controller.conf && \
    echo 'stdout_logfile=/var/log/load_controller.log' >> /etc/supervisor/conf.d/load_controller.conf && \
    echo 'stderr_logfile=/var/log/load_controller.err.log' >> /etc/supervisor/conf.d/load_controller.conf && \
    echo 'priority=200' >> /etc/supervisor/conf.d/load_controller.conf && \
    echo 'startsecs=10' >> /etc/supervisor/conf.d/load_controller.conf && \
    # 创建日志文件（FastAPI 以 ubuntu 用户运行，其他服务以 root 运行）
    touch /var/log/fastapi.log /var/log/fastapi.err.log && \
    touch /var/log/node_exporter.log /var/log/node_exporter.err.log && \
    touch /var/log/load_controller.log /var/log/load_controller.err.log && \
    chown ubuntu:ubuntu /var/log/fastapi.log /var/log/fastapi.err.log && \
    chmod 644 /var/log/fastapi.log /var/log/fastapi.err.log && \
    chmod 644 /var/log/node_exporter.log /var/log/node_exporter.err.log && \
    chmod 644 /var/log/load_controller.log /var/log/load_controller.err.log && \
    # 创建初始配置文件
    echo '{"target_cpu": 50.0, "target_memory": 50.0, "target_disk": 30.0, "created_at": "auto"}' > /tmp/load_controller_config.json && \
    chown ubuntu:ubuntu /tmp/load_controller_config.json && \
    # 修改文件所有权
    chown -R ubuntu:ubuntu /home/ubuntu

# 暴露端口
EXPOSE 8080 9100

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# 设置 OOM score 后启动 supervisor（所有子进程继承此设置）
CMD ["/bin/bash", "-c", "echo -500 > /proc/self/oom_score_adj && exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf"]
