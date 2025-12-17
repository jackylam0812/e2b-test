#!/usr/bin/env python3
"""
E2B云存储集成性能测试脚本
测试指标:
- 对象存储上传性能(小文件/大文件/并行)
- 对象存储下载性能(小文件/大文件/并行)
- 对象存储操作延迟(列举/元数据读取)

支持的云存储平台:
- AWS S3
- Google Cloud Storage (GCS)
- Azure Blob Storage
"""

import time
import json
import os
import sys
import tempfile
import concurrent.futures
from typing import Dict, List, Optional
import boto3
from google.cloud import storage
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.identity import DefaultAzureCredential, AzureCliCredential

# 导入彩色日志
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import get_logger

logger = get_logger(__name__)

def create_test_file(size_mb: int) -> str:
    """
    创建测试文件
    
    Args:
        size_mb: 文件大小(MB)
    
    Returns:
        文件路径
    """
    file_path = f"/tmp/test_file_{size_mb}mb.bin"
    
    # 创建指定大小的随机文件
    with open(file_path, 'wb') as f:
        f.write(os.urandom(size_mb * 1024 * 1024))
    
    return file_path


def test_s3_small_file_upload(bucket_name: str, region: str = "us-east-1", iterations: int = 3) -> Dict:
    """
    测试S3小文件上传速度(1MB)
    
    Args:
        bucket_name: S3桶名称
        region: AWS区域
        iterations: 测试次数
    
    Returns:
        包含上传速度统计的字典
    """
    logger.info(f"开始测试S3小文件上传速度(1MB, {iterations}次)...")
    
    # 创建1MB测试文件
    test_file = create_test_file(1)
    file_size_mb = 1
    
    speeds = []
    
    try:
        s3_client = boto3.client('s3', region_name=region)
        
        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")
            
            object_key = f"test_small_file_{i}.bin"
            
            start_time = time.time()
            s3_client.upload_file(test_file, bucket_name, object_key)
            end_time = time.time()
            
            upload_time = end_time - start_time
            upload_speed_mbps = file_size_mb / upload_time
            speeds.append(upload_speed_mbps)
            
            logger.info(f"{upload_speed_mbps:.2f} MB/s")
            
            # 清理
            s3_client.delete_object(Bucket=bucket_name, Key=object_key)
            
            time.sleep(1)
        
        avg_speed = sum(speeds) / len(speeds)
        
        logger.info(f"✓ 平均上传速度: {avg_speed:.2f} MB/s")
        
        # 清理测试文件
        os.remove(test_file)
        
        return {
            "success": True,
            "file_size_mb": file_size_mb,
            "speeds_mbps": speeds,
            "average_speed_mbps": avg_speed
        }
    
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_s3_large_file_upload(bucket_name: str, region: str = "us-east-1", iterations: int = 3) -> Dict:
    """
    测试S3大文件上传速度(1GB)
    
    Args:
        bucket_name: S3桶名称
        region: AWS区域
        iterations: 测试次数
    
    Returns:
        包含上传速度统计的字典
    """
    logger.info(f"开始测试S3大文件上传速度(1GB, {iterations}次)...")
    
    # 创建1GB测试文件
    test_file = create_test_file(1024)
    file_size_mb = 1024
    
    speeds = []
    
    try:
        s3_client = boto3.client('s3', region_name=region)
        
        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")
            
            object_key = f"test_large_file_{i}.bin"
            
            start_time = time.time()
            s3_client.upload_file(test_file, bucket_name, object_key)
            end_time = time.time()
            
            upload_time = end_time - start_time
            upload_speed_mbps = file_size_mb / upload_time
            speeds.append(upload_speed_mbps)
            
            logger.info(f"{upload_speed_mbps:.2f} MB/s")
            
            # 清理
            s3_client.delete_object(Bucket=bucket_name, Key=object_key)
            
            time.sleep(1)
        
        avg_speed = sum(speeds) / len(speeds)
        
        logger.info(f"✓ 平均上传速度: {avg_speed:.2f} MB/s")
        
        # 清理测试文件
        os.remove(test_file)
        
        return {
            "success": True,
            "file_size_mb": file_size_mb,
            "speeds_mbps": speeds,
            "average_speed_mbps": avg_speed
        }
    
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_s3_parallel_upload(bucket_name: str, region: str = "us-east-1", file_count: int = 10) -> Dict:
    """
    测试S3并行上传吞吐量(同时上传10个100MB文件)
    
    Args:
        bucket_name: S3桶名称
        region: AWS区域
        file_count: 文件数量
    
    Returns:
        包含并行吞吐量的字典
    """
    logger.info(f"开始测试S3并行上传吞吐量({file_count}个100MB文件)...")
    
    # 创建100MB测试文件
    test_file = create_test_file(100)
    file_size_mb = 100
    total_size_mb = file_size_mb * file_count
    
    try:
        s3_client = boto3.client('s3', region_name=region)
        
        def upload_file(index):
            object_key = f"test_parallel_{index}.bin"
            s3_client.upload_file(test_file, bucket_name, object_key)
            return object_key
        
        start_time = time.time()
        
        # 并行上传
        with concurrent.futures.ThreadPoolExecutor(max_workers=file_count) as executor:
            object_keys = list(executor.map(upload_file, range(file_count)))
        
        end_time = time.time()
        
        total_time = end_time - start_time
        throughput_mbps = total_size_mb / total_time
        
        logger.info(f"✓ 总数据量: {total_size_mb} MB")
        logger.info(f"✓ 总耗时: {total_time:.2f} 秒")
        logger.info(f"✓ 并行吞吐量: {throughput_mbps:.2f} MB/s")
        
        # 清理
        for object_key in object_keys:
            s3_client.delete_object(Bucket=bucket_name, Key=object_key)
        
        os.remove(test_file)
        
        return {
            "success": True,
            "total_size_mb": total_size_mb,
            "total_time_seconds": total_time,
            "parallel_throughput_mbps": throughput_mbps
        }
    
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_s3_small_file_download(bucket_name: str, region: str = "us-east-1", iterations: int = 3) -> Dict:
    """
    测试S3小文件下载速度(1MB)
    
    Args:
        bucket_name: S3桶名称
        region: AWS区域
        iterations: 测试次数
    
    Returns:
        包含下载速度统计的字典
    """
    logger.info(f"开始测试S3小文件下载速度(1MB, {iterations}次)...")
    
    # 创建并上传1MB测试文件
    test_file = create_test_file(1)
    file_size_mb = 1
    object_key = "test_download_small.bin"
    
    speeds = []
    
    try:
        s3_client = boto3.client('s3', region_name=region)
        
        # 上传文件
        s3_client.upload_file(test_file, bucket_name, object_key)
        
        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")
            
            download_path = f"/tmp/download_{i}.bin"
            
            start_time = time.time()
            s3_client.download_file(bucket_name, object_key, download_path)
            end_time = time.time()
            
            download_time = end_time - start_time
            download_speed_mbps = file_size_mb / download_time
            speeds.append(download_speed_mbps)
            
            logger.info(f"{download_speed_mbps:.2f} MB/s")
            
            # 清理
            os.remove(download_path)
            
            time.sleep(1)
        
        avg_speed = sum(speeds) / len(speeds)
        
        logger.info(f"✓ 平均下载速度: {avg_speed:.2f} MB/s")
        
        # 清理
        s3_client.delete_object(Bucket=bucket_name, Key=object_key)
        os.remove(test_file)
        
        return {
            "success": True,
            "file_size_mb": file_size_mb,
            "speeds_mbps": speeds,
            "average_speed_mbps": avg_speed
        }
    
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_s3_large_file_download(bucket_name: str, region: str = "us-east-1", iterations: int = 3) -> Dict:
    """
    测试S3大文件下载速度(1GB)
    
    Args:
        bucket_name: S3桶名称
        region: AWS区域
        iterations: 测试次数
    
    Returns:
        包含下载速度统计的字典
    """
    logger.info(f"开始测试S3大文件下载速度(1GB, {iterations}次)...")
    
    # 创建并上传1GB测试文件
    test_file = create_test_file(1024)
    file_size_mb = 1024
    object_key = "test_download_large.bin"
    
    speeds = []
    
    try:
        s3_client = boto3.client('s3', region_name=region)
        
        # 上传文件
        logger.info("  上传测试文件...")
        s3_client.upload_file(test_file, bucket_name, object_key)
        
        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")
            
            download_path = f"/tmp/download_large_{i}.bin"
            
            start_time = time.time()
            s3_client.download_file(bucket_name, object_key, download_path)
            end_time = time.time()
            
            download_time = end_time - start_time
            download_speed_mbps = file_size_mb / download_time
            speeds.append(download_speed_mbps)
            
            logger.info(f"{download_speed_mbps:.2f} MB/s")
            
            # 清理
            os.remove(download_path)
            
            time.sleep(1)
        
        avg_speed = sum(speeds) / len(speeds)
        
        logger.info(f"✓ 平均下载速度: {avg_speed:.2f} MB/s")
        
        # 清理
        s3_client.delete_object(Bucket=bucket_name, Key=object_key)
        os.remove(test_file)
        
        return {
            "success": True,
            "file_size_mb": file_size_mb,
            "speeds_mbps": speeds,
            "average_speed_mbps": avg_speed
        }
    
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_s3_object_list_latency(bucket_name: str, region: str = "us-east-1", iterations: int = 3) -> Dict:
    """
    测试S3对象列举延迟
    
    Args:
        bucket_name: S3桶名称
        region: AWS区域
        iterations: 测试次数
    
    Returns:
        包含列举延迟统计的字典
    """
    logger.info(f"开始测试S3对象列举延迟({iterations}次)...")
    
    latencies = []
    
    try:
        s3_client = boto3.client('s3', region_name=region)
        
        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")
            
            start_time = time.time()
            response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=100)
            end_time = time.time()
            
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
            
            object_count = len(response.get('Contents', []))
            
            logger.info(f"{latency_ms:.2f} ms (对象数: {object_count})")
            
            time.sleep(1)
        
        avg_latency = sum(latencies) / len(latencies)
        
        logger.info(f"✓ 平均列举延迟: {avg_latency:.2f} ms")
        
        return {
            "success": True,
            "latencies_ms": latencies,
            "average_latency_ms": avg_latency
        }
    
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_s3_metadata_read_latency(bucket_name: str, object_key: str, region: str = "us-east-1", iterations: int = 3) -> Dict:
    """
    测试S3对象元数据读取延迟

    Args:
        bucket_name: S3桶名称
        object_key: 对象键
        region: AWS区域
        iterations: 测试次数

    Returns:
        包含元数据读取延迟统计的字典
    """
    logger.info(f"开始测试S3对象元数据读取延迟({iterations}次)...")

    latencies = []

    try:
        s3_client = boto3.client('s3', region_name=region)

        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")

            start_time = time.time()
            response = s3_client.head_object(Bucket=bucket_name, Key=object_key)
            end_time = time.time()

            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

            logger.info(f"{latency_ms:.2f} ms")

            time.sleep(1)

        avg_latency = sum(latencies) / len(latencies)

        logger.info(f"✓ 平均元数据读取延迟: {avg_latency:.2f} ms")

        return {
            "success": True,
            "latencies_ms": latencies,
            "average_latency_ms": avg_latency
        }

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


