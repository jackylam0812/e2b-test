#!/usr/bin/env python3
"""
E2B模板和快照测试脚本
测试指标:
- 模板构建时间
- 模板上传/下载速度
- 模板存储成本
- 快照创建时间
- 快照下载速度
- 快照存储成本
"""

import time
import json
import os
import sys
import boto3
from google.cloud import storage
from typing import Dict

# 导入彩色日志
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.logger import get_logger

logger = get_logger(__name__)

def test_template_build_time(dockerfile_path: str, template_name: str) -> Dict:
    """
    测试模板构建时间
    
    Args:
        dockerfile_path: Dockerfile路径
        template_name: 模板名称
    
    Returns:
        包含构建时间的字典
    """
    logger.info(f"开始测试模板构建时间...")
    logger.info(f"  Dockerfile: {dockerfile_path}")
    logger.info(f"  模板名称: {template_name}")
    
    start_time = time.time()
    
    try:
        # 使用E2B CLI构建模板
        # 注意: 需要先安装E2B CLI: npm install -g @e2b/cli
        import subprocess
        
        result = subprocess.run(
            ["e2b", "template", "build", "-f", dockerfile_path, "-n", template_name],
            capture_output=True,
            text=True,
            timeout=600  # 10分钟超时
        )
        
        end_time = time.time()
        build_time = end_time - start_time
        
        if result.returncode == 0:
            logger.info(f"\n✓ 模板构建成功")
            logger.info(f"  构建时间: {build_time:.2f} 秒")
            
            return {
                "success": True,
                "build_time_seconds": build_time,
                "template_name": template_name,
                "output": result.stdout
            }
        else:
            logger.error(f"\n✗ 模板构建失败")
            logger.error(f"  错误信息: {result.stderr}")
            return {
                "success": False,
                "error": result.stderr
            }
    
    except Exception as e:
        logger.error(f"\n✗ 模板构建异常: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_template_upload_speed_s3(
    file_path: str,
    bucket_name: str,
    object_key: str,
    region: str = "us-east-1"
) -> Dict:
    """
    测试模板上传速度(AWS S3)
    
    Args:
        file_path: 本地文件路径
        bucket_name: S3桶名称
        object_key: 对象键
        region: AWS区域
    
    Returns:
        包含上传速度的字典
    """
    logger.info(f"开始测试模板上传速度(S3)...")
    
    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / (1024 * 1024)
    
    logger.info(f"  文件大小: {file_size_mb:.2f} MB")
    
    try:
        s3_client = boto3.client('s3', region_name=region)
        
        start_time = time.time()
        s3_client.upload_file(file_path, bucket_name, object_key)
        end_time = time.time()
        
        upload_time = end_time - start_time
        upload_speed_mbps = (file_size_mb / upload_time)
        
        logger.info(f"\n✓ 上传成功")
        logger.info(f"  上传时间: {upload_time:.2f} 秒")
        logger.info(f"  上传速度: {upload_speed_mbps:.2f} MB/s ⭐")
        
        return {
            "success": True,
            "file_size_mb": file_size_mb,
            "upload_time_seconds": upload_time,
            "upload_speed_mbps": upload_speed_mbps
        }
    
    except Exception as e:
        logger.error(f"\n✗ 上传失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_template_download_speed_s3(
    bucket_name: str,
    object_key: str,
    download_path: str,
    region: str = "us-east-1",
    iterations: int = 5
) -> Dict:
    """
    测试模板下载速度(AWS S3)
    
    Args:
        bucket_name: S3桶名称
        object_key: 对象键
        download_path: 下载路径
        region: AWS区域
        iterations: 测试次数
    
    Returns:
        包含下载速度统计的字典
    """
    logger.info(f"开始测试模板下载速度(S3, {iterations}次)...")
    
    speeds = []
    
    try:
        s3_client = boto3.client('s3', region_name=region)
        
        # 获取文件大小
        response = s3_client.head_object(Bucket=bucket_name, Key=object_key)
        file_size = response['ContentLength']
        file_size_mb = file_size / (1024 * 1024)
        
        logger.info(f"  文件大小: {file_size_mb:.2f} MB")
        
        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")
            
            # 删除本地文件(如果存在)
            if os.path.exists(download_path):
                os.remove(download_path)
            
            start_time = time.time()
            s3_client.download_file(bucket_name, object_key, download_path)
            end_time = time.time()
            
            download_time = end_time - start_time
            download_speed_mbps = file_size_mb / download_time
            speeds.append(download_speed_mbps)
            
            logger.info(f"{download_speed_mbps:.2f} MB/s")
            
            time.sleep(1)
        
        avg_speed = sum(speeds) / len(speeds)
        
        logger.info(f"\n✓ 下载测试完成")
        logger.info(f"  平均下载速度: {avg_speed:.2f} MB/s ⭐")
        
        return {
            "success": True,
            "file_size_mb": file_size_mb,
            "speeds_mbps": speeds,
            "average_speed_mbps": avg_speed
        }
    
    except Exception as e:
        logger.error(f"\n✗ 下载失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_template_upload_speed_gcs(
    file_path: str,
    bucket_name: str,
    object_name: str
) -> Dict:
    """
    测试模板上传速度(GCP GCS)
    
    Args:
        file_path: 本地文件路径
        bucket_name: GCS桶名称
        object_name: 对象名称
    
    Returns:
        包含上传速度的字典
    """
    logger.info(f"开始测试模板上传速度(GCS)...")
    
    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / (1024 * 1024)
    
    logger.info(f"  文件大小: {file_size_mb:.2f} MB")
    
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        
        start_time = time.time()
        blob.upload_from_filename(file_path)
        end_time = time.time()
        
        upload_time = end_time - start_time
        upload_speed_mbps = file_size_mb / upload_time
        
        logger.info(f"\n✓ 上传成功")
        logger.info(f"  上传时间: {upload_time:.2f} 秒")
        logger.info(f"  上传速度: {upload_speed_mbps:.2f} MB/s ⭐")
        
        return {
            "success": True,
            "file_size_mb": file_size_mb,
            "upload_time_seconds": upload_time,
            "upload_speed_mbps": upload_speed_mbps
        }
    
    except Exception as e:
        logger.error(f"\n✗ 上传失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def test_template_download_speed_gcs(
    bucket_name: str,
    object_name: str,
    download_path: str,
    iterations: int = 5
) -> Dict:
    """
    测试模板下载速度(GCP GCS)
    
    Args:
        bucket_name: GCS桶名称
        object_name: 对象名称
        download_path: 下载路径
        iterations: 测试次数
    
    Returns:
        包含下载速度统计的字典
    """
    logger.info(f"开始测试模板下载速度(GCS, {iterations}次)...")
    
    speeds = []
    
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_name)
        
        # 获取文件大小
        blob.reload()
        file_size = blob.size
        file_size_mb = file_size / (1024 * 1024)
        
        logger.info(f"  文件大小: {file_size_mb:.2f} MB")
        
        for i in range(iterations):
            logger.info(f"  测试 {i+1}/{iterations}...")
            
            # 删除本地文件(如果存在)
            if os.path.exists(download_path):
                os.remove(download_path)
            
            start_time = time.time()
            blob.download_to_filename(download_path)
            end_time = time.time()
            
            download_time = end_time - start_time
            download_speed_mbps = file_size_mb / download_time
            speeds.append(download_speed_mbps)
            
            logger.info(f"{download_speed_mbps:.2f} MB/s")
            
            time.sleep(1)
        
        avg_speed = sum(speeds) / len(speeds)
        
        logger.info(f"\n✓ 下载测试完成")
        logger.info(f"  平均下载速度: {avg_speed:.2f} MB/s ⭐")
        
        return {
            "success": True,
            "file_size_mb": file_size_mb,
            "speeds_mbps": speeds,
            "average_speed_mbps": avg_speed
        }
    
    except Exception as e:
        logger.error(f"\n✗ 下载失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def calculate_template_storage_cost(
    template_size_gb: float,
    storage_price_per_gb_month: float,
    template_count: int
) -> float:
    """
    计算模板存储成本
    
    Args:
        template_size_gb: 单个模板大小(GB)
        storage_price_per_gb_month: 存储单价(USD/GB/月)
        template_count: 模板数量
    
    Returns:
        月度存储成本(USD)
    """
    cost = template_size_gb * storage_price_per_gb_month * template_count
    
    logger.info(f"\n模板存储成本计算:")
    logger.info(f"  单个模板大小: {template_size_gb:.2f} GB")
    logger.info(f"  存储单价: ${storage_price_per_gb_month:.4f}/GB/月")
    logger.info(f"  模板数量: {template_count}")
    logger.info(f"  月度存储成本: ${cost:.2f} ⭐")
    
    return cost


