#!/usr/bin/env python3
"""
E2B沙箱容量和负载均衡测试脚本

测试指标:
- 集群总容量（最大并发沙箱数）
- 单机最大沙箱密度
- 沙箱调度负载均衡性
- 节点间分布均匀度

环境变量 (必须通过 .e2b_env 配置):
- E2B_DOMAIN: E2B 服务域名 (必需)
- E2B_API_KEY: E2B API 密钥 (必需)
- E2B_TEMPLATE_NAME: 沙箱模板名称 (可选，默认使用默认模板)
- NOMAD_ADDR: Nomad 服务地址 (用于获取节点信息)
- NOMAD_TOKEN: Nomad 访问令牌 (用于获取节点信息)

使用方法:
  source .e2b_env
  python3 06_sandbox_capacity.py --batch-size 10 --max-sandboxes 1000
"""

import os
import sys
import ssl
import time
import json
import logging
import statistics
import subprocess
import re
from typing import List, Dict, Optional
from datetime import datetime
from collections import defaultdict

# ========== 禁用 SSL 证书验证 ==========
os.environ['PYTHONHTTPSVERIFY'] = '0'
os.environ['CURL_CA_BUNDLE'] = ''
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['SSL_CERT_FILE'] = ''
os.environ['SSL_CERT_DIR'] = ''
os.environ['REQUESTS_VERIFY'] = 'false'

ssl._create_default_https_context = ssl._create_unverified_context

_original_create_default_context = ssl.create_default_context
def _patched_create_default_context(*args, **kwargs):
    ctx = _original_create_default_context(*args, **kwargs)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx
ssl.create_default_context = _patched_create_default_context

_original_wrap_socket = ssl.SSLContext.wrap_socket
def _patched_wrap_socket(self, sock, server_side=False, do_handshake_on_connect=True,
                        suppress_ragged_eofs=True, server_hostname=None, session=None):
    self.check_hostname = False
    self.verify_mode = ssl.CERT_NONE
    return _original_wrap_socket(
        self, sock, server_side=server_side,
        do_handshake_on_connect=do_handshake_on_connect,
        suppress_ragged_eofs=suppress_ragged_eofs,
        server_hostname=server_hostname, session=session
    )
ssl.SSLContext.wrap_socket = _patched_wrap_socket

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import requests
    requests.packages.urllib3.disable_warnings()
except (ImportError, AttributeError):
    pass

try:
    import httpx
    _original_httpx_client_init = httpx.Client.__init__
    def _patched_httpx_client_init(self, *args, verify=False, **kwargs):
        return _original_httpx_client_init(self, *args, verify=False, **kwargs)
    httpx.Client.__init__ = _patched_httpx_client_init

    _original_httpx_async_client_init = httpx.AsyncClient.__init__
    def _patched_httpx_async_client_init(self, *args, verify=False, **kwargs):
        return _original_httpx_async_client_init(self, *args, verify=False, **kwargs)
    httpx.AsyncClient.__init__ = _patched_httpx_async_client_init
except (ImportError, AttributeError):
    pass

from e2b import Sandbox

# 配置彩色日志
try:
    import colorlog

    # 创建彩色formatter
    formatter = colorlog.ColoredFormatter(
        '%(log_color)s%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        },
        secondary_log_colors={},
        style='%'
    )

    # 配置handler
    handler = colorlog.StreamHandler()
    handler.setFormatter(formatter)

    # 配置logger
    logger = colorlog.getLogger(__name__)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