# ==================== Azure Blob Storage 辅助函数 ====================

def get_azure_blob_service_client(account_name: Optional[str] = None, connection_string: Optional[str] = None) -> BlobServiceClient:
    """
    获取 Azure BlobServiceClient，支持多种认证方式
    认证顺序（与 Golang 实现一致）：
    1. Connection String（如果提供）
    2. Managed Identity（优先，支持 AZURE_CLIENT_ID 环境变量）
    3. Azure CLI（回退）
    4. DefaultAzureCredential（最后尝试）

    Args:
        account_name: Azure 存储账户名称（用于 Managed Identity/CLI 认证）
        connection_string: Azure 连接字符串（传统认证方式）

    Returns:
        BlobServiceClient 实例
    """
    # 优先使用 connection_string
    if connection_string:
        return BlobServiceClient.from_connection_string(connection_string)

    # 使用 account_name + Azure Identity 认证
    if account_name:
        account_url = f"https://{account_name}.blob.core.windows.net"

        # 1. 优先尝试 Managed Identity（与 Golang 实现一致）
        try:
            from azure.identity import ManagedIdentityCredential

            # 检查是否有 AZURE_CLIENT_ID（用户分配的托管标识）
            client_id = os.getenv('AZURE_CLIENT_ID')
            if client_id:
                credential = ManagedIdentityCredential(client_id=client_id)
                logger.info(f"  尝试使用用户分配的 Managed Identity (Client ID: {client_id[:8]}...)")
            else:
                credential = ManagedIdentityCredential()
                logger.info(f"  尝试使用系统分配的 Managed Identity")

            blob_service_client = BlobServiceClient(account_url, credential=credential)
            # 测试连接
            list(blob_service_client.list_containers(results_per_page=1))
            logger.info(f"✓ 使用 Managed Identity 认证连接到: {account_name}")
            return blob_service_client
        except Exception as e:
            logger.error(f"  Managed Identity 认证失败: {str(e)[:100]}")

        # 2. 回退到 Azure CLI 认证
        try:
            credential = AzureCliCredential()
            blob_service_client = BlobServiceClient(account_url, credential=credential)
            # 测试连接
            list(blob_service_client.list_containers(results_per_page=1))
            logger.info(f"✓ 使用 Azure CLI 认证连接到: {account_name}")
            return blob_service_client
        except Exception as e:
            logger.error(f"  Azure CLI 认证失败: {str(e)[:100]}")

        # 3. 最后尝试 DefaultAzureCredential
        try:
            credential = DefaultAzureCredential()
            blob_service_client = BlobServiceClient(account_url, credential=credential)
            # 测试连接
            list(blob_service_client.list_containers(results_per_page=1))
            logger.info(f"✓ 使用 DefaultAzureCredential 连接到: {account_name}")
            return blob_service_client
        except Exception as e:
            raise Exception(f"所有认证方式都失败。最后错误: {e}")

    raise ValueError("必须提供 connection_string 或 account_name")


