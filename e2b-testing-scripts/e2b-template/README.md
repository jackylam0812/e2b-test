# 文件管理服务

> 基于Python + FastAPI的异步文件管理服务，支持并发安全操作

**创建时间**: 2025-12-01
**时区**: UTC+8
e2b tpl bd -n agent_test --cpu-count 6 --memory-mb 4096
---

## 📋 项目简介

本服务是一个运行在Docker容器中的HTTP服务器，提供文件管理和模拟新闻内容生成功能。采用Python异步编程模型，使用FastAPI框架实现，支持高并发请求处理。

### 核心特性

- ✅ **异步架构**: 基于FastAPI + uvicorn，支持高并发
- ✅ **无锁设计**: 最大化并发性能，无等待，无阻塞
- ✅ **容器化**: Docker部署，使用ubuntu非特权用户运行
- ✅ **自动管理**: 文件数量超过10个时自动删除最旧文件
- ✅ **模拟数据**: 生成随机新闻内容，无需外部API依赖
- ⚡ **极致性能**: 支持100+并发请求，无锁等待

---

## 🚀 快速开始

### 前置条件

- Docker 或 Docker Buildx

### 构建应用镜像

本项目使用 **Dockerfile 多阶段构建**，一个命令即可完成：

```bash
cd template_app
docker build -t file-manager-service:latest .
```

**构建说明**：
- 第一阶段（base）：构建 e2b 基础环境
  - Ubuntu 22.04
  - Python 3.11
  - 大量预装工具（git, curl, vim, chromium 等）
  - 预装的 Python 包（fastapi, uvicorn, pandas, numpy 等）
  - ubuntu 用户和完整的开发环境

- 第二阶段（app）：构建应用
  - 基于第一阶段的基础环境
  - 安装应用特定依赖
  - 复制应用代码

**优势**：
- ✅ 无需预先构建基础镜像
- ✅ 一条命令完成构建
- ✅ 利用 Docker 层缓存，后续构建更快
- ✅ 适合 CI/CD 流程

### 运行容器

```bash
docker run -d \
  --name file-manager \
  -p 8080:8080 \
  file-manager-service
```

### 测试服务

```bash
# 健康检查
curl http://localhost:8080/health

# 查看文件数量
curl http://localhost:8080/sum

# 创建新文件
curl -X POST http://localhost:8080/action
```

---

## 📡 API接口

### 1. `GET /` - 服务信息
返回服务基本信息和可用接口列表。

**响应示例**:
```json
{
  "service": "文件管理服务",
  "version": "1.0.0",
  "endpoints": {
    "/health": "健康检查 (GET)",
    "/sum": "获取文件数量 (GET)",
    "/action": "创建文件并写入新闻 (POST)",
    "/search": "浏览器搜索 (POST)",
    "/terminal": "执行终端命令 (POST)",
    "/network": "网络 I/O 测试 (POST)",
    "/docs": "API文档 (GET)"
  }
}
```

### 2. `GET /health` - 健康检查
检查服务运行状态。

**响应示例**:
```json
{
  "status": "ok"
}
```

### 3. `GET /sum` - 获取文件数量
返回当前文件总数和存储路径。

**响应示例**:
```json
{
  "count": 8,
  "path": "/home/ubuntu/",
  "timestamp": "2025-12-01T17:30:00.123456"
}
```

### 4. `POST /action` - 创建文件
创建新文件并写入模拟新闻内容。

**功能说明**:
1. 检查当前文件数量
2. 如果文件数 ≥ 10，删除最旧的文件（基于mtime）
3. 生成模拟新闻内容
4. 创建新文件并写入内容
5. 返回操作结果

**响应示例**:
```json
{
  "status": "success",
  "message": "文件创建成功",
  "filename": "news_20251201_173000_123456.txt",
  "deleted_file": "news_20251201_160000_000000.txt",
  "current_count": 10,
  "timestamp": "2025-12-01T17:30:00.123456"
}
```

### 5. `POST /search` - 浏览器搜索
使用 Chromium 浏览器访问 Google 并进行随机搜索。

**功能说明**:
1. 启动 Chromium 浏览器（无头模式）
2. 访问 www.google.com
3. 随机选择关键词进行搜索
4. 获取搜索结果页面信息

