"""
文件管理服务 - FastAPI异步实现
功能：
1. /health - 健康检查
2. /sum - 返回文件数量
3. /action - 创建文件并写入模拟新闻内容，支持文件数量管理
4. /search - 使用浏览器访问 Google 并进行随机搜索
5. /terminal - 执行随机终端命令
6. /network - 执行网络 I/O 操作
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import aiofiles
import asyncio
import os
import random
import subprocess
import httpx
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from playwright.async_api import async_playwright, Browser, Page

# FastAPI应用实例
app = FastAPI(
    title="文件管理服务",
    description="基于FastAPI的异步文件管理服务，支持并发安全的文件创建和管理",
    version="1.0.0"
)

# 配置
FILE_DIR = "/home/ubuntu/"
MAX_FILES = 10

# ⭐ 无锁设计：最大化并发性能
# 注意：在高并发场景下，文件数量可能暂时超过MAX_FILES
# 这是性能和一致性之间的权衡

# 模拟新闻标题和内容模板
NEWS_TITLES = [
    "科技巨头发布最新AI产品",
    "全球气候峰会达成重要协议",
    "经济数据显示增长势头强劲",
    "体育赛事创下收视新高",
    "文化展览吸引大量观众",
    "健康研究揭示新发现",
    "教育改革方案正式实施",
    "交通基础设施建设加速",
    "环保倡议获得广泛支持",
    "国际合作项目取得突破"
]

NEWS_CATEGORIES = ["科技", "财经", "体育", "文化", "健康", "教育", "社会", "国际"]

# 随机搜索关键词列表
SEARCH_KEYWORDS = [
    "人工智能最新发展",
    "量子计算机",
    "气候变化解决方案",
    "太空探索新闻",
    "可再生能源技术",
    "机器学习应用",
    "区块链技术",
    "元宇宙发展",
    "生物科技突破",
    "自动驾驶汽车"
]

# 随机终端命令列表
TERMINAL_COMMANDS = [
    {"cmd": ["pwd"], "description": "显示当前工作目录"},
    {"cmd": ["whoami"], "description": "显示当前用户"},
    {"cmd": ["date"], "description": "显示当前日期和时间"},
    {"cmd": ["uname", "-a"], "description": "显示系统信息"},
    {"cmd": ["df", "-h"], "description": "显示磁盘使用情况"},
    {"cmd": ["free", "-m"], "description": "显示内存使用情况"},
    {"cmd": ["uptime"], "description": "显示系统运行时间"},
    {"cmd": ["ls", "-la", "/home/ubuntu"], "description": "列出 ubuntu 主目录文件"},
    {"cmd": ["python", "--version"], "description": "显示 Python 版本"},
    {"cmd": ["echo", "Hello from terminal!"], "description": "输出问候信息"}
]

# 网络 I/O 测试配置（全部为互联网公网地址）
NETWORK_TEST_URLS = [
    # httpbin.org - 公开的 HTTP 测试服务
    {
        "url": "https://httpbin.org/bytes/1048576",  # 1MB
        "description": "httpbin.org - 下载 1MB 随机数据",
        "size_mb": 1.0,
        "type": "download"
    },
    {
        "url": "https://httpbin.org/bytes/5242880",  # 5MB
        "description": "httpbin.org - 下载 5MB 随机数据",
        "size_mb": 5.0,
        "type": "download"
    },
    {
        "url": "https://httpbin.org/bytes/10485760",  # 10MB
        "description": "httpbin.org - 下载 10MB 随机数据",
        "size_mb": 10.0,
        "type": "download"
    },
    # 延迟测试
    {
        "url": "https://httpbin.org/delay/1",
        "description": "httpbin.org - 1秒延迟请求（测试延迟）",
        "size_mb": 0.001,
        "type": "latency"
    },
    {
        "url": "https://httpbin.org/delay/2",
        "description": "httpbin.org - 2秒延迟请求（测试延迟）",
        "size_mb": 0.001,
        "type": "latency"
    },
    # GitHub API - 全球 CDN
    {
        "url": "https://api.github.com/repos/python/cpython",
        "description": "GitHub API - Python 仓库信息",
        "size_mb": 0.01,
        "type": "api"
    },
    {
        "url": "https://api.github.com/repos/microsoft/vscode",
        "description": "GitHub API - VSCode 仓库信息",
        "size_mb": 0.01,
        "type": "api"
    },
    # JSONPlaceholder - 公开测试 API
    {
        "url": "https://jsonplaceholder.typicode.com/posts",
        "description": "JSONPlaceholder - 获取文章列表",
        "size_mb": 0.01,
        "type": "api"
    },
    {
        "url": "https://jsonplaceholder.typicode.com/users",
        "description": "JSONPlaceholder - 获取用户列表",
        "size_mb": 0.005,
        "type": "api"
    },
    # Google 公开服务
    {
        "url": "https://www.google.com",
        "description": "Google - 首页（HTML）",
        "size_mb": 0.5,
        "type": "web"
    },
    # Wikipedia
    {
        "url": "https://en.wikipedia.org/wiki/Main_Page",
        "description": "Wikipedia - 英文首页",
        "size_mb": 0.8,
        "type": "web"
    },
    # Cloudflare Speed Test
    {
        "url": "https://speed.cloudflare.com/__down?bytes=1000000",
        "description": "Cloudflare - 下载 1MB 测速",
        "size_mb": 1.0,
        "type": "download"
    }
]


def generate_mock_news() -> str:
    """
    生成模拟新闻内容

    Returns:
        str: 格式化的新闻内容
    """
    title = random.choice(NEWS_TITLES)
    category = random.choice(NEWS_CATEGORIES)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 生成随机段落
    paragraphs = []
    num_paragraphs = random.randint(2, 4)

    for _ in range(num_paragraphs):
        sentences = []
        num_sentences = random.randint(3, 6)
        for _ in range(num_sentences):
            sentence = f"这是一条关于{category}的新闻内容，包含重要信息和详细报道。"
            sentences.append(sentence)
        paragraphs.append(" ".join(sentences))

    # 添加文件创建时间戳（UTC+8）
    create_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    create_timestamp_iso = datetime.now().isoformat()

    content = f"""