# ==================== Azure Blob Storage 测试函数 ====================

def test_azure_small_file_upload(connection_string: Optional[str] = None, container_name: str = None,
                                  account_name: Optional[str] = None, iterations: int = 3) -> Dict:
    """
    测试Azure Blob Storage小文件上传速度(1MB)

    Args:
        connection_string: Azure存储账户连接字符串（可选）
        container_name: 容器名称
        account_name: Azure存储账户名称（用于CLI认证，可选）
        iterations: 测试次数

    Returns:
        包含上传速度统计的字典
    """
    logger.info(f"开始测试Azure Blob Storage小文件上传速度(1MB, {iterations}次)...")

    # 创建1MB测试文件
    test_file = create_test_file(1)
    file_size_mb = 1

    speeds = []

    try:
        blob_service_client = get_azure_blob_service_client(account_name=account_name, connection_string=connection_string)
        container_client = blob_service_client.get_container_client(container_name)

        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")

            blob_name = f"test_small_file_{i}.bin"
            blob_client = container_client.get_blob_client(blob_name)

            start_time = time.time()
            with open(test_file, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            end_time = time.time()

            upload_time = end_time - start_time
            upload_speed_mbps = file_size_mb / upload_time
            speeds.append(upload_speed_mbps)

            logger.info(f"{upload_speed_mbps:.2f} MB/s")

            # 清理
            blob_client.delete_blob()

            time.sleep(1)

        avg_speed = sum(speeds) / len(speeds)

        logger.info(f"✓ 平均上传速度: {avg_speed:.2f} MB/s")

        # 清理测试文件
        os.remove(test_file)

        return {
            "success": True,
            "file_size_mb": file_size_mb,
            "speeds_mbps": speeds,
            "average_speed_mbps": avg_speed
        }

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_azure_large_file_upload(connection_string: Optional[str] = None, container_name: str = None,
                                  account_name: Optional[str] = None, iterations: int = 3) -> Dict:
    """
    测试Azure Blob Storage大文件上传速度(1GB)

    Args:
        connection_string: Azure存储账户连接字符串（可选）
        container_name: 容器名称
        account_name: Azure存储账户名称（用于CLI认证，可选）
        iterations: 测试次数

    Returns:
        包含上传速度统计的字典
    """
    logger.info(f"开始测试Azure Blob Storage大文件上传速度(1GB, {iterations}次)...")

    # 创建1GB测试文件
    test_file = create_test_file(1024)
    file_size_mb = 1024

    speeds = []

    try:
        blob_service_client = get_azure_blob_service_client(account_name=account_name, connection_string=connection_string)
        container_client = blob_service_client.get_container_client(container_name)

        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")

            blob_name = f"test_large_file_{i}.bin"
            blob_client = container_client.get_blob_client(blob_name)

            start_time = time.time()
            with open(test_file, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            end_time = time.time()

            upload_time = end_time - start_time
            upload_speed_mbps = file_size_mb / upload_time
            speeds.append(upload_speed_mbps)

            logger.info(f"{upload_speed_mbps:.2f} MB/s")

            # 清理
            blob_client.delete_blob()

            time.sleep(1)

        avg_speed = sum(speeds) / len(speeds)

        logger.info(f"✓ 平均上传速度: {avg_speed:.2f} MB/s")

        # 清理测试文件
        os.remove(test_file)

        return {
            "success": True,
            "file_size_mb": file_size_mb,
            "speeds_mbps": speeds,
            "average_speed_mbps": avg_speed
        }

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_azure_parallel_upload(connection_string: Optional[str] = None, container_name: Optional[str] = None, account_name: Optional[str] = None, file_count: int = 10) -> Dict:
    """
    测试Azure Blob Storage并行上传吞吐量(同时上传10个100MB文件)

    Args:
        connection_string: Azure存储账户连接字符串
        container_name: 容器名称
        file_count: 文件数量

    Returns:
        包含并行吞吐量的字典
    """
    logger.info(f"开始测试Azure Blob Storage并行上传吞吐量({file_count}个100MB文件)...")

    # 创建100MB测试文件
    test_file = create_test_file(100)
    file_size_mb = 100
    total_size_mb = file_size_mb * file_count

    try:
        blob_service_client = get_azure_blob_service_client(account_name=account_name, connection_string=connection_string)
        container_client = blob_service_client.get_container_client(container_name)

        def upload_file(index):
            blob_name = f"test_parallel_{index}.bin"
            blob_client = container_client.get_blob_client(blob_name)
            with open(test_file, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
            return blob_name

        start_time = time.time()

        # 并行上传
        with concurrent.futures.ThreadPoolExecutor(max_workers=file_count) as executor:
            blob_names = list(executor.map(upload_file, range(file_count)))

        end_time = time.time()

        total_time = end_time - start_time
        throughput_mbps = total_size_mb / total_time

        logger.info(f"✓ 总数据量: {total_size_mb} MB")
        logger.info(f"✓ 总耗时: {total_time:.2f} 秒")
        logger.info(f"✓ 并行吞吐量: {throughput_mbps:.2f} MB/s")

        # 清理
        for blob_name in blob_names:
            blob_client = container_client.get_blob_client(blob_name)
            blob_client.delete_blob()

        os.remove(test_file)

        return {
            "success": True,
            "total_size_mb": total_size_mb,
            "total_time_seconds": total_time,
            "parallel_throughput_mbps": throughput_mbps
        }

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_azure_small_file_download(connection_string: Optional[str] = None, container_name: Optional[str] = None, account_name: Optional[str] = None, iterations: int = 3) -> Dict:
    """
    测试Azure Blob Storage小文件下载速度(1MB)

    Args:
        connection_string: Azure存储账户连接字符串
        container_name: 容器名称
        iterations: 测试次数

    Returns:
        包含下载速度统计的字典
    """
    logger.info(f"开始测试Azure Blob Storage小文件下载速度(1MB, {iterations}次)...")

    # 创建并上传1MB测试文件
    test_file = create_test_file(1)
    file_size_mb = 1
    blob_name = "test_download_small.bin"

    speeds = []

    try:
        blob_service_client = get_azure_blob_service_client(account_name=account_name, connection_string=connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)

        # 上传文件
        with open(test_file, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")

            download_path = f"/tmp/download_{i}.bin"

            start_time = time.time()
            with open(download_path, "wb") as download_file:
                download_file.write(blob_client.download_blob().readall())
            end_time = time.time()

            download_time = end_time - start_time
            download_speed_mbps = file_size_mb / download_time
            speeds.append(download_speed_mbps)

            logger.info(f"{download_speed_mbps:.2f} MB/s")

            # 清理
            os.remove(download_path)

            time.sleep(1)

        avg_speed = sum(speeds) / len(speeds)

        logger.info(f"✓ 平均下载速度: {avg_speed:.2f} MB/s")

        # 清理
        blob_client.delete_blob()
        os.remove(test_file)

        return {
            "success": True,
            "file_size_mb": file_size_mb,
            "speeds_mbps": speeds,
            "average_speed_mbps": avg_speed
        }

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_azure_large_file_download(connection_string: Optional[str] = None, container_name: Optional[str] = None, account_name: Optional[str] = None, iterations: int = 3) -> Dict:
    """
    测试Azure Blob Storage大文件下载速度(1GB)

    Args:
        connection_string: Azure存储账户连接字符串
        container_name: 容器名称
        iterations: 测试次数

    Returns:
        包含下载速度统计的字典
    """
    logger.info(f"开始测试Azure Blob Storage大文件下载速度(1GB, {iterations}次)...")

    # 创建并上传1GB测试文件
    test_file = create_test_file(1024)
    file_size_mb = 1024
    blob_name = "test_download_large.bin"

    speeds = []

    try:
        blob_service_client = get_azure_blob_service_client(account_name=account_name, connection_string=connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)

        # 上传文件
        logger.info("  上传测试文件...")
        with open(test_file, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")

            download_path = f"/tmp/download_large_{i}.bin"

            start_time = time.time()
            with open(download_path, "wb") as download_file:
                download_file.write(blob_client.download_blob().readall())
            end_time = time.time()

            download_time = end_time - start_time
            download_speed_mbps = file_size_mb / download_time
            speeds.append(download_speed_mbps)

            logger.info(f"{download_speed_mbps:.2f} MB/s")

            # 清理
            os.remove(download_path)

            time.sleep(1)

        avg_speed = sum(speeds) / len(speeds)

        logger.info(f"✓ 平均下载速度: {avg_speed:.2f} MB/s")

        # 清理
        blob_client.delete_blob()
        os.remove(test_file)

        return {
            "success": True,
            "file_size_mb": file_size_mb,
            "speeds_mbps": speeds,
            "average_speed_mbps": avg_speed
        }

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_azure_blob_list_latency(connection_string: Optional[str] = None, container_name: Optional[str] = None, account_name: Optional[str] = None, iterations: int = 3) -> Dict:
    """
    测试Azure Blob Storage对象列举延迟

    Args:
        connection_string: Azure存储账户连接字符串
        container_name: 容器名称
        iterations: 测试次数

    Returns:
        包含列举延迟统计的字典
    """
    logger.info(f"开始测试Azure Blob Storage对象列举延迟({iterations}次)...")

    latencies = []

    try:
        blob_service_client = get_azure_blob_service_client(account_name=account_name, connection_string=connection_string)
        container_client = blob_service_client.get_container_client(container_name)

        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")

            start_time = time.time()
            blob_list = list(container_client.list_blobs(results_per_page=100))
            end_time = time.time()

            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

            blob_count = len(blob_list)

            logger.info(f"{latency_ms:.2f} ms (对象数: {blob_count})")

            time.sleep(1)

        avg_latency = sum(latencies) / len(latencies)

        logger.info(f"✓ 平均列举延迟: {avg_latency:.2f} ms")

        return {
            "success": True,
            "latencies_ms": latencies,
            "average_latency_ms": avg_latency
        }

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_azure_metadata_read_latency(connection_string: Optional[str] = None, container_name: Optional[str] = None, account_name: Optional[str] = None, blob_name: Optional[str] = None, iterations: int = 3) -> Dict:
    """
    测试Azure Blob Storage对象元数据读取延迟

    Args:
        connection_string: Azure存储账户连接字符串
        container_name: 容器名称
        blob_name: Blob名称
        iterations: 测试次数

    Returns:
        包含元数据读取延迟统计的字典
    """
    logger.info(f"开始测试Azure Blob Storage对象元数据读取延迟({iterations}次)...")

    latencies = []

    try:
        blob_service_client = get_azure_blob_service_client(account_name=account_name, connection_string=connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)

        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")

            start_time = time.time()
            properties = blob_client.get_blob_properties()
            end_time = time.time()

            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)

            logger.info(f"{latency_ms:.2f} ms")

            time.sleep(1)

        avg_latency = sum(latencies) / len(latencies)

        logger.info(f"✓ 平均元数据读取延迟: {avg_latency:.2f} ms")

        return {
            "success": True,
            "latencies_ms": latencies,
            "average_latency_ms": avg_latency
        }

    except Exception as e:
        logger.error(f"✗ 测试失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="E2B云存储集成性能测试")
    parser.add_argument("--test", choices=["upload-small", "upload-large", "upload-parallel",
                                          "download-small", "download-large", "list", "metadata", "all"],
                       default="all", help="测试类型")
    parser.add_argument("--cloud", choices=["s3", "gcs", "azure"], default="s3", help="云存储类型")
    parser.add_argument("--bucket", type=str, help="存储桶名称(S3/GCS)")
    parser.add_argument("--container", type=str, help="容器名称(Azure)")
    parser.add_argument("--region", type=str, default="us-east-1", help="AWS区域")
    parser.add_argument("--connection-string", type=str, help="Azure存储账户连接字符串（可选，与--account-name二选一）")
    parser.add_argument("--account-name", type=str, help="Azure存储账户名称（使用CLI认证，与--connection-string二选一）")
    parser.add_argument("--iterations", type=int, default=3, help="测试迭代次数")
    parser.add_argument("--object-key", type=str, help="对象键(用于元数据测试,S3)")
    parser.add_argument("--blob-name", type=str, help="Blob名称(用于元数据测试,Azure)")
    parser.add_argument("--output", type=str, help="输出JSON文件路径")

    args = parser.parse_args()

    # 从环境变量获取默认值（如果命令行未提供）
    if args.cloud == "azure":
        if not args.account_name and not args.connection_string:
            args.account_name = os.getenv('AZURE_STORAGE_ACCOUNT_NAME')
        if not args.container:
            args.container = os.getenv('TEMPLATE_BUCKET_NAME') or os.getenv('BUILD_CACHE_BUCKET_NAME')

    results = {}

    if args.cloud == "s3":
        if not args.bucket:
            logger.error("错误: S3测试需要提供 --bucket 参数")
            return

        if args.test in ["upload-small", "all"]:
            results["upload_small"] = test_s3_small_file_upload(args.bucket, args.region, args.iterations)
            logger.info("\n" + "="*60 + "\n")

        if args.test in ["upload-large", "all"]:
            results["upload_large"] = test_s3_large_file_upload(args.bucket, args.region, args.iterations)
            logger.info("\n" + "="*60 + "\n")

        if args.test in ["upload-parallel", "all"]:
            results["upload_parallel"] = test_s3_parallel_upload(args.bucket, args.region)
            logger.info("\n" + "="*60 + "\n")

        if args.test in ["download-small", "all"]:
            results["download_small"] = test_s3_small_file_download(args.bucket, args.region, args.iterations)
            logger.info("\n" + "="*60 + "\n")

        if args.test in ["download-large", "all"]:
            results["download_large"] = test_s3_large_file_download(args.bucket, args.region, args.iterations)
            logger.info("\n" + "="*60 + "\n")

        if args.test in ["list", "all"]:
            results["list_latency"] = test_s3_object_list_latency(args.bucket, args.region, args.iterations)
            logger.info("\n" + "="*60 + "\n")

        if args.test in ["metadata"] and args.object_key:
            results["metadata_latency"] = test_s3_metadata_read_latency(args.bucket, args.object_key, args.region, args.iterations)
            logger.info("\n" + "="*60 + "\n")

    elif args.cloud == "azure":
        # 验证必需参数
        if not args.container:
            logger.error("错误: Azure测试需要提供 --container 参数")
            return
        if not args.connection_string and not args.account_name:
            logger.error("错误: Azure测试需要提供 --connection-string 或 --account-name 参数")
            return

        # 显示认证信息
        if args.connection_string:
            logger.info(f"认证方式: Connection String")
        else:
            logger.info(f"认证方式: Azure CLI / Managed Identity (账户: {args.account_name})")
        logger.info(f"容器: {args.container}\n")

        if args.test in ["upload-small", "all"]:
            results["upload_small"] = test_azure_small_file_upload(
                connection_string=args.connection_string,
                container_name=args.container,
                account_name=args.account_name,
                iterations=args.iterations
            )
            logger.info("\n" + "="*60 + "\n")

        if args.test in ["upload-large", "all"]:
            results["upload_large"] = test_azure_large_file_upload(
                connection_string=args.connection_string,
                container_name=args.container,
                account_name=args.account_name,
                iterations=args.iterations
            )
            logger.info("\n" + "="*60 + "\n")

        if args.test in ["upload-parallel", "all"]:
            results["upload_parallel"] = test_azure_parallel_upload(
                connection_string=args.connection_string,
                container_name=args.container,
                account_name=args.account_name
            )
            logger.info("\n" + "="*60 + "\n")

        if args.test in ["download-small", "all"]:
            results["download_small"] = test_azure_small_file_download(
                connection_string=args.connection_string,
                container_name=args.container,
                account_name=args.account_name,
                iterations=args.iterations
            )
            logger.info("\n" + "="*60 + "\n")

        if args.test in ["download-large", "all"]:
            results["download_large"] = test_azure_large_file_download(
                connection_string=args.connection_string,
                container_name=args.container,
                account_name=args.account_name,
                iterations=args.iterations
            )
            logger.info("\n" + "="*60 + "\n")

        if args.test in ["list", "all"]:
            results["list_latency"] = test_azure_blob_list_latency(
                connection_string=args.connection_string,
                container_name=args.container,
                account_name=args.account_name,
                iterations=args.iterations
            )
            logger.info("\n" + "="*60 + "\n")

        if args.test in ["metadata"] and args.blob_name:
            results["metadata_latency"] = test_azure_metadata_read_latency(
                connection_string=args.connection_string,
                container_name=args.container,
                account_name=args.account_name,
                blob_name=args.blob_name,
                iterations=args.iterations
            )
            logger.info("\n" + "="*60 + "\n")

    # 保存结果
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"结果已保存到: {args.output}")

    return results


if __name__ == "__main__":
    main()
