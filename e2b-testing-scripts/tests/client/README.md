# 客户端测试

E2B 客户端性能测试套件，用于评估沙箱生命周期、容量和模板构建性能。

## 目录结构

```
tests/client/
├── run_all_tests.py             # 统一测试入口（Python）
├── 01_sandbox_lifecycle.py      # 沙箱生命周期测试
├── 02_template_snapshot.py      # 模板快照测试
├── 06_sandbox_capacity.py       # 沙箱容量测试
├── test_template_build.py       # 模板构建测试
├── cleanup_sandboxes.py         # 清理工具
└── README.md                    # 本文档
```

## 环境配置

测试需要配置环境变量，请先创建并配置 `.e2b_env` 文件：

```bash
# .e2b_env 示例
export E2B_DOMAIN="your-domain.com"
export E2B_API_KEY="your-api-key"
export E2B_TEMPLATE_NAME="agent_test"
export NOMAD_ADDR="http://localhost:4646"
export NOMAD_TOKEN="your-nomad-token"
export E2B_ORCHESTRATOR_JOB="orchestrator"
export E2B_DEFAULT_ITERATIONS="3"
export CLOUD_PROVIDER="aws"
```

加载环境变量：
```bash
source .e2b_env
```

## 快速开始

### 运行所有测试

```bash
cd tests/client
python3 run_all_tests.py --all
```

### 运行指定测试

```bash
# 生命周期测试
python3 run_all_tests.py --lifecycle

# 容量测试
python3 run_all_tests.py --capacity

# 模板快照测试
python3 run_all_tests.py --snapshot

# 模板构建测试
python3 run_all_tests.py --template-build

# 组合测试
python3 run_all_tests.py --lifecycle --capacity
```

## 测试说明

### 1. 沙箱生命周期测试 (`--lifecycle`)

**测试文件**: [01_sandbox_lifecycle.py](01_sandbox_lifecycle.py)

**测试指标**：
- 冷启动延迟（从无到创建沙箱的时间）
- 热启动延迟（复用已有资源创建沙箱的时间）
- 启动成功率
- 延迟分布（P50/P95/P99）

**命令行选项**：
```bash
# 使用统一入口
python3 run_all_tests.py --lifecycle --cold-iterations 5 --warm-iterations 20

# 直接运行
python3 01_sandbox_lifecycle.py --test cold --iterations 5 --template agent_test
python3 01_sandbox_lifecycle.py --test warm --iterations 20 --template agent_test
```

**输出文件**：
- `outputs/01_cold_start.json` - 冷启动结果
- `outputs/01_warm_start.json` - 热启动结果

### 2. 模板快照测试 (`--snapshot`)

**测试文件**: [02_template_snapshot.py](02_template_snapshot.py)

**测试指标**：
- 模板构建时间
- 模板上传/下载速度
- 快照创建时间
- 快照下载速度
- 存储成本估算

**命令行选项**：
```bash
# 使用统一入口
python3 run_all_tests.py --snapshot

# 直接运行
python3 02_template_snapshot.py --output outputs/02_template_snapshot.json
```

**输出文件**：
- `outputs/02_template_snapshot.json`

### 3. 沙箱容量测试 (`--capacity`)

**测试文件**: [06_sandbox_capacity.py](06_sandbox_capacity.py)

**测试指标**：
- 集群总容量（最大并发沙箱数）
- 单机最大沙箱密度
- 沙箱调度负载均衡性
- 节点间分布均匀度

**命令行选项**：
```bash
# 使用统一入口
python3 run_all_tests.py --capacity --batch-size 20 --max-sandboxes 200

# 直接运行
python3 06_sandbox_capacity.py --batch-size 20 --max-sandboxes 200 --output outputs/06_capacity.json
```

**输出文件**：
- `outputs/06_sandbox_capacity.json`

**注意**：
- 容量测试会创建大量沙箱，请谨慎设置 `--max-sandboxes`
- 建议在测试环境中运行

### 4. 模板构建测试 (`--template-build`)

**测试文件**: [test_template_build.py](test_template_build.py)

