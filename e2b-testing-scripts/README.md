# E2B 服务基准测试工具集

E2B (End-to-End Benchmarking) 服务性能测试与对比工具，用于评估和对比不同云厂商上自建 E2B 服务的性能表现。

## 📋 项目概述

本项目提供完整的基准测试工具和指标定义，涵盖：
- 沙箱生命周期性能（冷/热启动、快照恢复）
- 沙箱内部性能（CPU、内存、磁盘、网络）
- 宿主机性能（底层硬件能力）
- 云存储集成性能
- 成本核算与性价比分析

## 🎯 核心测试指标

### 必测指标（🔴 核心）

以下指标对 E2B 服务影响最大，**必须测试**：

| 指标 | 单位 | 说明 | 文档位置 |
|-----|------|------|---------|
| **沙箱冷启动延迟(P95)** | ms | 无缓存情况下的启动性能 | [§1.1.1](docs/E2B服务基准测试指标定义.md#111-冷启动延迟-cold-start-latency) |
| **沙箱热启动延迟(P50)** | ms | 有预热池情况下的启动性能 | [§1.1.2](docs/E2B服务基准测试指标定义.md#112-热启动延迟-warm-start-latency) |
| **快照恢复延迟(P50)** | ms | 从快照恢复的启动性能 | [§1.1.3](docs/E2B服务基准测试指标定义.md#113-从快照恢复延迟-snapshot-restore-latency) |
| **模板下载速度** | MB/s | 影响冷启动的主要因素 | [§2.2.2](docs/E2B服务基准测试指标定义.md#222-模板下载速度-template-download-speed) |
| **沙箱内CPU性能** | events/s | 实际计算能力（含虚拟化开销） | [§4.1.1](docs/E2B服务基准测试指标定义.md#411-沙箱cpu性能) |
| **沙箱内磁盘随机读IOPS** | IOPS | 实际I/O性能 | [§4.3.1](docs/E2B服务基准测试指标定义.md#431-沙箱随机读iops-sandbox-random-read-iops) |
| **Python/Node.js代码执行性能** | score | 业务场景真实性能 | [§4.5](docs/E2B服务基准测试指标定义.md#45-沙箱应用场景性能) |
| **CPU/I/O隔离效果** | % | "吵闹邻居"影响程度 | [§4.6](docs/E2B服务基准测试指标定义.md#46-沙箱资源隔离质量) |
| **宿主机到云存储延迟** | ms | 影响模板/快照访问 | [§5.4.3](docs/E2B服务基准测试指标定义.md#543-宿主机到云存储延迟-host-to-cloud-storage-latency) |
| **大页内存性能提升** | % | 性能优化关键 | [§5.2.3](docs/E2B服务基准测试指标定义.md#523-大页内存支持-huge-pages-support) |
| **单位算力成本** | USD/分 | 性价比核心指标 | [§7.2.2](docs/E2B服务基准测试指标定义.md#722-单位算力成本-cost-per-performance-unit) |

### 建议测试指标（🟡 重要）

13项重要指标，详见 [指标定义文档 §8.2](docs/E2B服务基准测试指标定义.md#82-重要指标建议测)

### 可选测试指标（🟢 可选）

4项可选指标，详见 [指标定义文档 §8.3](docs/E2B服务基准测试指标定义.md#83-可选指标按需测)

## 📚 完整文档

### 核心文档
- **[E2B服务基准测试指标定义.md](docs/E2B服务基准测试指标定义.md)** - 完整的指标定义、计算方法和测试标准
- **[E2B服务基准测试记录表单.md](docs/E2B服务基准测试记录表单.md)** - 用于记录单个云厂商的详细测试数据
- **[E2B服务基准测试汇总对比表.md](docs/E2B服务基准测试汇总对比表.md)** - 用于跨云厂商性能对比分析
- **[容量测试说明.md](docs/06_容量测试说明.md)** - 沙箱容量和负载均衡测试指南

### 测试指南
- **[客户端测试指南](tests/client/README.md)** - 沙箱生命周期、模板快照、容量测试的详细说明
- **[宿主机测试指南](tests/host/README.md)** - 硬件性能测试和云存储测试的详细说明
- **[IO 诊断工具指南](tests/host/io_test_scripts/README.md)** - 磁盘性能诊断工具使用指南
- **[沙箱测试指南](tests/sandbox/README.md)** - 沙箱内自动化测试的详细说明

## ⚡ 极速开始（使用 Makefile）

```bash
# 1. 初始化项目
make setup

# 2. 配置环境变量
cp env/.e2b_env.template env/.e2b_env
vim env/.e2b_env

# 3. 切换到指定环境
make switch-env ENV=awsdev
source env/.e2b_env_awsdev

# 4. 构建模板
make build

# 5. 运行快速测试
make quick-test

# 6. 查看完整命令
make help
```

## 🚀 快速开始（详细步骤）

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd awsdev-tpl

# 运行安装脚本
./setup.sh
```

### 2. 配置环境变量

```bash
# 复制配置模板
cp env/.e2b_env.template env/.e2b_env

# 编辑配置文件，填入实际的API密钥和配置
vim env/.e2b_env
```

需要配置的关键变量：
- `E2B_DOMAIN`: E2B 服务域名
- `E2B_API_KEY`: E2B API 密钥
- `E2B_TEMPLATE_NAME`: 沙箱模板名称
- `NOMAD_ADDR`: Nomad 服务地址（冷启动测试需要）
- `NOMAD_TOKEN`: Nomad 访问令牌（冷启动测试需要）

### 3. 环境切换（可选）

本项目支持多环境配置（AWS、Azure等），可以方便地切换：

```bash
# 列出所有可用环境
./switch-env.sh --list

# 切换到指定环境
./switch-env.sh awsdev

# 加载环境变量
source env/.e2b_env_awsdev
```

或使用 Makefile：
```bash
make switch-env ENV=awsdev
source env/.e2b_env_awsdev
```

### 4. 加载环境变量

```bash
# 加载默认环境
source env/.e2b_env

# 或加载指定环境
source env/.e2b_env_awsdev
```

### 5. 运行测试

#### 使用 Makefile（推荐）

```bash
# 查看所有可用命令
make help

# 快速测试
make quick-test

# 完整测试
make full-test

# 构建模板并测试
make build && make test-all
```

#### 使用 Python 脚本

**运行所有测试**：
```bash
python3 tests/client/run_all_tests.py
```

**运行特定测试**：

**沙箱生命周期测试**：
```bash
# 冷启动测试
python3 tests/client/01_sandbox_lifecycle.py --test cold --iterations 10

# 热启动测试
python3 tests/client/01_sandbox_lifecycle.py --test warm --iterations 10
```

**模板和快照测试**：
```bash
python3 tests/client/02_template_snapshot.py
```

**宿主机性能测试**：
```bash
# 使用统一入口脚本运行所有宿主机测试
python3 tests/host/run_host_tests.py --all

# 或运行特定测试
python3 tests/host/run_host_tests.py --cpu --disk
python3 tests/host/04_host_performance.py
```

**云存储性能测试**：
```bash
python3 tests/host/05_cloud_storage.py
```

**沙箱内性能测试**（自动化方式）：
```bash
# 自动在沙箱内执行CPU、内存、磁盘、网络测试
python3 tests/sandbox/run_sandbox_tests.py --test cpu memory disk network
```

**沙箱容量和负载均衡测试**：
```bash
# 标准测试
python3 tests/client/06_sandbox_capacity.py --batch-size 10 --max-sandboxes 200

# 详细说明见文档
```

更多详情请参考 [容量测试说明](docs/06_容量测试说明.md)

### 5. 生成测试报告

```bash
# 生成汇总报告
python3 tests/client/generate_report.py

# 生成可视化报告
python3 tests/client/generate_visual_report.py
```

## 📊 测试结果

测试结果分为两类：
- `outputs/` - 测试临时输出文件（JSON格式，可删除）
- `reports/` - 正式测试报告（Markdown格式，重要）

## 📦 项目结构

```
.
├── e2b-template/            # E2B 沙箱模板
│   ├── e2b.Dockerfile      # Docker 构建文件
│   ├── e2b.toml            # 当前使用的配置（gitignore）
│   ├── e2b.toml.awsdev     # AWS 开发环境配置
│   ├── e2b.toml.azure      # Azure 环境配置
│   ├── e2b.toml.template   # 配置模板
│   ├── app.py              # 模板应用代码
│   └── requirements.txt    # 模板应用依赖
│
├── env/                     # 环境变量管理
│   ├── .e2b_env.template   # 环境变量模板（提交到git）
│   ├── .e2b_env_awsdev     # AWS 开发环境（gitignore）
│   └── .e2b_env_azure      # Azure 环境（gitignore）
│
├── tests/                   # 测试脚本（已完全 Python 化）
│   ├── requirements.txt    # 测试框架依赖
│   ├── utils/              # 共享工具库（logger等）
│   ├── client/             # 客户端测试脚本
│   │   ├── README.md                  # 客户端测试完整指南
│   │   ├── run_all_tests.py           # 统一入口脚本（推荐）
│   │   ├── 01_sandbox_lifecycle.py    # 沙箱生命周期测试
│   │   ├── 02_template_snapshot.py    # 模板和快照测试
│   │   ├── 06_sandbox_capacity.py     # 沙箱容量测试
│   │   ├── test_template_build.py     # 模板构建验证
│   │   └── cleanup_sandboxes.py       # 清理工具
│   ├── host/               # 宿主机测试脚本
│   │   ├── README.md                  # 宿主机测试完整指南
│   │   ├── run_host_tests.py          # 统一入口脚本（推荐）
│   │   ├── 04_host_performance.py     # 宿主机性能测试
│   │   ├── 05_cloud_storage.py        # 云存储性能测试
│   │   └── io_test_scripts/           # IO 诊断工具（shell脚本）
│   │       ├── README.md              # IO 工具使用指南
│   │       ├── fio_comprehensive_test.sh
│   │       ├── aws_ebs_monitor.sh
│   │       └── ...
│   └── sandbox/            # 沙箱内自动化测试
│       ├── README.md                  # 沙箱测试完整指南
│       ├── run_sandbox_tests.py       # 自动化测试引擎（推荐）
│       ├── example_command_simple.py  # SDK 示例
│       └── _deprecated_shell_scripts/ # 备份的测试脚本
│           └── README.md              # 迁移说明
│
├── reports/                 # 测试报告（重要结果）
│   ├── E2B服务基准测试记录表单-awsdev.md
│   └── E2B服务基准测试记录表单-azure.md
│
├── outputs/                 # 测试临时输出（可删除）
│
├── docs/                    # 项目文档
│   ├── E2B服务基准测试指标定义.md
│   ├── E2B服务基准测试记录表单.md
│   ├── E2B服务基准测试汇总对比表.md
│   └── 06_容量测试说明.md
│
├── switch-env.sh            # 环境切换脚本
├── setup.sh                 # 环境安装脚本
├── Makefile                 # Make 命令集合
└── README.md                # 本文件
```

## 🔧 依赖要求

### Python 依赖
- `e2b` - E2B SDK
- `pyyaml` - YAML 解析

### 系统工具（可选，用于宿主机性能测试）
- `sysbench` - CPU 和内存基准测试
- `fio` - 磁盘 I/O 基准测试
- `iperf3` - 网络性能测试

### Nomad CLI（可选，用于冷启动测试）
- 用于重启 orchestrator 进行真正的冷启动测试

## ⚠️ 注意事项

### 测试前提

1. **配置一致性**：确保所有云厂商测试环境的配置尽可能一致
   - vCPU: 96核或等效
   - 内存: 384GB
   - 本地存储: 6TB SSD

2. **模板一致性**：所有沙箱内部性能测试必须使用**同一模板**构建的沙箱

3. **测试标准**：
   - 每项指标测试 ≥10 次
   - 使用中位数，剔除异常值（±3σ）
   - 测试间隔 ≥1 秒

### SSL 证书

如果使用自签名证书，测试脚本已内置证书验证跳过功能。生产环境建议配置有效的 SSL 证书。

## 📝 测试流程

1. **准备阶段**
   - 搭建 E2B 服务环境
   - 配置环境变量
   - 准备统一的沙箱模板

2. **执行测试**
   - 按优先级执行测试（核心 → 重要 → 可选）
   - 记录测试数据到 [测试记录表单](docs/E2B服务基准测试记录表单.md)

3. **数据分析**
   - 使用生成报告工具汇总数据
   - 填写 [汇总对比表](docs/E2B服务基准测试汇总对比表.md) 进行跨云厂商对比

4. **结果输出**
   - 生成性能对比报告
   - 计算性价比指标
   - 提供优化建议

## 🔍 故障排查

### 常见问题

**Q: 冷启动测试失败，提示无法连接 Nomad**
A: 确保 `NOMAD_ADDR` 和 `NOMAD_TOKEN` 配置正确，并且 Nomad 服务可访问

**Q: SSL 证书验证错误**
A: 测试脚本已禁用 SSL 验证，如仍有问题，检查 `PYTHONHTTPSVERIFY` 环境变量

**Q: 沙箱内性能测试失败**
A: 确保沙箱模板中已安装 `sysbench` 和 `fio` 工具

## 📄 许可证

[根据项目实际情况填写]

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📧 联系方式

[根据项目实际情况填写]
