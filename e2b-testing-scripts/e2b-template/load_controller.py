#!/usr/bin/env python3
"""
负载控制服务
功能：
1. 作为后台服务运行，持续生成负载
2. 默认以 50% CPU 和 50% 内存使用率运行
3. 通过配置文件接收目标调整指令
4. 定期保存状态到文件供查询
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Optional, List
import signal
import sys
import os
import json


class LoadControllerService:
    """负载控制服务：持续运行并动态调整负载"""

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        initial_target_cpu: float = 50.0,
        initial_target_memory: float = 50.0,
        initial_target_disk: float = 50.0
    ):
        self.base_url = base_url
        self.target_cpu = initial_target_cpu
        self.target_memory = initial_target_memory
        self.target_disk = initial_target_disk
        self.current_request_interval = 1.0  # 当前请求间隔（秒）
        self.running = True
        self.worker_tasks = []
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'start_time': None
        }

        # 内存占用控制
        self.memory_ballast: List[bytearray] = []  # 用于占用内存的数据
        self.target_memory_bytes = 0

        # 磁盘占用控制
        self.disk_file_path = "/tmp/load_controller_disk_ballast.bin"
        self.target_disk_bytes = 0

        # 所有测试接口及其权重（权重从大到小）
        # 权重越大，调用越频繁
        self.endpoints = {
            'health': {'weight': 5.0, 'path': '/health'},      # 健康检查，权重最大
            'network': {'weight': 4.0, 'path': '/network'},    # 网络 I/O（公网）
            'action': {'weight': 3.0, 'path': '/action'},      # 文件 I/O
            'terminal': {'weight': 2.0, 'path': '/terminal'},  # 终端命令
            'sum': {'weight': 1.0, 'path': '/sum'},            # 文件统计
            'search': {'weight': 0.5, 'path': '/search'}       # 浏览器，权重最小（最重）
        }

    async def get_current_cpu(self) -> float:
        """从 Node Exporter 获取当前 CPU 使用率"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:9100/metrics', timeout=5) as response:
                    if response.status != 200:
                        return 0.0

                    text = await response.text()

                    # 简单解析 CPU 使用率
                    cpu_idle = 0
                    cpu_total = 0
                    for line in text.split('\n'):
                        if line.startswith('node_cpu_seconds_total'):
                            parts = line.split()
                            if len(parts) >= 2:
                                value = float(parts[1])
                                cpu_total += value
                                if 'mode="idle"' in parts[0]:
                                    cpu_idle += value

                    if cpu_total > 0:
                        return ((cpu_total - cpu_idle) / cpu_total) * 100
                    return 0.0

        except Exception as e:
            print(f"[监控] 获取 CPU 使用率失败: {e}")
            return 0.0

    async def get_current_memory(self) -> float:
        """从 Node Exporter 获取当前内存使用率"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:9100/metrics', timeout=5) as response:
                    if response.status != 200:
                        return 0.0

                    text = await response.text()

                    # 解析内存指标
                    mem_total = 0
                    mem_available = 0

                    for line in text.split('\n'):
                        if line.startswith('node_memory_MemTotal_bytes'):
                            parts = line.split()
                            if len(parts) >= 2:
                                mem_total = float(parts[1])
                        elif line.startswith('node_memory_MemAvailable_bytes'):
                            parts = line.split()
                            if len(parts) >= 2:
                                mem_available = float(parts[1])

                    if mem_total > 0:
                        used = mem_total - mem_available
                        return (used / mem_total) * 100
                    return 0.0

        except Exception as e:
            print(f"[监控] 获取内存使用率失败: {e}")
            return 0.0

    async def get_current_disk(self) -> float:
        """从 Node Exporter 获取当前磁盘使用率"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:9100/metrics', timeout=5) as response:
                    if response.status != 200:
                        return 0.0

                    text = await response.text()

                    # 解析根文件系统磁盘指标
                    fs_size = 0
                    fs_avail = 0

                    for line in text.split('\n'):
                        # 只关注根文件系统 (mountpoint="/")
                        if 'mountpoint="/"' in line and 'fstype=' in line:
                            if line.startswith('node_filesystem_size_bytes'):
                                parts = line.split()
                                if len(parts) >= 2:
                                    fs_size = float(parts[1])
                            elif line.startswith('node_filesystem_avail_bytes'):
                                parts = line.split()
                                if len(parts) >= 2:
                                    fs_avail = float(parts[1])

                    if fs_size > 0:
                        used = fs_size - fs_avail
                        return (used / fs_size) * 100
                    return 0.0

        except Exception as e:
            print(f"[监控] 获取磁盘使用率失败: {e}")
            return 0.0

    async def get_total_memory_bytes(self) -> int:
        """从 Node Exporter 获取系统总内存（字节）"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:9100/metrics', timeout=5) as response:
                    if response.status != 200:
                        return 0

                    text = await response.text()

                    for line in text.split('\n'):
                        if line.startswith('node_memory_MemTotal_bytes'):
                            parts = line.split()
                            if len(parts) >= 2:
                                return int(float(parts[1]))
                    return 0

        except Exception:
            return 0

    async def get_total_disk_bytes(self) -> int:
        """从 Node Exporter 获取系统总磁盘空间（字节）"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:9100/metrics', timeout=5) as response:
                    if response.status != 200:
                        return 0

                    text = await response.text()

                    for line in text.split('\n'):
                        if 'mountpoint="/"' in line and line.startswith('node_filesystem_size_bytes'):
                            parts = line.split()
                            if len(parts) >= 2:
                                return int(float(parts[1]))
                    return 0

        except Exception:
            return 0

    async def adjust_memory(self):
        """调整内存占用以达到目标"""
        try:
            current_memory_percent = await self.get_current_memory()
            total_memory = await self.get_total_memory_bytes()

            if total_memory == 0:
                return

            # 计算目标内存字节数
            target_bytes = int(total_memory * self.target_memory / 100)

            # 计算当前 ballast 占用的内存
            current_ballast_bytes = sum(len(chunk) for chunk in self.memory_ballast)

            # 计算需要调整的内存量
            delta_bytes = target_bytes - current_ballast_bytes

            if abs(delta_bytes) > 100 * 1024 * 1024:  # 如果差异超过 100MB
                if delta_bytes > 0:
                    # 需要增加内存
                    chunk_size = min(delta_bytes, 100 * 1024 * 1024)  # 每次最多分配 100MB
                    chunk = bytearray(chunk_size)
                    # 写入数据以确保内存真正分配
                    for i in range(0, len(chunk), 4096):
                        chunk[i] = 1
                    self.memory_ballast.append(chunk)
                    print(f"[内存] 增加 {chunk_size / 1024 / 1024:.1f}MB "
                          f"(系统内存: {current_memory_percent:.1f}%, 目标: {self.target_memory:.1f}%, "
                          f"Ballast: {(current_ballast_bytes + chunk_size) / 1024 / 1024:.1f}MB)")
                else:
                    # 需要释放内存
                    if self.memory_ballast:
                        released = self.memory_ballast.pop()
                        released_size = len(released)
                        del released
                        print(f"[内存] 释放 {released_size / 1024 / 1024:.1f}MB "
                              f"(系统内存: {current_memory_percent:.1f}%, 目标: {self.target_memory:.1f}%, "
                              f"Ballast: {(current_ballast_bytes - released_size) / 1024 / 1024:.1f}MB)")
        except Exception as e:
            print(f"[内存] 调整内存失败: {e}")

    async def adjust_disk(self):
        """调整磁盘占用以达到目标"""
        try:
            current_disk_percent = await self.get_current_disk()
            total_disk = await self.get_total_disk_bytes()

            if total_disk == 0:
                return

            # 计算目标磁盘字节数
            target_bytes = int(total_disk * self.target_disk / 100)

            # 获取当前文件大小
            current_bytes = 0
            if os.path.exists(self.disk_file_path):
                current_bytes = os.path.getsize(self.disk_file_path)

            # 计算需要调整的磁盘空间
            delta_bytes = target_bytes - current_bytes

            if abs(delta_bytes) > 100 * 1024 * 1024:  # 如果差异超过 100MB
                if delta_bytes > 0:
                    # 需要增加磁盘占用
                    chunk_size = min(delta_bytes, 500 * 1024 * 1024)  # 每次最多增加 500MB

                    # 以追加模式写入文件
                    with open(self.disk_file_path, 'ab') as f:
                        # 写入随机数据
                        chunk = bytearray(chunk_size)
                        for i in range(0, len(chunk), 4096):
                            chunk[i] = i % 256
                        f.write(chunk)

                    print(f"[磁盘] 增加 {chunk_size / 1024 / 1024:.1f}MB "
                          f"(系统磁盘: {current_disk_percent:.1f}%, 目标: {self.target_disk:.1f}%, "
                          f"Ballast: {(current_bytes + chunk_size) / 1024 / 1024:.1f}MB)")
                else:
                    # 需要释放磁盘空间
                    if current_bytes > 0:
                        new_size = max(0, current_bytes + delta_bytes)
                        if new_size == 0:
                            os.remove(self.disk_file_path)
                            print(f"[磁盘] 删除文件 "
                                  f"(系统磁盘: {current_disk_percent:.1f}%, 目标: {self.target_disk:.1f}%)")
                        else:
                            os.truncate(self.disk_file_path, new_size)
                            print(f"[磁盘] 减少 {abs(delta_bytes) / 1024 / 1024:.1f}MB "
                                  f"(系统磁盘: {current_disk_percent:.1f}%, 目标: {self.target_disk:.1f}%, "
                                  f"Ballast: {new_size / 1024 / 1024:.1f}MB)")
        except Exception as e:
            print(f"[磁盘] 调整磁盘失败: {e}")

    async def worker(self, endpoint_name: str, worker_id: int):
        """
        工作协程：持续向指定接口发送请求

        Args:
            endpoint_name: 接口名称 (action, search, terminal, network, sum)
            worker_id: Worker ID
        """
        endpoint = self.endpoints[endpoint_name]
        url = f"{self.base_url}{endpoint['path']}"
        weight = endpoint['weight']

        print(f"[Worker] 启动 {endpoint_name} worker {worker_id}")

        while self.running:
            try:
                async with aiohttp.ClientSession() as session:
                    try:
                        # health 和 sum 使用 GET，其他使用 POST
                        if endpoint_name in ['health', 'sum']:
                            async with session.get(url, timeout=30) as response:
                                self.stats['total_requests'] += 1
                                if response.status == 200:
                                    self.stats['successful_requests'] += 1
                                else:
                                    self.stats['failed_requests'] += 1
                        else:
                            async with session.post(url, timeout=30) as response:
                                self.stats['total_requests'] += 1
                                if response.status == 200:
                                    self.stats['successful_requests'] += 1
                                else:
                                    self.stats['failed_requests'] += 1
                    except Exception:
                        self.stats['failed_requests'] += 1

                # 根据当前请求间隔和权重计算休眠时间
                # 权重越大的接口，调用越频繁（休眠时间越短）
                sleep_time = self.current_request_interval / weight
                await asyncio.sleep(sleep_time)

            except Exception as e:
                if self.running:
                    print(f"[Worker-{endpoint_name}-{worker_id}] 错误: {e}")
                await asyncio.sleep(1)

    async def load_config(self):
        """从配置文件加载目标设置"""
        try:
            config_file = "/tmp/load_controller_config.json"
            if os.path.exists(config_file):
                import json
                with open(config_file, 'r') as f:
                    config = json.load(f)

                    new_cpu = config.get('target_cpu', self.target_cpu)
                    new_memory = config.get('target_memory', self.target_memory)
                    new_disk = config.get('target_disk', self.target_disk)

                    if new_cpu != self.target_cpu:
                        self.target_cpu = new_cpu
                        print(f"[配置] CPU 目标更新: {self.target_cpu}%")

                    if new_memory != self.target_memory:
                        self.target_memory = new_memory
                        print(f"[配置] 内存目标更新: {self.target_memory}%")

                    if new_disk != self.target_disk:
                        self.target_disk = new_disk
                        print(f"[配置] 磁盘目标更新: {self.target_disk}%")
        except Exception as e:
            print(f"[配置] 加载配置失败: {e}")

    async def save_status(self, current_cpu: float, current_memory: float, current_disk: float):
        """保存当前状态到文件"""
        try:
            status_file = "/tmp/load_controller_status.json"
            import json
            status = self.get_status()
            status['current_cpu'] = round(current_cpu, 1)
            status['current_memory'] = round(current_memory, 1)
            status['current_disk'] = round(current_disk, 1)
            status['timestamp'] = datetime.now().isoformat()

            with open(status_file, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            print(f"[状态] 保存状态失败: {e}")

    async def adjust_concurrency(self):
        """定期调整并发数以达到目标 CPU、内存和磁盘使用率"""
        while self.running:
            try:
                # 加载配置（检查是否有新的目标设置）
                await self.load_config()

                # 获取当前使用率
                current_cpu = await self.get_current_cpu()
                current_memory = await self.get_current_memory()
                current_disk = await self.get_current_disk()

                # 保存状态
                await self.save_status(current_cpu, current_memory, current_disk)

                # === CPU 控制 ===
                error = self.target_cpu - current_cpu

                # P 控制器 - 调整请求间隔而不是并发数
                # 目标 CPU 越高，间隔越短（请求越频繁）

                # 将目标 CPU 映射到请求间隔
                if self.target_cpu == 0:
                    target_interval = 10.0  # 几乎不发请求
                elif self.target_cpu <= 50:
                    # 0-50%: 线性映射到 10.0-1.0s
                    target_interval = 10.0 - (self.target_cpu / 50.0) * 9.0
                elif self.target_cpu <= 75:
                    # 50-75%: 线性映射到 1.0-0.5s
                    target_interval = 1.0 - ((self.target_cpu - 50) / 25.0) * 0.5
                elif self.target_cpu <= 85:
                    # 75-85%: 线性映射到 0.5-0.3s
                    target_interval = 0.5 - ((self.target_cpu - 75) / 10.0) * 0.2
                elif self.target_cpu <= 95:
                    # 85-95%: 线性映射到 0.3-0.1s
                    target_interval = 0.3 - ((self.target_cpu - 85) / 10.0) * 0.2
                else:
                    # 95-100%: 线性映射到 0.1-0.05s
                    target_interval = 0.1 - ((self.target_cpu - 95) / 5.0) * 0.05

                # 根据当前 CPU 使用率微调
                if abs(error) > 10:
                    # 偏差较大，快速调整
                    adjustment_factor = 1.0 - (error / 100.0) * 0.5
                    new_interval = self.current_request_interval * adjustment_factor
                else:
                    # 偏差较小，缓慢调整
                    new_interval = target_interval

                # 限制间隔范围
                new_interval = max(0.05, min(10.0, new_interval))

                if abs(new_interval - self.current_request_interval) > 0.01:
                    print(f"[CPU控制] 调整请求间隔: {self.current_request_interval:.3f}s -> {new_interval:.3f}s "
                          f"(当前: {current_cpu:.1f}%, 目标: {self.target_cpu:.1f}%)")
                    self.current_request_interval = new_interval

                # === 内存控制 ===
                await self.adjust_memory()

                # === 磁盘控制 ===
                await self.adjust_disk()

                # 每个调整周期打印状态
                uptime = (datetime.now() - self.stats['start_time']).total_seconds() if self.stats['start_time'] else 0
                print(f"[状态] 运行: {int(uptime)}s | CPU: {current_cpu:.1f}%/{self.target_cpu:.1f}% | "
                      f"内存: {current_memory:.1f}%/{self.target_memory:.1f}% | "
                      f"磁盘: {current_disk:.1f}%/{self.target_disk:.1f}% | "
                      f"请求: {self.stats['total_requests']}")

            except Exception as e:
                print(f"[控制器] 调整错误: {e}")

            await asyncio.sleep(5)  # 每 5 秒调整一次

    async def run(self):
        """运行负载控制服务"""
        print("=" * 70)
        print("负载控制服务启动")
        print(f"目标 CPU 使用率: {self.target_cpu}%")
        print(f"目标内存使用率: {self.target_memory}%")
        print(f"目标磁盘使用率: {self.target_disk}%")
        print(f"测试接口: {', '.join(self.endpoints.keys())}")
        print("策略: 所有接口持续调用，通过频率控制压力；动态调整内存和磁盘占用")
        print("=" * 70)

        self.stats['start_time'] = datetime.now()

        # 为每种接口启动固定数量的 worker
        # 每种接口 2 个 worker 以保证覆盖
        workers_per_endpoint = 2

        for endpoint_name in self.endpoints.keys():
            for worker_id in range(workers_per_endpoint):
                task = asyncio.create_task(
                    self.worker(endpoint_name, worker_id)
                )
                self.worker_tasks.append(task)

        print(f"[启动] 已启动 {len(self.worker_tasks)} 个 workers")
        print(f"[接口] {', '.join(self.endpoints.keys())}")

        # 启动控制器
        controller_task = asyncio.create_task(self.adjust_concurrency())

        # 等待服务运行
        try:
            await controller_task
        except asyncio.CancelledError:
            print("\n负载控制服务正在关闭...")
            self.running = False

            # 取消所有 worker
            for task in self.worker_tasks:
                task.cancel()

            await asyncio.gather(*self.worker_tasks, return_exceptions=True)

            print("负载控制服务已停止")

    def set_target_cpu(self, target: float):
        """设置目标 CPU 使用率"""
        if 0 <= target <= 100:
            self.target_cpu = target
            print(f"[控制器] 目标 CPU 使用率更新为: {target}%")
            return True
        return False

    def get_status(self) -> Dict:
        """获取当前状态"""
        uptime = (datetime.now() - self.stats['start_time']).total_seconds() if self.stats['start_time'] else 0

        # 获取当前内存和磁盘信息
        memory_ballast_mb = sum(len(chunk) for chunk in self.memory_ballast) / 1024 / 1024
        disk_ballast_mb = 0
        if os.path.exists(self.disk_file_path):
            disk_ballast_mb = os.path.getsize(self.disk_file_path) / 1024 / 1024

        return {
            'running': self.running,
            'target_cpu': self.target_cpu,
            'target_memory': self.target_memory,
            'target_disk': self.target_disk,
            'current_request_interval': round(self.current_request_interval, 3),
            'memory_ballast_mb': round(memory_ballast_mb, 1),
            'disk_ballast_mb': round(disk_ballast_mb, 1),
            'active_endpoints': list(self.endpoints.keys()),
            'workers_count': len(self.worker_tasks),
            'uptime_seconds': round(uptime, 1),
            'total_requests': self.stats['total_requests'],
            'successful_requests': self.stats['successful_requests'],
            'failed_requests': self.stats['failed_requests']
        }


# 全局实例
controller = LoadControllerService(
    initial_target_cpu=50.0,
    initial_target_memory=50.0,
    initial_target_disk=50.0
)


def signal_handler(sig, frame):
    """处理退出信号"""
    print("\n收到退出信号，正在关闭服务...")
    controller.running = False

    # 清理资源
    try:
        # 清理内存
        controller.memory_ballast.clear()
        print("[清理] 已释放内存")

        # 清理磁盘文件
        if os.path.exists(controller.disk_file_path):
            os.remove(controller.disk_file_path)
            print(f"[清理] 已删除磁盘文件: {controller.disk_file_path}")
    except Exception as e:
        print(f"[清理] 清理资源失败: {e}")

    sys.exit(0)


async def main():
    """主函数"""
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 运行服务
    await controller.run()


if __name__ == '__main__':
    asyncio.run(main())