**测试指标**：
- 模板构建时间
- 沙箱创建时间
- 基本功能验证

**命令行选项**：
```bash
# 使用统一入口
python3 run_all_tests.py --template-build

# 直接运行
python3 test_template_build.py --name agent_test --memory 4096 --cpu 6
```

**输出文件**：
- `outputs/template_build.json`

## 命令行参数

### 测试选择

| 参数 | 说明 |
|:---|:---|
| `--all` | 运行所有测试 |
| `--lifecycle` | 运行沙箱生命周期测试 |
| `--snapshot` | 运行模板快照测试 |
| `--capacity` | 运行沙箱容量测试 |
| `--template-build` | 运行模板构建测试 |

### 参数配置

| 参数 | 默认值 | 说明 |
|:---|:---|:---|
| `--iterations` | 3 | 测试迭代次数 |
| `--cold-iterations` | 3 | 冷启动测试次数 |
| `--warm-iterations` | 10 | 热启动测试次数 |
| `--batch-size` | 10 | 容量测试批次大小 |
| `--max-sandboxes` | 100 | 容量测试最大沙箱数 |
| `--output-dir` | outputs/ | 输出目录 |

## 使用示例

### 示例 1: 完整测试

```bash
# 运行所有测试（默认参数）
python3 run_all_tests.py --all

# 运行所有测试（自定义参数）
python3 run_all_tests.py --all \
  --cold-iterations 5 \
  --warm-iterations 20 \
  --max-sandboxes 200 \
  --output-dir /tmp/e2b_test_results
```

### 示例 2: 快速性能测试

```bash
# 只测试启动性能
python3 run_all_tests.py --lifecycle --cold-iterations 3 --warm-iterations 10
```

### 示例 3: 容量压力测试

```bash
# 测试最大容量
python3 run_all_tests.py --capacity --batch-size 20 --max-sandboxes 500
```

### 示例 4: 组合测试

```bash
# 生命周期 + 容量测试
python3 run_all_tests.py --lifecycle --capacity
```

## 输出文件

测试完成后，结果保存在输出目录中：

```
outputs/
├── summary_report.json          # 综合测试报告
├── 01_cold_start.json           # 冷启动测试结果
├── 01_warm_start.json           # 热启动测试结果
├── 02_template_snapshot.json    # 模板快照测试结果
├── 06_sandbox_capacity.json     # 容量测试结果
└── template_build.json          # 模板构建测试结果
```

### 综合报告格式

```json
{
  "metadata": {
    "cloud_provider": "aws",
    "template": "agent_test",
    "test_date": "2025-12-19T15:00:00",
    "total_elapsed_time": 456.78,
    "iterations": {
      "default": 3,
      "cold_start": 3,
      "warm_start": 10
    }
  },
  "results": {
    "lifecycle_cold": {"success": true, "elapsed_time": 123.45},
    "lifecycle_warm": {"success": true, "elapsed_time": 89.12},
    "sandbox_capacity": {"success": true, "elapsed_time": 234.56},
    ...
  }
}
```

## 依赖工具

### Python 依赖

```bash
pip3 install -r requirements.txt
```

主要依赖：
- `e2b` - E2B Python SDK
- `pyyaml` - YAML 配置解析
- `boto3` - AWS SDK（模板快照测试需要）
- `google-cloud-storage` - GCS SDK（模板快照测试需要）

### 系统工具

- `e2b` CLI - 模板构建需要
  ```bash
  npm install -g @e2b/cli
  ```

## 工具脚本

### cleanup_sandboxes.py

清理残留的沙箱资源。

```bash
python3 cleanup_sandboxes.py
```

## SSL 证书问题解决方案

如果遇到 SSL 证书验证问题，在测试脚本开头添加：

```python
import ssl
ssl._create_default_https_context = ssl._create_unverified_context
```

参考示例：[tests/sandbox/example_command_simple.py](../sandbox/example_command_simple.py)

## 性能基准

### 冷启动延迟