**响应示例**:
```json
{
  "status": "success",
  "message": "浏览器搜索完成",
  "search_keyword": "Python编程",
  "page_title": "Python编程 - Google 搜索",
  "page_url": "https://www.google.com/search?q=Python%E7%BC%96%E7%A8%8B",
  "duration_seconds": 3.45,
  "timestamp": "2025-12-01T17:30:00.123456"
}
```

### 6. `POST /terminal` - 执行终端命令
执行随机的终端命令并返回结果。

**功能说明**:
1. 从预定义命令列表中随机选择
2. 在子进程中执行命令
3. 捕获命令输出（stdout 和 stderr）

**响应示例**:
```json
{
  "status": "success",
  "message": "终端命令执行完成",
  "command": "ls -lh",
  "description": "列出当前目录文件（详细格式）",
  "return_code": 0,
  "stdout": "total 12K\n-rw-r--r-- 1 ubuntu ubuntu 1.2K Dec  1 17:30 file.txt",
  "stderr": null,
  "duration_seconds": 0.015,
  "timestamp": "2025-12-01T17:30:00.123456"
}
```

### 7. `POST /network` - 网络 I/O 测试
执行网络 I/O 测试，测量网络延迟和下载速度。

**功能说明**:
1. 随机选择测试 URL
2. 发送 HTTP 请求并下载数据
3. 测量延迟和下载速度

**响应示例**:
```json
{
  "status": "success",
  "message": "网络 I/O 测试完成",
  "test_description": "httpbin.org - 下载 1MB 随机数据",
  "url": "https://httpbin.org/bytes/1048576",
  "http_status": 200,
  "data_size_mb": 1.0,
  "expected_size_mb": 1.0,
  "duration_seconds": 0.523,
  "download_speed_mbps": 15.31,
  "timestamp": "2025-12-01T17:30:00.123456"
}
```

### 8. `GET /docs` - API文档
FastAPI自动生成的交互式API文档（Swagger UI）。

访问: http://localhost:8080/docs

---

## 🏗️ 技术架构

### 技术栈

| 组件 | 技术 | 版本 |
|------|------|------|
| 框架 | FastAPI | 0.104.1 |
| ASGI服务器 | uvicorn | 0.24.0 |
| 异步文件操作 | aiofiles | 23.2.1 |
| HTTP客户端 | httpx | 0.25.1 |
| 容器 | Docker | - |
| 基础镜像 | Ubuntu | 22.04 |

### 并发设计：无锁架构

采用**无锁设计**，最大化并发性能：

```python
@app.post("/action")
async def create_file_with_news():
    # 无锁设计 - 完全并发执行
    # 1. 检查文件数量（并发）
    files = await get_files_sorted_by_mtime()

    # 2. 删除旧文件（并发，自动处理FileNotFoundError）
    if len(files) >= MAX_FILES:
        try:
            os.remove(oldest_file)
        except FileNotFoundError:
            pass  # 已被其他请求删除，继续

    # 3. 创建新文件（并发）
    async with aiofiles.open(filepath, 'w') as f:
        await f.write(content)
```

**设计理念**:
- ⚡ **极致性能**: 无锁，无等待，100%并发
- 🎯 **最终一致**: 文件数量最终趋向于MAX_FILES（10个）
- 🛡️ **容错设计**: 自动处理并发删除冲突（FileNotFoundError）
- 📊 **权衡取舍**: 接受暂时超过限制，换取最大吞吐量

**并发行为**:
- ✅ 100个并发请求可同时执行
- ⚠️ 高并发时文件数可能暂时超过10个（如12-15个）
- ✅ 系统会自动清理，最终稳定在10个左右

---

## 📁 项目结构

```
template_app/
├── app.py              # FastAPI应用主文件
├── requirements.txt    # Python依赖
├── Dockerfile         # Docker构建文件
└── README.md          # 本文档
```

---

## 🔧 本地开发

### 环境要求

- Python 3.10+
- pip

### 安装依赖

```bash
cd template_app
pip install -r requirements.txt
```

### 运行服务

```bash
python3 app.py
```

或使用uvicorn：