except ImportError:
    # 如果没有colorlog，使用标准日志并添加简单的ANSI颜色
    class ColoredFormatter(logging.Formatter):
        """自定义彩色formatter"""

        # ANSI颜色代码
        COLORS = {
            'DEBUG': '\033[36m',      # 青色
            'INFO': '\033[32m',       # 绿色
            'WARNING': '\033[33m',    # 黄色
            'ERROR': '\033[31m',      # 红色
            'CRITICAL': '\033[41m',   # 红色背景
        }
        RESET = '\033[0m'

        def format(self, record):
            # 添加颜色
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"
                record.msg = f"{self.COLORS[levelname]}{record.msg}{self.RESET}"
            return super().format(record)

    # 配置日志
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter(
        '%(asctime)s.%(msecs)03d [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))

    logger = logging.getLogger(__name__)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# 检查必需的环境变量
required_env_vars = ['E2B_DOMAIN', 'E2B_API_KEY']
missing_vars = [var for var in required_env_vars if var not in os.environ]
if missing_vars:
    logger.error(f"缺少必需的环境变量: {', '.join(missing_vars)}")
    logger.error("请先配置 .e2b_env 文件并运行: source .e2b_env")
    sys.exit(1)

E2B_DOMAIN = os.environ['E2B_DOMAIN']
E2B_API_KEY = os.environ['E2B_API_KEY']
E2B_TEMPLATE = os.environ.get('E2B_TEMPLATE_NAME', None)
NOMAD_ADDR = os.environ.get('NOMAD_ADDR', '')
NOMAD_TOKEN = os.environ.get('NOMAD_TOKEN', '')


class SandboxCapacityTester:
    """沙箱容量和负载均衡测试器"""

    def __init__(self, batch_size: int = 10, max_sandboxes: int = 1000,
                 interval: float = 2.0, timeout: int = 1500, auto_cleanup: bool = True,
                 maintain_lifecycle: bool = False, max_lifetime: int = 3600,
                 check_interval: int = 60, initial_target: int = None):
        """
        初始化测试器

        Args:
            batch_size: 每批创建的沙箱数量
            max_sandboxes: 最大尝试创建的沙箱数（防止无限创建）
            interval: 批次之间的间隔时间（秒）
            timeout: 单个沙箱创建的超时时间（秒）
            auto_cleanup: 是否自动清理创建的沙箱（默认：True）
            maintain_lifecycle: 是否启用维持生命周期模式（默认：False）
            max_lifetime: 维持生命周期模式下的最大生命周期时间（秒，默认：3600）
            check_interval: 维持生命周期模式下检查沙箱存活状态的间隔（秒，默认：60）
            initial_target: 第一阶段的初始目标沙箱数（默认：None，表示等于max_sandboxes）
        """
        self.batch_size = batch_size
        self.max_sandboxes = max_sandboxes
        # 如果没有指定 initial_target，则为 max_sandboxes 的 80%
        if initial_target is not None:
            self.initial_target = initial_target
        else:
            self.initial_target = int(max_sandboxes * 0.8) if maintain_lifecycle else max_sandboxes
        # 确保 initial_target 不超过 max_sandboxes
        if self.initial_target > max_sandboxes:
            self.initial_target = max_sandboxes
        # 确保至少为1
        if self.initial_target < 1:
            self.initial_target = 1
        self.interval = interval
        self.timeout = timeout
        self.auto_cleanup = auto_cleanup
        self.maintain_lifecycle = maintain_lifecycle
        self.max_lifetime = max_lifetime
        self.check_interval = check_interval
        self.sandboxes: List[Sandbox] = []
        self.sandbox_create_times: Dict[str, float] = {}  # 记录每个沙箱的创建时间
        self.failed_count = 0
        self.node_capacity_reached = False  # 标记是否达到节点容量上限
        self.results = {
            'total_created': 0,
            'total_failed': 0,
            'max_capacity': 0,
            'node_distribution': {},
            'balance_metrics': {},
            'test_timestamp': datetime.utcnow().isoformat(),
            'lifecycle_stats': {}  # 生命周期统计
        }

    def get_sandboxes_from_api(self) -> List[Dict]:
        """
        通过 E2B API 获取沙箱列表

        Returns:
            沙箱列表
        """
        try:
            headers = {
                'X-API-Key': E2B_API_KEY,
                'Content-Type': 'application/json'
            }

            # E2B API endpoint
            api_url = f"https://{E2B_DOMAIN}/api/sandboxes"

            response = requests.get(
                api_url,
                headers=headers,
                timeout=30,
                verify=False
            )

            if response.status_code == 200:
                sandboxes = response.json()
                return sandboxes if isinstance(sandboxes, list) else []
            else:
                return []

        except Exception:
            return []

    def get_node_sandbox_counts(self) -> None:
        """
        获取并显示每个节点上的沙箱数量统计
        """
        logger.info("=" * 60)
        logger.info("统计单个节点沙箱数量")
        logger.info("=" * 60)

        # 尝试通过 API 获取沙箱列表
        sandbox_list = self.get_sandboxes_from_api()

        # 如果 API 失败，尝试使用 CLI
        if not sandbox_list:
            sandbox_list = self.get_sandbox_list_from_cli()

        if not sandbox_list:
            logger.warning("无法获取沙箱列表")
            logger.info(f"提示: 当前已成功创建 {len(self.sandboxes)} 个沙箱")
            return

        # 统计每个节点的沙箱数量
        node_counts = defaultdict(int)
        for sandbox in sandbox_list:
            # 尝试多个可能的节点字段名
            node_id = (sandbox.get('node_id') or
                      sandbox.get('nodeId') or
                      sandbox.get('node') or
                      sandbox.get('clientNode') or
                      'unknown')
            node_counts[node_id] += 1

        if not node_counts or (len(node_counts) == 1 and 'unknown' in node_counts):
            logger.warning("无法获取节点分布信息（沙箱数据中不包含节点信息）")
            logger.info(f"总沙箱数: {len(sandbox_list)}")
            logger.info(f"当前已创建: {len(self.sandboxes)} 个")
            return

        # 显示统计结果
        logger.info(f"总沙箱数: {len(sandbox_list)}")
        logger.info(f"节点数: {len(node_counts)}")
        logger.info("各节点沙箱数量:")

        for node_id, count in sorted(node_counts.items(), key=lambda x: x[1], reverse=True):
            # 如果节点ID太长，只显示前8位
            display_name = node_id[:12] if len(node_id) > 12 else node_id
            percentage = (count / len(sandbox_list) * 100) if len(sandbox_list) > 0 else 0
            logger.info(f"  {display_name}: {count} 个沙箱 ({percentage:.1f}%)")

        logger.info("=" * 60)

    def create_sandbox_batch(self, count: int) -> List[Optional[Sandbox]]:
        """
        创建一批沙箱

        Args:
            count: 要创建的沙箱数量

        Returns:
            创建的沙箱对象列表（失败的为 None）
        """
        sandboxes = []
        for i in range(count):
            try:
                sandbox_num = len(self.sandboxes) + i + 1
                logger.info(f"创建沙箱 #{sandbox_num}...")

                # 创建沙箱
                if E2B_TEMPLATE:
                    sandbox = Sandbox(
                        template=E2B_TEMPLATE,
                        api_key=E2B_API_KEY,
                        timeout=self.timeout
                    )
                else:
                    sandbox = Sandbox(
                        api_key=E2B_API_KEY,
                        timeout=self.timeout
                    )

                sandboxes.append(sandbox)
                # 记录创建时间
                self.sandbox_create_times[sandbox.sandbox_id] = time.time()
                logger.info(f"✓ 沙箱 #{sandbox_num} 创建成功 (ID: {sandbox.sandbox_id})")

            except Exception as e:
                error_msg = str(e)
                logger.error(f"✗ 沙箱 #{sandbox_num} 创建失败: {error_msg}")
                sandboxes.append(None)
                self.failed_count += 1

                # 检查是否是节点放置失败错误
                if "500" in error_msg and "Failed to get node to place sandbox on" in error_msg:
                    logger.warning("检测到节点容量问题，正在统计节点沙箱数量...")
                    self.get_node_sandbox_counts()
                    self.node_capacity_reached = True
                    logger.warning("已达到节点容量上限，停止创建新沙箱")
                    return sandboxes

                # 如果连续失败多次，可能达到容量上限
                if self.failed_count >= 3:
                    logger.warning(f"连续失败 {self.failed_count} 次，可能已达到容量上限")
                    return sandboxes

        return sandboxes

    def get_sandbox_list_from_cli(self) -> List[Dict]:
        """
        通过 e2b CLI 获取沙箱列表

        Returns:
            沙箱列表
        """
        try:
            logger.info("获取沙箱列表 (通过 e2b sbx list)...")

            # 设置环境变量
            env = os.environ.copy()
            env['E2B_DOMAIN'] = E2B_DOMAIN
            env['E2B_API_KEY'] = E2B_API_KEY

            # 执行 e2b sbx ls 命令（不使用 --json 选项）
            result = subprocess.run(
                ['e2b', 'sbx', 'ls'],
                capture_output=True,
                text=True,
                timeout=30,
                env=env
            )

            if result.returncode != 0:
                logger.warning(f"e2b CLI 命令失败: {result.stderr}")
                return []

            # 调试：输出原始内容
            if not result.stdout.strip():
                logger.warning("e2b sbx list 返回空输出")
                logger.info(f"stderr: {result.stderr}")
                return []

            logger.info(f"[DEBUG] e2b sbx list 输出长度: {len(result.stdout)} 字符")
            logger.info(f"[DEBUG] 前200字符: {repr(result.stdout[:200])}")

            # 清除 ANSI 转义序列（终端颜色代码）
            # ANSI 代码格式：\x1b[...m
            ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
            clean_output = ansi_escape.sub('', result.stdout)

            # 解析文本输出
            # 输出格式是表格，需要跳过标题和表头行
            sandboxes = []
            lines = clean_output.strip().split('\n')

            # 跳过前面的空行、标题行、表头行
            data_started = False
            for line in lines:
                line = line.strip()

                # 跳过空行
                if not line:
                    continue

                # 跳过标题行（包含 "Running sandboxes" 等）
                if 'sandbox' in line.lower() and 'id' not in line.lower():
                    continue

                # 跳过表头行（包含 "Sandbox ID", "Template ID" 等列名）
                if line.lower().startswith('sandbox id') or 'template id' in line.lower():
                    data_started = True
                    continue

                # 如果还没遇到表头，继续跳过
                if not data_started:
                    continue

                # 解析数据行：第一列是沙箱ID
                parts = line.split()
                if parts and len(parts[0]) > 10:  # 沙箱ID通常较长
                    sandbox_id = parts[0]
                    # 验证沙箱ID格式（通常是字母数字加连字符）
                    if '-' in sandbox_id:
                        sandboxes.append({'sandbox_id': sandbox_id})

            logger.info(f"✓ 获取到 {len(sandboxes)} 个沙箱")
            return sandboxes

        except FileNotFoundError:
            logger.warning("未找到 e2b CLI 工具，请先安装: npm install -g @e2b/cli")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("e2b CLI 命令超时")
            return []
        except Exception as e:
            logger.warning(f"获取沙箱列表失败: {e}")
            return []

    def get_node_info_from_nomad(self) -> Dict[str, Dict]:
        """
        从 Nomad 获取节点信息

        Returns:
            节点信息字典 {node_id: {name, datacenter, ...}}
        """
        if not NOMAD_ADDR or not NOMAD_TOKEN:
            logger.warning("未配置 Nomad 访问信息，跳过节点信息获取")
            return {}

        try:
            logger.info("获取 Nomad 节点信息...")

            headers = {
                'X-Nomad-Token': NOMAD_TOKEN
            }

            response = requests.get(
                f"{NOMAD_ADDR.rstrip('/')}/v1/nodes",
                headers=headers,
                timeout=10,
                verify=False
            )

            if response.status_code != 200:
                logger.warning(f"获取节点信息失败: HTTP {response.status_code}")
                return {}

            nodes = response.json()
            node_info = {}

            for node in nodes:
                node_id = node.get('ID', '')
                node_info[node_id] = {
                    'name': node.get('Name', 'Unknown'),
                    'datacenter': node.get('Datacenter', 'Unknown'),
                    'status': node.get('Status', 'Unknown'),
                    'address': node.get('Address', 'Unknown')
                }

            logger.info(f"✓ 获取到 {len(node_info)} 个节点信息")
            return node_info

        except Exception as e:
            logger.warning(f"获取 Nomad 节点信息失败: {e}")
            return {}

    def analyze_distribution(self, sandboxes: List[Dict],
                           node_info: Dict[str, Dict]) -> Dict:
        """
        分析沙箱在节点上的分布情况

        Args:
            sandboxes: 沙箱列表
            node_info: 节点信息

        Returns:
            分布分析结果
        """
        logger.info("分析沙箱分布...")

        # 统计每个节点的沙箱数量
        node_counts = defaultdict(int)

        for sandbox in sandboxes:
            # 尝试从沙箱信息中提取节点ID
            # 注意：e2b CLI 的输出格式可能需要调整
            node_id = sandbox.get('node_id') or sandbox.get('nodeId') or 'unknown'
            node_counts[node_id] += 1

        # 如果无法从沙箱信息获取节点ID，尝试使用其他字段
        if len(node_counts) == 1 and 'unknown' in node_counts:
            logger.warning("无法从沙箱信息中获取节点分布，可能需要其他方式获取")

        # 计算统计指标
        counts = list(node_counts.values())

        if not counts:
            return {
                'node_distribution': {},
                'total_nodes': 0,
                'total_sandboxes': 0,
                'metrics': {}
            }

        metrics = {
            'total_nodes': len(counts),
            'total_sandboxes': sum(counts),
            'max_per_node': max(counts),
            'min_per_node': min(counts),
            'avg_per_node': statistics.mean(counts),
            'median_per_node': statistics.median(counts),
        }

        # 计算标准差和变异系数（衡量均衡性）
        if len(counts) > 1:
            metrics['stddev'] = statistics.stdev(counts)
            metrics['cv'] = metrics['stddev'] / metrics['avg_per_node'] if metrics['avg_per_node'] > 0 else 0
            metrics['balance_score'] = 1 - metrics['cv']  # 越接近1越均衡
        else:
            metrics['stddev'] = 0
            metrics['cv'] = 0
            metrics['balance_score'] = 1.0

        # 构建详细的节点分布信息
        distribution = {}
        for node_id, count in node_counts.items():
            node_name = node_info.get(node_id, {}).get('name', node_id)
            distribution[node_name] = {
                'node_id': node_id,
                'sandbox_count': count,
                'percentage': (count / metrics['total_sandboxes'] * 100) if metrics['total_sandboxes'] > 0 else 0
            }

        return {
            'node_distribution': distribution,
            'metrics': metrics
        }

    def check_sandbox_alive(self, sandbox: Sandbox, alive_sandboxes_cache: set = None) -> bool:
        """
        检查沙箱是否存活（通过查询沙箱列表）

        Args:
            sandbox: 沙箱对象
            alive_sandboxes_cache: 可选的存活沙箱ID缓存集合

        Returns:
            是否存活
        """
        try:
            sandbox_id = sandbox.sandbox_id

            # 如果提供了缓存，直接使用
            if alive_sandboxes_cache is not None:
                is_alive = sandbox_id in alive_sandboxes_cache
                logger.debug(f"沙箱 {sandbox_id[:12]} 存活检查（缓存）: {is_alive}")
                return is_alive

            # 否则通过 API 获取所有沙箱列表
            sandbox_list = self.get_sandboxes_from_api()

            if not sandbox_list:
                # API 失败，尝试 CLI
                logger.debug(f"API 获取沙箱列表失败，尝试使用 CLI")
                sandbox_list = self.get_sandbox_list_from_cli()

            if not sandbox_list:
                logger.warning(f"无法获取沙箱列表，无法验证沙箱 {sandbox_id[:12]} 状态")
                return False

            # 检查沙箱ID是否在列表中
            for sbx in sandbox_list:
                sbx_id = sbx.get('sandbox_id') or sbx.get('sandboxId') or sbx.get('id')
                if sbx_id == sandbox_id:
                    logger.debug(f"沙箱 {sandbox_id[:12]} 存在于列表中")
                    return True

            logger.debug(f"沙箱 {sandbox_id[:12]} 不在列表中（已被清理）")
            return False

        except Exception as e:
            error_msg = str(e)
            logger.warning(f"沙箱 {sandbox.sandbox_id[:12]} 状态查询失败: {error_msg}")
            return False

    def extend_sandbox_lifetime(self, sandbox: Sandbox) -> bool:
        """
        延长沙箱生命周期

        Args:
            sandbox: 沙箱对象

        Returns:
            是否成功延长
        """
        try:
            # E2B SDK 可能需要通过 API 来延长生命周期
            # 这里使用 keep_alive 或类似方法
            # 如果SDK不支持，我们需要通过API直接调用
            headers = {
                'X-API-Key': E2B_API_KEY,
                'Content-Type': 'application/json'
            }

            api_url = f"https://{E2B_DOMAIN}/api/sandboxes/{sandbox.sandbox_id}/refreshes"

            response = requests.post(
                api_url,
                headers=headers,
                timeout=30,
                verify=False
            )

            if response.status_code in [200, 201, 204]:
                logger.debug(f"沙箱 {sandbox.sandbox_id} 生命周期已延长")
                return True
            else:
                logger.warning(f"延长沙箱 {sandbox.sandbox_id} 生命周期失败: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.warning(f"延长沙箱 {sandbox.sandbox_id} 生命周期失败: {e}")
            return False

    def maintain_sandboxes_lifecycle(self) -> bool:
        """
        第二阶段：维持沙箱生命周期
        定期检查沙箱存活状态，并延长生命周期直到达到最大时间
        在每次检查时尝试创建新沙箱，如果成功则返回第一阶段继续批量创建

        Returns:
            是否应该继续创建沙箱（True表示还有容量，应返回第一阶段）
        """
        logger.info("=" * 60)
        logger.info("第二阶段：维持沙箱生命周期")
        logger.info("=" * 60)
        logger.info(f"最大生命周期: {self.max_lifetime}秒 ({self.max_lifetime/60:.1f}分钟)")
        logger.info(f"检查间隔: {self.check_interval}秒")
        logger.info(f"监控沙箱数: {len(self.sandboxes)}")
        logger.info("=" * 60)

        # 如果没有沙箱需要监控，直接退出
        if len(self.sandboxes) == 0:
            logger.warning("没有沙箱需要监控，跳过第二阶段")
            return False

        # 检查沙箱年龄，警告可能已超时的沙箱
        current_time = time.time()
        old_sandboxes = []
        for sandbox in self.sandboxes:
            create_time = self.sandbox_create_times.get(sandbox.sandbox_id, current_time)
            age = current_time - create_time
            if age > self.timeout * 0.9:  # 超过90%的timeout时间
                old_sandboxes.append((sandbox.sandbox_id[:12], age))

        if old_sandboxes:
            logger.warning(f"警告：{len(old_sandboxes)} 个沙箱已接近或超过timeout时间（{self.timeout}秒）")
            for sbx_id, age in old_sandboxes[:5]:  # 只显示前5个
                logger.warning(f"  - 沙箱 {sbx_id}: 已存活 {age:.0f}秒")
            if len(old_sandboxes) > 5:
                logger.warning(f"  ... 还有 {len(old_sandboxes)-5} 个")
            logger.warning("这些沙箱可能已被系统自动清理")


        start_time = time.time()
        check_count = 0
        total_extensions = 0
        dead_sandboxes = set()
        max_alive_count = 0  # 记录维持期间的最高存活数量

        try:
            while True:
                current_time = time.time()
                elapsed = current_time - start_time

                # 检查是否已达到最大生命周期
                if elapsed >= self.max_lifetime:
                    logger.info(f"已达到最大生命周期 {self.max_lifetime}秒，结束维持阶段")
                    break

                check_count += 1
                logger.info(f"[检查 #{check_count}] 已运行: {elapsed:.0f}秒 / {self.max_lifetime}秒 ({elapsed/self.max_lifetime*100:.1f}%)")

                # 一次性获取所有存活的沙箱ID（作为缓存）
                logger.debug("获取所有存活沙箱列表...")
                sandbox_list = self.get_sandboxes_from_api()
                if not sandbox_list:
                    sandbox_list = self.get_sandbox_list_from_cli()

                alive_sandboxes_cache = set()
                if sandbox_list:
                    for sbx in sandbox_list:
                        sbx_id = sbx.get('sandbox_id') or sbx.get('sandboxId') or sbx.get('id')
                        if sbx_id:
                            alive_sandboxes_cache.add(sbx_id)
                    logger.debug(f"获取到 {len(alive_sandboxes_cache)} 个存活沙箱")
                else:
                    logger.warning("无法获取沙箱列表，将逐个检查")
                    alive_sandboxes_cache = None

                alive_count = 0
                dead_count = 0
                extended_count = 0
                check_errors = []  # 记录检查错误

                # 检查每个沙箱
                for i, sandbox in enumerate(self.sandboxes):
                    sandbox_id = sandbox.sandbox_id

                    # 跳过已知死亡的沙箱
                    if sandbox_id in dead_sandboxes:
                        continue

                    # 检查沙箱是否存活（使用缓存）
                    try:
                        is_alive = self.check_sandbox_alive(sandbox, alive_sandboxes_cache)
                    except Exception as e:
                        # 捕获检查过程中的异常
                        error_msg = f"沙箱 {sandbox_id[:12]} 检查异常: {str(e)}"
                        check_errors.append(error_msg)
                        logger.warning(error_msg)
                        is_alive = False

                    if is_alive:
                        alive_count += 1

                        # 计算沙箱已存活时间
                        create_time = self.sandbox_create_times.get(sandbox_id, start_time)
                        sandbox_age = current_time - create_time

                        # 如果沙箱已经接近超时时间，尝试延长生命周期
                        # 我们在超时前提前延长（预留一些缓冲时间）
                        if sandbox_age > self.timeout * 0.8:  # 当达到80%超时时间时延长
                            if self.extend_sandbox_lifetime(sandbox):
                                extended_count += 1
                                total_extensions += 1
                                # 更新创建时间（视为重置生命周期）
                                self.sandbox_create_times[sandbox_id] = current_time
                                logger.info(f"  ✓ 沙箱 {sandbox_id[:12]} 生命周期已延长 (已存活: {sandbox_age:.0f}秒)")
                    else:
                        dead_count += 1
                        dead_sandboxes.add(sandbox_id)
                        # 只在第一次检查时输出详细信息
                        if check_count == 1 and i < 3:  # 只输出前3个的详细信息
                            logger.warning(f"  ✗ 沙箱 {sandbox_id[:12]} 未响应（可能已死亡或未完全启动）")
                        elif check_count > 1:
                            logger.warning(f"  ✗ 沙箱 {sandbox_id[:12]} 已死亡")

                # 更新最高存活数量
                if alive_count > max_alive_count:
                    max_alive_count = alive_count
                    logger.info(f"🔥 新纪录：存活沙箱数达到 {max_alive_count}")

                # 打印当前沙箱数量统计
                current_alive = alive_count
                current_total = len(self.sandboxes)
                logger.info(f"本次检查: 存活={alive_count}, 死亡={dead_count}, 延长={extended_count}")
                logger.info(f"当前状态: 总沙箱数={current_total}, 当前存活={current_alive}, 累计死亡={len(dead_sandboxes)}")
                logger.info(f"累计统计: 总检查={check_count}, 总延长={total_extensions}, 峰值存活={max_alive_count}")

                # 如果没有存活的沙箱，直接退出
                if alive_count == 0:
                    logger.warning("当前没有存活的沙箱")
                    if check_count == 1:
                        logger.warning("可能原因：")
                        logger.warning("  1. 沙箱已超过timeout时间被系统清理")
                        logger.warning("  2. 沙箱创建失败或启动失败")
                        logger.warning("  3. 网络连接问题导致无法查询状态")
                    logger.warning("第二阶段提前结束")
                    break

                # 检查是否已达到最大沙箱数
                if alive_count >= self.max_sandboxes:
                    logger.info(f"存活沙箱数（{alive_count}）已达到配置的最大值（{self.max_sandboxes}），不再创建新沙箱")
                    logger.info("继续维持现有沙箱生命周期...")
                    # 不尝试创建，直接进入下一次检查循环
                else:
                    # 尝试创建一个新沙箱，测试是否还有容量
                    logger.info("尝试创建新沙箱以测试集群容量...")
                    try:
                        if E2B_TEMPLATE:
                            test_sandbox = Sandbox(
                                template=E2B_TEMPLATE,
                                api_key=E2B_API_KEY,
                                timeout=self.timeout
                            )
                        else:
                            test_sandbox = Sandbox(
                                api_key=E2B_API_KEY,
                                timeout=self.timeout
                            )

                        # 创建成功，记录并返回True，表示应该继续第一阶段
                        self.sandboxes.append(test_sandbox)
                        self.sandbox_create_times[test_sandbox.sandbox_id] = time.time()
                        logger.info(f"✓ 新沙箱创建成功 (ID: {test_sandbox.sandbox_id})，返回第一阶段继续批量创建")
                        logger.info(f"当前总沙箱数: {len(self.sandboxes)}")

                        # 保存当前统计
                        self._save_lifecycle_stats(check_count, total_extensions, dead_sandboxes, time.time() - start_time, max_alive_count)
                        return True  # 返回True，表示应该继续创建

                    except Exception as e:
                        error_msg = str(e)
                        logger.warning(f"✗ 新沙箱创建失败: {error_msg}")

                        # 检查是否是容量问题
                        if "500" in error_msg and "Failed to get node to place sandbox on" in error_msg:
                            logger.info("确认已达到容量上限，继续维持现有沙箱生命周期")
                        else:
                            logger.info("创建失败（可能已达容量上限），继续维持现有沙箱生命周期")

                # 等待下一次检查
                remaining_time = self.max_lifetime - elapsed
                next_check_in = min(self.check_interval, remaining_time)

                if next_check_in > 0:
                    logger.info(f"等待 {next_check_in:.0f}秒进行下一次检查...")
                    time.sleep(next_check_in)

        except KeyboardInterrupt:
            logger.warning("收到中断信号，结束维持阶段")

        # 记录统计信息
        total_elapsed = time.time() - start_time
        self._save_lifecycle_stats(check_count, total_extensions, dead_sandboxes, total_elapsed, max_alive_count)

        logger.info("=" * 60)
        logger.info("第二阶段完成")
        logger.info("=" * 60)
        logger.info(f"总检查次数: {check_count}")
        logger.info(f"总延长次数: {total_extensions}")
        logger.info(f"峰值存活数: {max_alive_count} （维持期间的最高存活数量）")
        logger.info(f"死亡沙箱数: {len(dead_sandboxes)}")
        logger.info(f"当前存活数: {len(self.sandboxes) - len(dead_sandboxes)}")
        logger.info(f"存活率: {self.results['lifecycle_stats']['survival_rate']:.1f}%")
        logger.info(f"实际运行时间: {total_elapsed:.0f}秒 ({total_elapsed/60:.1f}分钟)")
        logger.info("=" * 60)

        return False  # 返回False，表示已达到最大生命周期时间，不再继续创建

    def _save_lifecycle_stats(self, check_count: int, total_extensions: int,
                              dead_sandboxes: set, total_elapsed: float, max_alive_count: int = 0):
        """
        保存生命周期统计信息

        Args:
            check_count: 检查次数
            total_extensions: 延长次数
            dead_sandboxes: 死亡沙箱集合
            total_elapsed: 总运行时间
            max_alive_count: 维持期间的最高存活数量
        """
        self.results['lifecycle_stats'] = {
            'total_checks': check_count,
            'total_extensions': total_extensions,
            'total_dead': len(dead_sandboxes),
            'total_elapsed': total_elapsed,
            'max_lifetime': self.max_lifetime,
            'check_interval': self.check_interval,
            'max_alive_count': max_alive_count,  # 峰值存活数量
            'survival_rate': (len(self.sandboxes) - len(dead_sandboxes)) / len(self.sandboxes) * 100 if self.sandboxes else 0
        }

    def run_test(self):
        """运行容量测试"""
        logger.info("=" * 60)
        logger.info("E2B 沙箱容量和负载均衡测试")
        logger.info("=" * 60)
        logger.info("配置:")
        logger.info(f"  E2B 域名: {E2B_DOMAIN}")
        logger.info(f"  模板: {E2B_TEMPLATE or '默认'}")
        logger.info(f"  批次大小: {self.batch_size}")
        logger.info(f"  批次间隔: {self.interval}秒")
        logger.info(f"  沙箱超时: {self.timeout}秒 ({self.timeout/60:.1f}分钟)")
        if self.maintain_lifecycle:
            logger.info(f"  维持生命周期模式: 已启用")
            logger.info(f"  初始目标数: {self.initial_target}")
            logger.info(f"  最大沙箱数: {self.max_sandboxes}")
            logger.info(f"  最大生命周期: {self.max_lifetime}秒 ({self.max_lifetime/60:.1f}分钟)")
            logger.info(f"  检查间隔: {self.check_interval}秒")
        else:
            logger.info(f"  最大沙箱数: {self.max_sandboxes}")
        logger.info("=" * 60)

        try:
            # 主循环：第一阶段（创建）和第二阶段（维持）交替进行
            phase_num = 1
            continue_creating = True

            while continue_creating:
                # ========== 第一阶段：批量创建沙箱 ==========
                logger.info("=" * 60)
                logger.info(f"第一阶段（轮次 {phase_num}）：批量创建沙箱")
                logger.info("=" * 60)

                batch_num = 1
                phase_start_sandboxes = len(self.sandboxes)

                # 第一阶段的目标：initial_target（首轮）或 max_sandboxes（后续轮次）
                phase_target = self.initial_target if phase_num == 1 else self.max_sandboxes

                while len(self.sandboxes) < phase_target:
                    logger.info(f"[批次 {batch_num}] 创建 {self.batch_size} 个沙箱...")

                    # 计算本批次应创建的数量
                    remaining = phase_target - len(self.sandboxes)
                    current_batch_size = min(self.batch_size, remaining)

                    # 创建沙箱
                    batch_start_time = time.time()
                    new_sandboxes = self.create_sandbox_batch(current_batch_size)
                    batch_elapsed = time.time() - batch_start_time

                    # 过滤掉失败的
                    successful = [s for s in new_sandboxes if s is not None]
                    self.sandboxes.extend(successful)

                    logger.info(f"本批次成功: {len(successful)}/{current_batch_size} (耗时: {batch_elapsed:.2f}秒)")
                    logger.info(f"累计成功: {len(self.sandboxes)}")
                    logger.info(f"累计失败: {self.failed_count}")

                    # 检查是否达到节点容量上限
                    if self.node_capacity_reached:
                        logger.info("✓ 已达到节点容量上限")
                        break

                    # 如果连续失败太多次，认为达到容量上限
                    if self.failed_count >= 3 and len(successful) == 0:
                        logger.info("✓ 达到容量上限，停止创建")
                        break

                    # 等待一段时间再创建下一批
                    if len(self.sandboxes) < self.max_sandboxes:
                        logger.info(f"等待 {self.interval} 秒...")
                        time.sleep(self.interval)

                    batch_num += 1

                # 记录第一阶段完成
                phase_created = len(self.sandboxes) - phase_start_sandboxes
                logger.info("=" * 60)
                logger.info(f"第一阶段（轮次 {phase_num}）完成")
                logger.info("=" * 60)
                logger.info(f"本轮创建: {phase_created} 个沙箱")
                logger.info(f"当前总数: {len(self.sandboxes)} 个沙箱")
                logger.info(f"累计失败: {self.failed_count} 次")
                logger.info("=" * 60)

                # ========== 第二阶段：维持生命周期 ==========
                # 如果启用了维持生命周期模式且有沙箱存在
                if self.maintain_lifecycle and len(self.sandboxes) > 0:
                    # 进入第二阶段，返回值表示是否应该继续创建
                    should_continue = self.maintain_sandboxes_lifecycle()

                    if should_continue:
                        # 返回True，表示发现有新容量，继续第一阶段
                        logger.info("检测到新容量，开始下一轮创建...")
                        phase_num += 1
                        continue_creating = True
                    else:
                        # 返回False，表示达到最大生命周期时间，结束测试
                        logger.info("已达到最大生命周期时间，测试结束")
                        continue_creating = False
                else:
                    # 没有启用维持生命周期模式，直接结束
                    continue_creating = False

            # 记录最大容量
            self.results['total_created'] = len(self.sandboxes)
            self.results['total_failed'] = self.failed_count
            self.results['max_capacity'] = len(self.sandboxes)

            # 获取最终统计信息
            logger.info("=" * 60)
            logger.info("最终阶段：获取统计信息和清理")
            logger.info("=" * 60)

            # 获取沙箱列表和节点信息
            logger.info("获取最终沙箱状态...")
            sandbox_list = self.get_sandbox_list_from_cli()
            node_info = self.get_node_info_from_nomad()

            # 分析分布
            if sandbox_list:
                distribution = self.analyze_distribution(sandbox_list, node_info)
                self.results['node_distribution'] = distribution['node_distribution']
                self.results['balance_metrics'] = distribution['metrics']

                # 打印分布统计
                logger.info("=" * 60)
                logger.info("沙箱分布统计")
                logger.info("=" * 60)

                metrics = distribution['metrics']
                logger.info(f"总节点数: {metrics.get('total_nodes', 0)}")
                logger.info(f"总沙箱数: {metrics.get('total_sandboxes', 0)}")
                logger.info(f"单节点最大: {metrics.get('max_per_node', 0)}")
                logger.info(f"单节点最小: {metrics.get('min_per_node', 0)}")
                logger.info(f"单节点平均: {metrics.get('avg_per_node', 0):.2f}")
                logger.info(f"单节点中位数: {metrics.get('median_per_node', 0):.2f}")

                if 'stddev' in metrics:
                    logger.info(f"标准差: {metrics['stddev']:.2f}")
                    logger.info(f"变异系数: {metrics['cv']:.4f}")
                    logger.info(f"均衡得分: {metrics['balance_score']:.2%} (越接近100%越均衡)")

                logger.info("各节点详细分布:")
                for node_name, info in sorted(
                    distribution['node_distribution'].items(),
                    key=lambda x: x[1]['sandbox_count'],
                    reverse=True
                ):
                    logger.info(f"  {node_name}: {info['sandbox_count']} 个沙箱 ({info['percentage']:.1f}%)")

        finally:
            # 清理资源
            if self.auto_cleanup:
                logger.info("=" * 60)
                logger.info("清理沙箱资源")
                logger.info("=" * 60)
                self.cleanup()
            else:
                logger.info("=" * 60)
                logger.info("跳过沙箱清理（--no-cleanup）")
                logger.info(f"保留 {len(self.sandboxes)} 个沙箱用于后续分析")
                logger.info("=" * 60)

    def cleanup(self):
        """清理所有创建的沙箱"""
        if not self.sandboxes:
            return

        # 先获取存活的沙箱列表
        logger.info("检查沙箱存活状态...")
        alive_sandboxes = set()

        # 尝试通过API获取
        sandbox_list = self.get_sandboxes_from_api()
        if not sandbox_list:
            # API失败，尝试CLI
            sandbox_list = self.get_sandbox_list_from_cli()

        if sandbox_list:
            alive_sandboxes = {sbx.get('sandbox_id') or sbx.get('sandboxId') or sbx.get('id')
                             for sbx in sandbox_list}
            logger.info(f"发现 {len(alive_sandboxes)} 个存活沙箱")
        else:
            logger.warning("无法获取存活沙箱列表，将尝试关闭所有沙箱")
            # 如果无法获取列表，假设所有沙箱都存活
            alive_sandboxes = {sbx.sandbox_id for sbx in self.sandboxes}

        # 统计
        success = 0
        failed = 0
        already_gone = 0

        for i, sandbox in enumerate(self.sandboxes, 1):
            sandbox_id = sandbox.sandbox_id

            # 检查沙箱是否存活
            if sandbox_id not in alive_sandboxes:
                logger.info(f"沙箱 {i}/{len(self.sandboxes)} (ID: {sandbox_id}) 已不存在，跳过关闭")
                already_gone += 1
                continue

            # 沙箱存活，尝试关闭
            try:
                logger.info(f"关闭沙箱 {i}/{len(self.sandboxes)} (ID: {sandbox_id})...")
                sandbox.kill()
                logger.info(f"✓ 沙箱 {i} 已关闭")
                success += 1
            except Exception as e:
                logger.error(f"✗ 沙箱 {i} 关闭失败: {e}")
                failed += 1

        logger.info(f"清理完成: {success} 成功, {failed} 失败, {already_gone} 已不存在")

    def save_results(self, output_file: str = 'outputs/06_sandbox_capacity.json'):
        """保存测试结果"""
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        logger.info(f"✓ 测试结果已保存到: {output_file}")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(
        description='E2B沙箱容量和负载均衡测试',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 每批创建10个沙箱，最多创建100个，批次间隔2秒
  python3 06_sandbox_capacity.py --batch-size 10 --max-sandboxes 100 --interval 2

  # 快速测试（小批次）
  python3 06_sandbox_capacity.py --batch-size 5 --max-sandboxes 50 --interval 1

  # 压力测试（大批次）
  python3 06_sandbox_capacity.py --batch-size 20 --max-sandboxes 500 --interval 3

  # 测试后不清理沙箱，保留用于后续分析
  python3 06_sandbox_capacity.py --batch-size 10 --max-sandboxes 100 --no-cleanup

  # 启用维持生命周期模式（默认初始目标为80%，即80个）
  python3 06_sandbox_capacity.py --batch-size 10 --max-sandboxes 100 --maintain-lifecycle --max-lifetime 3600 --check-interval 60

  # 自定义初始目标（第一阶段创建到50个，第二阶段逐步突破到100个）
  python3 06_sandbox_capacity.py --batch-size 10 --initial-target 50 --max-sandboxes 100 --maintain-lifecycle --max-lifetime 3600 --check-interval 60

  # 短时间测试（维持10分钟，每30秒检查一次）
  python3 06_sandbox_capacity.py --batch-size 10 --max-sandboxes 50 --maintain-lifecycle --max-lifetime 600 --check-interval 30
        """
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='每批创建的沙箱数量 (默认: 10)'
    )

    parser.add_argument(
        '--max-sandboxes',
        type=int,
        default=300,
        help='最大尝试创建的沙箱数 (默认: 300)'
    )

    parser.add_argument(
        '--interval',
        type=float,
        default=0.3,
        help='批次之间的间隔时间（秒） (默认: 0.3)'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=1500,
        help='单个沙箱的生命时间（秒） (默认: 1500)'
    )

    parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='测试完成后不清理沙箱，保留用于分析'
    )

    parser.add_argument(
        '--maintain-lifecycle',
        action='store_true',
        help='启用维持生命周期模式：创建沙箱后，定期检查并延长生命周期直到最大时间'
    )

    parser.add_argument(
        '--max-lifetime',
        type=int,
        default=3600,
        help='维持生命周期模式下的最大生命周期时间（秒） (默认: 3600秒，即1小时)'
    )

    parser.add_argument(
        '--check-interval',
        type=int,
        default=60,
        help='维持生命周期模式下检查沙箱存活状态的间隔（秒） (默认: 60)'
    )

    parser.add_argument(
        '--initial-target',
        type=int,
        default=None,
        help='第一阶段的初始目标沙箱数（默认：维持生命周期模式下为max-sandboxes的80%%，否则等于max-sandboxes）'
    )

    parser.add_argument(
        '--output',
        type=str,
        default='outputs/06_sandbox_capacity.json',
        help='输出文件路径 (默认: outputs/06_sandbox_capacity.json)'
    )

    args = parser.parse_args()

    # 创建测试器
    tester = SandboxCapacityTester(
        batch_size=args.batch_size,
        max_sandboxes=args.max_sandboxes,
        interval=args.interval,
        timeout=args.timeout,
        auto_cleanup=not args.no_cleanup,
        maintain_lifecycle=args.maintain_lifecycle,
        max_lifetime=args.max_lifetime,
        check_interval=args.check_interval,
        initial_target=args.initial_target
    )

    # 运行测试
    tester.run_test()

    # 保存结果
    tester.save_results(args.output)

    logger.info("=" * 60)
    logger.info("测试完成!")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