| 环境 | P50 | P95 | P99 |
|:---|:---|:---|:---|
| 本地开发 | ~500ms | ~800ms | ~1000ms |
| AWS (us-east-1) | ~300ms | ~500ms | ~700ms |
| GCP (us-central1) | ~350ms | ~550ms | ~750ms |

### 热启动延迟

| 环境 | P50 | P95 | P99 |
|:---|:---|:---|:---|
| 本地开发 | ~100ms | ~200ms | ~300ms |
| AWS (us-east-1) | ~50ms | ~100ms | ~150ms |
| GCP (us-central1) | ~60ms | ~120ms | ~180ms |

### 容量基准

| 配置 | 最大并发沙箱数 |
|:---|:---|
| 单机 (16核/64GB) | ~100-150 |
| 小集群 (3节点) | ~300-500 |
| 中集群 (10节点) | ~1000-1500 |

## 故障诊断

### 问题 1: 环境变量未配置

**症状**：
```
错误: 缺少必需的环境变量
缺少的变量: E2B_DOMAIN, E2B_API_KEY
```

**解决**：
```bash
# 1. 创建 .e2b_env 文件
# 2. 配置所需变量
# 3. 加载环境
source .e2b_env
```

### 问题 2: Python 依赖缺失

**症状**：
```
错误: 缺少必需的 Python 依赖
缺少的依赖: e2b, pyyaml
```

**解决**：
```bash
pip3 install -r requirements.txt
```

### 问题 3: 容量测试超时

**症状**：
- 容量测试运行时间过长
- 部分沙箱创建失败

**解决**：
```bash
# 降低批次大小和最大沙箱数
python3 run_all_tests.py --capacity --batch-size 5 --max-sandboxes 50
```

## 最佳实践

### 1. 测试前准备

```bash
# 1. 检查环境配置
cat .e2b_env

# 2. 加载环境变量
source .e2b_env

# 3. 验证连接
python3 -c "from e2b import Sandbox; s = Sandbox(); print(f'✓ 连接成功: {s.sandbox_id}'); s.kill()"
```

### 2. 测试策略

**开发环境**：
```bash
# 快速验证
python3 run_all_tests.py --lifecycle --cold-iterations 2 --warm-iterations 5
```

**生产环境**：
```bash
# 完整测试
python3 run_all_tests.py --all --cold-iterations 5 --warm-iterations 20 --max-sandboxes 200
```

**压力测试**：
```bash
# 容量极限测试
python3 run_all_tests.py --capacity --batch-size 50 --max-sandboxes 1000
```

### 3. 测试后清理

```bash
# 清理残留沙箱
python3 cleanup_sandboxes.py
```

## 常见问题

### Q: 测试需要多长时间？

A:
- 生命周期测试：3-5 分钟
- 模板快照测试：5-10 分钟
- 容量测试：根据 max-sandboxes 而定（100个约 5-10 分钟）
- 模板构建测试：2-5 分钟
- 完整测试（--all）：15-30 分钟

### Q: 容量测试安全吗？

A: 容量测试会创建大量沙箱，建议：
- 在测试环境中运行
- 先从小批次开始（--max-sandboxes 50）
- 监控资源使用情况

### Q: 如何解读测试结果？

A: 关注以下关键指标：
- 冷启动 P95 < 1000ms
- 热启动 P50 < 100ms
- 容量测试成功率 > 95%
- 负载均衡偏差 < 20%

### Q: 测试失败怎么办？

A: 检查以下内容：
1. 环境变量配置是否正确
2. E2B 服务是否正常运行
3. 网络连接是否正常
4. 查看详细日志输出
5. 检查 `outputs/summary_report.json` 中的错误信息

## 更新日志

### 2025-12-19
- 删除重复的 `test_template_build.sh`
- 扩展 `run_all_tests.py` 支持所有测试类型
- 添加完整的命令行参数支持
- 创建 README 文档

### 2024-12-03
- 初始版本
- 基础生命周期测试

## 贡献

如有问题或建议，请提交 Issue 或 Pull Request。

---

**维护者**: E2B Team
**最后更新**: 2025-12-19