def test_snapshot_creation_time(sandbox_id: str) -> Dict:
    """
    测试快照创建时间
    
    Args:
        sandbox_id: 沙箱ID
    
    Returns:
        包含快照创建时间的字典
    """
    logger.info(f"开始测试快照创建时间...")
    logger.info(f"  沙箱ID: {sandbox_id}")
    
    try:
        from e2b_code_interpreter import Sandbox
        
        # 连接到现有沙箱
        sandbox = Sandbox.connect(sandbox_id)
        
        start_time = time.time()
        snapshot = sandbox.create_snapshot()
        end_time = time.time()
        
        creation_time_ms = (end_time - start_time) * 1000
        
        logger.info(f"\n✓ 快照创建成功")
        logger.info(f"  快照ID: {snapshot.id}")
        logger.info(f"  创建时间: {creation_time_ms:.2f} ms")
        
        sandbox.close()
        
        return {
            "success": True,
            "snapshot_id": snapshot.id,
            "creation_time_ms": creation_time_ms
        }
    
    except Exception as e:
        logger.error(f"\n✗ 快照创建失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def calculate_snapshot_storage_cost(
    snapshot_size_gb: float,
    storage_price_per_gb_month: float,
    snapshot_count: int
) -> float:
    """
    计算快照存储成本
    
    Args:
        snapshot_size_gb: 单个快照大小(GB)
        storage_price_per_gb_month: 存储单价(USD/GB/月)
        snapshot_count: 快照数量
    
    Returns:
        月度存储成本(USD)
    """
    cost = snapshot_size_gb * storage_price_per_gb_month * snapshot_count
    
    logger.info(f"\n快照存储成本计算:")
    logger.info(f"  单个快照大小: {snapshot_size_gb:.2f} GB")
    logger.info(f"  存储单价: ${storage_price_per_gb_month:.4f}/GB/月")
    logger.info(f"  快照数量: {snapshot_count}")
    logger.info(f"  月度存储成本: ${cost:.2f}")
    
    return cost


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="E2B模板和快照测试")
    parser.add_argument("--test", choices=["build", "upload", "download", "snapshot", "cost"], 
                       required=True, help="测试类型")
    parser.add_argument("--cloud", choices=["s3", "gcs"], help="云存储类型")
    parser.add_argument("--file", type=str, help="文件路径")
    parser.add_argument("--bucket", type=str, help="存储桶名称")
    parser.add_argument("--object-key", type=str, help="对象键/名称")
    parser.add_argument("--region", type=str, default="us-east-1", help="AWS区域")
    parser.add_argument("--iterations", type=int, default=5, help="测试迭代次数")
    parser.add_argument("--output", type=str, help="输出JSON文件路径")
    
    # 成本计算参数
    parser.add_argument("--size-gb", type=float, help="文件大小(GB)")
    parser.add_argument("--price", type=float, help="存储单价(USD/GB/月)")
    parser.add_argument("--count", type=int, help="文件数量")
    
    args = parser.parse_args()
    
    result = {}
    
    if args.test == "upload":
        if args.cloud == "s3":
            result = test_template_upload_speed_s3(
                args.file, args.bucket, args.object_key, args.region
            )
        elif args.cloud == "gcs":
            result = test_template_upload_speed_gcs(
                args.file, args.bucket, args.object_key
            )
    
    elif args.test == "download":
        if args.cloud == "s3":
            result = test_template_download_speed_s3(
                args.bucket, args.object_key, "/tmp/download_test", 
                args.region, args.iterations
            )
        elif args.cloud == "gcs":
            result = test_template_download_speed_gcs(
                args.bucket, args.object_key, "/tmp/download_test", 
                args.iterations
            )
    
    elif args.test == "cost":
        if args.size_gb and args.price and args.count:
            result = {
                "storage_cost_usd_month": calculate_template_storage_cost(
                    args.size_gb, args.price, args.count
                )
            }
    
    # 保存结果
    if args.output and result:
        with open(args.output, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"\n结果已保存到: {args.output}")
    
    return result


if __name__ == "__main__":
    main()