```bash
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

---

## 🧪 测试

### 并发测试

使用Apache Bench进行并发测试：

```bash
# 100个请求，10个并发
ab -n 100 -c 10 -m POST http://localhost:8080/action
```

使用wrk进行压力测试：

```bash
wrk -t4 -c10 -d10s --latency -s post.lua http://localhost:8080/action
```

### 验证指标

- ✅ 文件总数始终不超过10个
- ✅ 每次请求都能成功完成
- ✅ 没有文件被重复删除
- ✅ 所有文件都有正确的内容

---

## 📝 文件格式

创建的新闻文件格式示例：

```
========================================
📄 文件信息
========================================
文件创建时间: 2025-12-01 17:30:00 (UTC+8)
创建时间戳: 2025-12-01T17:30:00.123456

========================================
📰 新闻内容
========================================
新闻标题：科技巨头发布最新AI产品
分类：科技
发布时间：2025-12-01 17:30:00
========================================

这是一条关于科技的新闻内容，包含重要信息和详细报道。...

----------------------------------------
本文由文件管理服务自动生成
生成时间：2025-12-01 17:30:00
时区：UTC+8
========================================
```

---

## 🐳 Docker配置

### Dockerfile说明

本项目采用 **Dockerfile 多阶段构建**（Multi-stage Build）：

#### 第一阶段（base）：e2b 基础环境
- **基础镜像**: Ubuntu 22.04
- **Python版本**: Python 3.11
- **预装工具**: git, curl, vim, chromium, supervisor 等
- **预装Python包**: fastapi, uvicorn, pandas, numpy, playwright 等
- **包管理**: 使用 `uv` 进行快速包安装
- **用户**: ubuntu用户（非root）

#### 第二阶段（app）：应用镜像
- **基于**: 第一阶段的 base
- **工作目录**: /home/ubuntu/
- **暴露端口**: 8080
- **健康检查**: 每30秒检查一次 `/health` 接口
- **运行用户**: ubuntu（非root，安全）

**优势**：
- ✅ 一条命令完成构建，无需预先构建基础镜像
- ✅ 利用 Docker 层缓存，后续构建更快
- ✅ 包含完整的 e2b 开发环境
- ✅ 适合 CI/CD 自动化部署

### 环境变量

当前版本使用硬编码配置，未来可通过环境变量配置：

- `FILE_DIR`: 文件存储目录（默认: /home/ubuntu/）
- `MAX_FILES`: 最大文件数（默认: 10）
- `PORT`: 服务端口（默认: 8080）

---

## 🔒 安全性

### 用户权限

- ✅ 使用ubuntu非特权用户运行服务
- ✅ 不使用root用户，降低安全风险
- ✅ 文件操作限制在 /home/ubuntu/ 目录

### 资源限制

- 最大文件数量: 10个
- 文件自动清理: 超过限制时删除最旧文件

---

## 📊 性能考虑

### 异步优势

- **非阻塞I/O**: 文件操作使用aiofiles
- **高并发**: 支持同时处理多个请求
- **资源高效**: 单个进程处理多个连接

### 性能优化建议

1. **缩小锁范围**: 将耗时操作移到锁外执行
2. **使用异步I/O**: 所有I/O操作使用async/await
3. **合理配置**: 根据实际负载调整uvicorn workers数量

---

## 🐛 故障排查

### 常见问题

**Q: 容器无法启动**
```bash
# 检查日志
docker logs file-manager

# 检查端口占用
netstat -tulpn | grep 8080
```

**Q: 文件权限错误**
```bash
# 确保使用ubuntu用户
docker exec -it file-manager whoami
# 应该输出: ubuntu
```

**Q: 并发测试失败**
```bash
# 检查文件数量
docker exec -it file-manager ls -la /home/ubuntu/ | grep news_
```

---

## 📚 相关文档

- [需求文档](../需求文档-文件管理服务.md)
- [FastAPI官方文档](https://fastapi.tiangolo.com/)
- [Docker官方文档](https://docs.docker.com/)

---

## 📄 许可证

本项目仅供学习和测试使用。

---

## 👥 维护信息

- **创建日期**: 2025-12-01
- **时区**: UTC+8
- **版本**: 1.0.0