========================================
📄 文件信息
========================================
文件创建时间: {create_timestamp} (UTC+8)
创建时间戳: {create_timestamp_iso}

========================================
📰 新闻内容
========================================
新闻标题：{title}
分类：{category}
发布时间：{timestamp}
========================================

{chr(10).join(paragraphs)}

----------------------------------------
本文由文件管理服务自动生成
生成时间：{timestamp}
时区：UTC+8
========================================
"""
    return content


async def get_files_sorted_by_mtime() -> list[str]:
    """
    获取文件列表，按修改时间排序（最旧的在前）

    Returns:
        list[str]: 排序后的文件名列表
    """
    try:
        # 确保目录存在
        Path(FILE_DIR).mkdir(parents=True, exist_ok=True)

        # 获取所有文件
        files = [
            f for f in os.listdir(FILE_DIR)
            if os.path.isfile(os.path.join(FILE_DIR, f)) and f.startswith("news_")
        ]

        # 按修改时间排序（最旧的在前）
        files.sort(key=lambda x: os.path.getmtime(os.path.join(FILE_DIR, x)))

        return files
    except Exception as e:
        print(f"获取文件列表出错: {e}")
        return []


@app.get("/health")
async def health_check():
    """
    健康检查接口

    Returns:
        dict: 健康状态
    """
    return {"status": "ok"}


@app.get("/sum")
async def get_file_count():
    """
    返回当前文件数量

    Returns:
        dict: 包含文件数量和路径的信息
    """
    try:
        files = await get_files_sorted_by_mtime()
        return {
            "count": len(files),
            "path": FILE_DIR,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件数量失败: {str(e)}")


@app.post("/action")
async def create_file_with_news():
    """
    创建文件并写入模拟新闻内容（无锁高并发版本）

    功能：
    1. 检查当前文件数量
    2. 如果文件数量 >= 10，尝试删除最旧的文件（基于mtime）
    3. 生成模拟新闻内容
    4. 创建新文件并写入内容
    5. 返回操作结果

    注意：
    - 无锁设计，支持完全并发执行
    - 高并发时文件数量可能暂时超过MAX_FILES
    - 最终会趋向于维持在MAX_FILES左右

    Returns:
        dict: 操作结果，包含文件名、删除的文件等信息
    """
    try:
        # 步骤1: 获取当前文件列表（按mtime排序）
        files = await get_files_sorted_by_mtime()
        deleted_file: Optional[str] = None

        # 步骤2: 检查并删除最旧的文件（如果需要）
        if len(files) >= MAX_FILES:
            oldest_file = files[0]
            oldest_file_path = os.path.join(FILE_DIR, oldest_file)

            try:
                os.remove(oldest_file_path)
                deleted_file = oldest_file
                print(f"[并发删除] 删除最旧文件: {oldest_file}")
            except FileNotFoundError:
                # 并发场景：文件可能已被其他请求删除，这是正常的
                print(f"[并发删除] 文件已被删除: {oldest_file}")
                deleted_file = f"{oldest_file} (已被其他请求删除)"
            except Exception as e:
                # 其他删除错误
                print(f"[错误] 删除文件失败: {e}")
                # 不抛出异常，继续创建新文件

        # 步骤3: 生成模拟新闻内容
        news_content = generate_mock_news()

        # 步骤4: 创建新文件
        # 使用时间戳 + 微秒 + 随机数确保文件名唯一性（高并发场景）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        new_filename = f"news_{timestamp}.txt"
        filepath = os.path.join(FILE_DIR, new_filename)

        # 步骤5: 异步写入文件
        try:
            async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
                await f.write(news_content)
            print(f"[并发创建] 创建新文件: {new_filename}")
        except Exception as e:
            print(f"[错误] 写入文件失败: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"写入文件失败: {str(e)}"
            )

        # 步骤6: 获取最新文件数量
        current_files = await get_files_sorted_by_mtime()

        # 步骤7: 返回结果
        return {
            "status": "success",
            "message": "文件创建成功（无锁并发模式）",
            "filename": new_filename,
            "deleted_file": deleted_file,
            "current_count": len(current_files),
            "max_files": MAX_FILES,
            "note": "高并发场景下文件数量可能暂时超过限制",
            "timestamp": datetime.now().isoformat()
        }

    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 捕获其他所有异常
        print(f"[错误] 操作失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"操作失败: {str(e)}"
        )


@app.post("/search")
async def google_search():
    """
    使用浏览器访问 Google 并进行随机搜索

    功能：
    1. 启动 Chromium 浏览器（无头模式）
    2. 访问 www.google.com
    3. 随机选择一个关键词进行搜索
    4. 获取搜索结果页面标题
    5. 关闭浏览器

    Returns:
        dict: 搜索结果信息
    """
    search_keyword = random.choice(SEARCH_KEYWORDS)
    start_time = datetime.now()

    try:
        async with async_playwright() as p:
            # 启动浏览器（使用系统 chromium）
            print(f"[浏览器] 启动 Chromium 浏览器...")
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled'
                ]
            )

            # 创建新页面
            page = await browser.new_page()
            print(f"[浏览器] 访问 Google...")

            try:
                # 访问 Google
                await page.goto('https://www.google.com', timeout=30000)
                await asyncio.sleep(1)

                # 查找搜索框并输入关键词
                print(f"[浏览器] 搜索关键词: {search_keyword}")
                search_box = await page.query_selector('textarea[name="q"]')
                if not search_box:
                    # 尝试另一个选择器
                    search_box = await page.query_selector('input[name="q"]')

                if search_box:
                    await search_box.fill(search_keyword)
                    await search_box.press('Enter')

                    # 等待搜索结果加载
                    await page.wait_for_load_state('networkidle', timeout=10000)
                    await asyncio.sleep(1)

                    # 获取页面标题
                    page_title = await page.title()
                    page_url = page.url

                    print(f"[浏览器] 搜索完成: {page_title}")

                    # 关闭浏览器
                    await browser.close()

                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()

                    return {
                        "status": "success",
                        "message": "浏览器搜索完成",
                        "search_keyword": search_keyword,
                        "page_title": page_title,
                        "page_url": page_url,
                        "duration_seconds": round(duration, 2),
                        "timestamp": datetime.now().isoformat()
                    }
                else:
                    await browser.close()
                    raise HTTPException(
                        status_code=500,
                        detail="无法找到搜索框"
                    )

            except Exception as e:
                await browser.close()
                print(f"[浏览器错误] {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"浏览器操作失败: {str(e)}"
                )

    except Exception as e:
        print(f"[错误] 浏览器启动失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"浏览器启动失败: {str(e)}"
        )


@app.post("/terminal")
async def execute_terminal_command():
    """
    执行随机终端命令

    功能：
    1. 从预定义命令列表中随机选择一个命令
    2. 在子进程中执行该命令
    3. 捕获命令输出（stdout 和 stderr）
    4. 返回执行结果

    Returns:
        dict: 命令执行结果
    """
    # 随机选择一个命令
    command_info = random.choice(TERMINAL_COMMANDS)
    command = command_info["cmd"]
    description = command_info["description"]

    start_time = datetime.now()

    try:
        print(f"[终端] 执行命令: {' '.join(command)}")

        # 异步执行命令
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/home/ubuntu"
        )

        # 等待命令完成并获取输出
        stdout, stderr = await process.communicate()

        # 解码输出
        stdout_text = stdout.decode('utf-8') if stdout else ""
        stderr_text = stderr.decode('utf-8') if stderr else ""

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        print(f"[终端] 命令执行完成，返回码: {process.returncode}")

        return {
            "status": "success" if process.returncode == 0 else "error",
            "message": "终端命令执行完成",
            "command": " ".join(command),
            "description": description,
            "return_code": process.returncode,
            "stdout": stdout_text.strip(),
            "stderr": stderr_text.strip() if stderr_text else None,
            "duration_seconds": round(duration, 3),
            "timestamp": datetime.now().isoformat()
        }

    except FileNotFoundError:
        print(f"[终端错误] 命令不存在: {command[0]}")
        raise HTTPException(
            status_code=500,
            detail=f"命令不存在: {command[0]}"
        )
    except Exception as e:
        print(f"[终端错误] 执行失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"命令执行失败: {str(e)}"
        )


@app.post("/network")
async def network_io_test():
    """
    执行网络 I/O 测试

    功能：
    1. 随机选择一个测试 URL
    2. 发送 HTTP 请求并下载数据
    3. 测量网络延迟、下载速度
    4. 可选：发送多个并发请求

    Returns:
        dict: 网络测试结果
    """
    # 随机选择测试配置
    test_config = random.choice(NETWORK_TEST_URLS)
    url = test_config["url"]
    description = test_config["description"]
    expected_size_mb = test_config["size_mb"]

    start_time = datetime.now()

    try:
        print(f"[网络] 开始测试: {description}")
        print(f"[网络] URL: {url}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 发送请求并下载数据
            response = await client.get(url)

            # 获取响应数据
            data = response.content
            data_size_bytes = len(data)
            data_size_mb = data_size_bytes / (1024 * 1024)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # 计算下载速度
            if duration > 0:
                speed_mbps = (data_size_mb * 8) / duration  # Mbps
            else:
                speed_mbps = 0

            print(f"[网络] 完成: {data_size_mb:.2f} MB, {duration:.2f}s, {speed_mbps:.2f} Mbps")

            return {
                "status": "success",
                "message": "网络 I/O 测试完成",
                "test_description": description,
                "url": url,
                "http_status": response.status_code,
                "data_size_mb": round(data_size_mb, 3),
                "expected_size_mb": expected_size_mb,
                "duration_seconds": round(duration, 3),
                "download_speed_mbps": round(speed_mbps, 2),
                "timestamp": datetime.now().isoformat()
            }

    except httpx.TimeoutException:
        print(f"[网络错误] 请求超时: {url}")
        raise HTTPException(
            status_code=504,
            detail=f"网络请求超时: {url}"
        )
    except httpx.RequestError as e:
        print(f"[网络错误] 请求失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"网络请求失败: {str(e)}"
        )
    except Exception as e:
        print(f"[网络错误] 未知错误: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"网络测试失败: {str(e)}"
        )


@app.post("/network/concurrent")
async def network_concurrent_test(num_requests: int = 5):
    """
    执行并发网络 I/O 测试

    Args:
        num_requests: 并发请求数量（默认 5）

    功能：
    1. 同时发送多个 HTTP 请求
    2. 测量总体吞吐量和平均延迟
    3. 统计成功率

    Returns:
        dict: 并发测试结果
    """
    if num_requests < 1 or num_requests > 50:
        raise HTTPException(
            status_code=400,
            detail="num_requests 必须在 1-50 之间"
        )

    print(f"[网络] 开始并发测试: {num_requests} 个请求")
    start_time = datetime.now()

    # 创建测试任务
    async def single_request(request_id: int) -> dict:
        test_config = random.choice(NETWORK_TEST_URLS)
        url = test_config["url"]

        req_start = datetime.now()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                data_size = len(response.content)
                req_duration = (datetime.now() - req_start).total_seconds()

                return {
                    "request_id": request_id,
                    "success": True,
                    "url": url,
                    "status": response.status_code,
                    "size_bytes": data_size,
                    "duration": req_duration
                }
        except Exception as e:
            return {
                "request_id": request_id,
                "success": False,
                "url": url,
                "error": str(e)
            }

    # 并发执行所有请求
    tasks = [single_request(i) for i in range(num_requests)]
    results = await asyncio.gather(*tasks)

    end_time = datetime.now()
    total_duration = (end_time - start_time).total_seconds()

    # 统计结果
    successful_requests = [r for r in results if r.get("success")]
    failed_requests = [r for r in results if not r.get("success")]

    total_bytes = sum(r.get("size_bytes", 0) for r in successful_requests)
    total_mb = total_bytes / (1024 * 1024)

    avg_latency = sum(r.get("duration", 0) for r in successful_requests) / len(successful_requests) if successful_requests else 0

    throughput_mbps = (total_mb * 8) / total_duration if total_duration > 0 else 0

    print(f"[网络] 并发测试完成: {len(successful_requests)}/{num_requests} 成功")

    return {
        "status": "success",
        "message": "并发网络测试完成",
        "num_requests": num_requests,
        "successful_requests": len(successful_requests),
        "failed_requests": len(failed_requests),
        "success_rate_percent": round((len(successful_requests) / num_requests) * 100, 2),
        "total_data_mb": round(total_mb, 3),
        "total_duration_seconds": round(total_duration, 3),
        "average_latency_seconds": round(avg_latency, 3),
        "throughput_mbps": round(throughput_mbps, 2),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/load/status")
async def get_load_status():
    """
    获取负载测试服务状态

    通过读取负载控制服务的状态文件获取信息

    Returns:
        dict: 负载测试服务状态
    """
    try:
        # 尝试读取状态文件
        status_file = "/tmp/load_controller_status.json"
        if os.path.exists(status_file):
            async with aiofiles.open(status_file, 'r') as f:
                import json
                content = await f.read()
                return json.loads(content)
        else:
            return {
                "status": "unknown",
                "message": "负载控制服务状态文件不存在"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"获取状态失败: {str(e)}"
        }


@app.post("/load/target")
async def set_load_target(target_cpu: float):
    """
    设置目标 CPU 使用率

    Args:
        target_cpu: 目标 CPU 使用率 (0-100)

    Returns:
        dict: 设置结果
    """
    if not 0 <= target_cpu <= 100:
        raise HTTPException(
            status_code=400,
            detail="target_cpu 必须在 0-100 之间"
        )

    try:
        # 写入配置文件
        config_file = "/tmp/load_controller_config.json"
        config = {
            "target_cpu": target_cpu,
            "updated_at": datetime.now().isoformat()
        }

        async with aiofiles.open(config_file, 'w') as f:
            import json
            await f.write(json.dumps(config, indent=2))

        print(f"[负载控制] 目标 CPU 使用率已更新: {target_cpu}%")

        return {
            "status": "success",
            "message": f"目标 CPU 使用率已设置为 {target_cpu}%",
            "target_cpu": target_cpu,
            "note": "负载控制服务将在下一个调整周期（~5秒）应用新配置"
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"设置失败: {str(e)}"
        )


@app.get("/")
async def root():
    """
    根路径，返回服务信息

    Returns:
        dict: 服务基本信息和可用接口
    """
    return {
        "service": "文件管理服务",
        "version": "1.0.0",
        "endpoints": {
            "/health": "健康检查 (GET)",
            "/sum": "获取文件数量 (GET)",
            "/action": "创建文件并写入新闻 (POST)",
            "/search": "浏览器搜索 (POST)",
            "/terminal": "执行终端命令 (POST)",
            "/network": "网络 I/O 测试 (POST)",
            "/network/concurrent": "并发网络测试 (POST)",
            "/load/status": "获取负载测试状态 (GET)",
            "/load/target": "设置目标负载 (POST)",
            "/docs": "API文档 (GET)"
        },
        "description": "基于FastAPI的异步文件管理服务，支持并发安全操作、浏览器自动化、终端命令执行、网络 I/O 测试和动态负载控制"
    }


# 启动时的初始化
@app.on_event("startup")
async def startup_event():
    """
    应用启动时执行
    确保工作目录存在，安装 Playwright 浏览器
    """
    print("=" * 50)
    print("文件管理服务启动中...")
    print(f"工作目录: {FILE_DIR}")
    print(f"最大文件数: {MAX_FILES}")

    # 确保目录存在
    try:
        Path(FILE_DIR).mkdir(parents=True, exist_ok=True)
        print(f"工作目录已就绪")
    except Exception as e:
        print(f"创建工作目录失败: {e}")

    # 显示当前文件数量
    files = await get_files_sorted_by_mtime()
    print(f"当前文件数量: {len(files)}")
    print("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """
    应用关闭时执行
    """
    print("=" * 50)
    print("文件管理服务正在关闭...")
    print("=" * 50)


if __name__ == "__main__":
    import uvicorn

    # 开发环境运行配置
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info"
    )
