# E2B 云存储性能测试脚本使用示例

## 概述

`05_cloud_storage.py` 支持测试三种云存储平台的性能：
- AWS S3
- Google Cloud Storage (GCS)
- Azure Blob Storage

## 测试类型

- `upload-small`: 小文件上传 (1MB × 3次)
- `upload-large`: 大文件上传 (1GB × 3次)
- `upload-parallel`: 并行上传 (10个100MB文件)
- `download-small`: 小文件下载 (1MB × 3次)
- `download-large`: 大文件下载 (1GB × 3次)
- `list`: 对象列举延迟测试
- `metadata`: 元数据读取延迟测试
- `all`: 运行所有测试（除了 metadata）

---

## Azure Blob Storage 测试示例

### 场景1：使用 Azure CLI 认证（推荐用于开发环境）

```bash
# 前置条件：需要先登录 Azure CLI
az login

# 完整测试
python 05_cloud_storage.py \
  --cloud azure \
  --account-name xxxxxxstorage \
  --container template \
  --test all \
  --iterations 3 \
  --output ../../outputs/05_azure_storage_performance.json

```

### 场景2：使用 Managed Identity 认证（推荐用于生产环境）

```bash
# 系统分配的托管标识
python 05_cloud_storage.py \
  --cloud azure \
  --account-name xxxxxxstorage \
  --container template \
  --test all \
  --output ../../outputs/05_azure_storage_performance.json

# 用户分配的托管标识（需要指定 Client ID）
AZURE_CLIENT_ID="<your-managed-identity-client-id>" \
python 05_cloud_storage.py \
  --cloud azure \
  --account-name xxxxxxstorage \
  --container template \
  --test all \
  --output ../../outputs/05_azure_storage_performance.json
```

### 场景3：使用环境变量简化命令

```bash
# 设置环境变量
export AZURE_STORAGE_ACCOUNT_NAME="xxxxxxstorage"
export TEMPLATE_BUCKET_NAME="template"

# 运行测试（脚本会自动读取环境变量）
python 05_cloud_storage.py \
  --cloud azure \
  --test all \
  --iterations 3 \
  --output ../../outputs/05_azure_storage_performance.json
```

### 场景4：使用 Connection String 认证（传统方式）

```bash
# 获取 Connection String
CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=xxxxxxstorage;AccountKey=<your-key>;EndpointSuffix=core.windows.net"

# 运行测试
python 05_cloud_storage.py \
  --cloud azure \
  --connection-string "$CONNECTION_STRING" \
  --container template \
  --test all \
  --output ../../outputs/05_azure_storage_performance.json
```

## AWS S3 测试示例

### 场景1：标准 S3 测试

```bash
# 前置条件：配置 AWS 凭证
aws configure

# 完整测试
python 05_cloud_storage.py \
  --cloud s3 \
  --bucket my-e2b-test-bucket \
  --region us-east-1 \
  --test all \
  --iterations 3 \
  --output ../../outputs/05_s3_performance.json
```

### 场景2：使用环境变量

```bash
# 设置 AWS 凭证
export AWS_ACCESS_KEY_ID="<your-key-id>"
export AWS_SECRET_ACCESS_KEY="<your-secret-key>"
export AWS_DEFAULT_REGION="us-east-1"

# 运行测试
python 05_cloud_storage.py \
  --cloud s3 \
  --bucket my-e2b-test-bucket \
  --test all \
  --output ../../outputs/05_s3_performance.json
```

### 场景3：测试不同区域性能

```bash
# 测试 us-east-1
python 05_cloud_storage.py \
  --cloud s3 \
  --bucket my-bucket-us-east-1 \
  --region us-east-1 \
  --test all \
  --output ../../outputs/05_s3_us_east_1.json

# 测试 us-west-2
python 05_cloud_storage.py \
  --cloud s3 \
  --bucket my-bucket-us-west-2 \
  --region us-west-2 \
  --test all \
  --output ../../outputs/05_s3_us_west_2.json

# 测试 ap-northeast-1
python 05_cloud_storage.py \
  --cloud s3 \
  --bucket my-bucket-ap-northeast-1 \
  --region ap-northeast-1 \
  --test all \
  --output ../../outputs/05_s3_ap_northeast_1.json
```

## Google Cloud Storage (GCS) 测试示例

### 场景1：使用服务账号认证

```bash
# 前置条件：设置 GCP 凭证
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# 完整测试
python 05_cloud_storage.py \
  --cloud gcs \
  --bucket my-gcs-e2b-bucket \
  --test all \
  --iterations 3 \
  --output ../../outputs/05_gcs_performance.json
```

### 场景2：使用 gcloud CLI 认证

```bash
# 登录 gcloud
gcloud auth application-default login

# 运行测试
python 05_cloud_storage.py \
  --cloud gcs \
  --bucket my-gcs-e2b-bucket \
  --test all \
  --output ../../outputs/05_gcs_performance.json
```

---

## 实际使用场景示例

### E2B Orchestrator 宿主机测试（Azure）

```bash
# 在 E2B orchestrator 宿主机上运行
cd /home/ubuntu/e2b-testing-scripts

# 使用已配置的环境变量
export AZURE_STORAGE_ACCOUNT_NAME="xxxxxxstorage"
export TEMPLATE_BUCKET_NAME="template"

# 完整性能测试（输出到 outputs 目录）
python tests/host/05_cloud_storage.py \
  --cloud azure \
  --test all \
  --iterations 3 \
  --output ../outputs/05_azure_storage_performance.json

# 查看结果
cat ../outputs/05_azure_storage_performance.json | jq '.'
```

### 快速验证连接测试

```bash
# 快速验证 Azure Storage 连接是否正常
python 05_cloud_storage.py \
  --cloud azure \
  --account-name xxxxxxstorage \
  --container template \
  --test upload-small \
  --iterations 1

# 快速验证 S3 连接
python 05_cloud_storage.py \
  --cloud s3 \
  --bucket my-bucket \
  --region us-east-1 \
  --test upload-small \
  --iterations 1
```

### 并行性能压测

```bash
# 测试高并发上传性能（10个100MB文件并行）
python 05_cloud_storage.py \
  --cloud azure \
  --account-name xxxxxxstorage \
  --container template \
  --test upload-parallel

# 自定义并发数（需要修改脚本的 file_count 参数）
```

### 生产环境测试（最小化输出）

```bash
# 使用 Managed Identity + 仅保存结果
python 05_cloud_storage.py \
  --cloud azure \
  --account-name xxxxxxstorage \
  --container template \
  --test all \
  --iterations 3 \
  --output ../../outputs/05_azure_storage_$(date +%Y%m%d_%H%M%S).json \
  2>&1 | tee ../../logs/azure_storage_test.log
```

---

## 常见问题排查

### Azure 认证失败

```bash
# 检查 Azure CLI 登录状态
az account show

# 重新登录
az login

# 测试存储账户访问权限
az storage container list \
  --account-name xxxxxxstorage \
  --auth-mode login
```

### AWS 认证失败

```bash
# 检查 AWS 配置
aws sts get-caller-identity

# 检查 S3 桶访问权限
aws s3 ls s3://my-bucket/
```

### Python 依赖安装

```bash
# 安装所需的 Python 包
pip install boto3 google-cloud-storage azure-storage-blob azure-identity
```

---

## 性能测试最佳实践

### 1. 测试前准备

```bash
# 确保有足够磁盘空间（至少 3GB）
df -h /tmp

# 检查网络连接
ping -c 5 xxxxxxstorage.blob.core.windows.net

# 清理旧的测试文件
rm -f /tmp/test_*.bin /tmp/download*.bin
```

### 2. 多次测试取平均值

```bash
# 运行 3 次完整测试
for i in 1 2 3; do
  echo "=== 测试轮次 $i ==="
  python 05_cloud_storage.py \
    --cloud azure \
    --account-name xxxxxxstorage \
    --container template \
    --test all \
    --iterations 3 \
    --output ../../outputs/05_azure_storage_run${i}.json
  sleep 10
done
```

### 3. 对比不同容器性能

```bash
# 测试 template 容器
python 05_cloud_storage.py \
  --cloud azure \
  --account-name xxxxxxstorage \
  --container template \
  --test all \
  --output ../../outputs/05_azure_template_performance.json

# 测试 build-cache 容器
python 05_cloud_storage.py \
  --cloud azure \
  --account-name xxxxxxstorage \
  --container build-cache \
  --test all \
  --output ../../outputs/05_azure_buildcache_performance.json
```

---

## 完整的 E2B 环境测试工作流

### 在 Orchestrator 宿主机上

```bash
#!/bin/bash
# E2B Azure Storage 性能测试脚本

# 1. 设置环境变量
export AZURE_STORAGE_ACCOUNT_NAME="xxxxxxstorage"
export TEMPLATE_BUCKET_NAME="template"
export BUILD_CACHE_BUCKET_NAME="build-cache"

# 2. 切换到测试目录
cd /home/ubuntu/e2b-testing-scripts/tests/host

# 3. 测试 template 容器性能
echo "=== 测试 Template 容器性能 ==="
python 05_cloud_storage.py \
  --cloud azure \
  --account-name xxxxxxstorage \
  --container template \
  --test all \
  --iterations 3 \
  --output ../../outputs/05_azure_template_performance.json

# 4. 测试 build-cache 容器性能
echo ""
echo "=== 测试 Build Cache 容器性能 ==="
python 05_cloud_storage.py \
  --cloud azure \
  --account-name xxxxxxstorage \
  --container build-cache \
  --test all \
  --iterations 3 \
  --output ../../outputs/05_azure_buildcache_performance.json

# 5. 显示结果摘要
echo ""
echo "=== 测试完成 ==="
echo "Template 容器结果:"
cat ../../outputs/05_azure_template_performance.json | jq '.upload_small.average_speed_mbps, .download_small.average_speed_mbps'

echo ""
echo "Build Cache 容器结果:"
cat ../../outputs/05_azure_buildcache_performance.json | jq '.upload_small.average_speed_mbps, .download_small.average_speed_mbps'
```

### 在 E2B 沙箱内测试

```bash
# 在沙箱中运行相同的测试
# 注意：需要确保沙箱有 Azure 认证配置

cd /home/user/e2b-testing-scripts

python 05_cloud_storage.py \
  --cloud azure \
  --account-name xxxxxxstorage \
  --container template \
  --test all \
  --iterations 3 \
  --output /root/sandbox_storage_performance.json
```

---

## 针对不同云平台的环境变量配置

### Azure

```bash
# 方式1：使用账户名 + Managed Identity / Azure CLI
export AZURE_STORAGE_ACCOUNT_NAME="xxxxxxstorage"
export TEMPLATE_BUCKET_NAME="template"

# 方式2：使用 Connection String
export AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=xxxxxxstorage;AccountKey=<key>;EndpointSuffix=core.windows.net"

# 方式3：使用用户分配的托管标识
export AZURE_CLIENT_ID="<managed-identity-client-id>"
export AZURE_STORAGE_ACCOUNT_NAME="xxxxxxstorage"
```

### AWS S3

```bash
# AWS 凭证
export AWS_ACCESS_KEY_ID="<your-access-key>"
export AWS_SECRET_ACCESS_KEY="<your-secret-key>"
export AWS_DEFAULT_REGION="us-east-1"

# 或使用 IAM Role（在 EC2 上）
# 无需额外配置，自动使用实例的 IAM Role
```

### Google Cloud Storage

```bash
# 使用服务账号密钥
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"

# 或使用 gcloud CLI
# gcloud auth application-default login
```

---

## 输出结果示例

测试完成后，JSON 输出格式如下：

```json
{
  "upload_small": {
    "success": true,
    "file_size_mb": 1,
    "speeds_mbps": [12.5, 13.2, 12.8],
    "average_speed_mbps": 12.83
  },
  "upload_large": {
    "success": true,
    "file_size_mb": 1024,
    "speeds_mbps": [85.3, 87.1, 86.5],
    "average_speed_mbps": 86.30
  },
  "upload_parallel": {
    "success": true,
    "total_size_mb": 1000,
    "total_time_seconds": 8.52,
    "parallel_throughput_mbps": 117.37
  },
  "download_small": {
    "success": true,
    "file_size_mb": 1,
    "speeds_mbps": [45.2, 46.8, 45.5],
    "average_speed_mbps": 45.83
  },
  "download_large": {
    "success": true,
    "file_size_mb": 1024,
    "speeds_mbps": [120.5, 118.3, 119.7],
    "average_speed_mbps": 119.50
  },
  "list_latency": {
    "success": true,
    "latencies_ms": [125.3, 132.1, 128.7],
    "average_latency_ms": 128.70
  }
}
```

---

## 当前 E2B 环境配置（Azure）

根据你的环境配置：

```bash
# 推荐的测试命令
cd /home/jie/e2btests/tests/host

python 05_cloud_storage.py \
  --cloud azure \
  --account-name xxxxxxstorage \
  --container template \
  --test all \
  --iterations 3 \
  --output ../../outputs/05_azure_storage_performance.json
```

或使用环境变量：

```bash
export AZURE_STORAGE_ACCOUNT_NAME="xxxxxxstorage"
export TEMPLATE_BUCKET_NAME="template"

python 05_cloud_storage.py \
  --cloud azure \
  --test all \
  --iterations 3 \
  --output ../../outputs/05_azure_storage_performance.json
```

---

## 故障排除

### 错误：认证失败

```bash
# Azure: 检查认证
az account show
az storage container list --account-name xxxxxxstorage --auth-mode login

# AWS: 检查认证
aws sts get-caller-identity

# GCP: 检查认证
gcloud auth list
```

### 错误：容器不存在

```bash
# Azure: 列出现有容器
az storage container list \
  --account-name xxxxxxstorage \
  --auth-mode login \
  --output table

# 创建测试容器
az storage container create \
  --account-name xxxxxxstorage \
  --name e2b-perf-test \
  --auth-mode login
```

### 错误：磁盘空间不足

```bash
# 检查磁盘空间
df -h /tmp

# 清理旧测试文件
rm -f /tmp/test_*.bin /tmp/download*.bin
```

### 错误：Python 依赖缺失

```bash
# 安装所有依赖
pip install boto3 google-cloud-storage azure-storage-blob azure-identity

# 或使用 requirements.txt（如果有）
pip install -r requirements.txt
```
