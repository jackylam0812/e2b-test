# 沙箱自动化性能测试

使用 E2B SDK 的 `sandbox.commands` API 自动化执行沙箱性能测试，无需手动进入沙箱。

## 特点

✅ **全自动化**：无需手动进入沙箱执行命令
✅ **实时输出**：测试过程中实时显示输出
✅ **结果保存**：自动保存 JSON 格式的测试结果
✅ **错误处理**：自动处理测试失败和异常情况
✅ **灵活配置**：可以选择运行特定测试

## 使用方法

### 1. 基本使用

```bash
# 加载环境变量
source env/.e2b_env

# 运行所有测试（CPU + 内存 + 磁盘 + 网络）
python3 tests/sandbox/run_sandbox_tests.py
```

### 2. 运行特定测试

```bash
# 只运行 CPU 测试
python3 tests/sandbox/run_sandbox_tests.py --test cpu

# 运行 CPU 和内存测试
python3 tests/sandbox/run_sandbox_tests.py --test cpu memory

# 运行磁盘测试
python3 tests/sandbox/run_sandbox_tests.py --test disk

# 运行网络性能测试
python3 tests/sandbox/run_sandbox_tests.py --test network

# 运行组合测试
python3 tests/sandbox/run_sandbox_tests.py --test cpu memory network
```

### 3. 运行网络诊断

```bash
# 运行网络诊断（用于故障排查）
python3 tests/sandbox/run_sandbox_tests.py --diagnose
```

### 4. 指定输出目录

```bash
python3 tests/sandbox/run_sandbox_tests.py --output outputs/my_tests
```

## 工作流程

1. **创建沙箱**：使用 E2B SDK 创建一个沙箱实例
2. **上传脚本**：将测试脚本上传到沙箱的 `/tmp` 目录
3. **执行测试**：使用 `sandbox.commands.run()` 执行测试脚本
4. **实时监控**：使用回调函数实时显示测试输出
5. **获取结果**：从沙箱读取 JSON 格式的测试结果
6. **保存本地**：将结果保存到本地输出目录
7. **清理资源**：自动关闭沙箱

## 输出文件

测试结果保存在 `outputs/sandbox_tests/` 目录：

```
outputs/sandbox_tests/
├── cpu_test_20231219_140530.json         # CPU 测试结果
├── memory_test_20231219_140545.json      # 内存测试结果
├── disk_test_20231219_140620.json        # 磁盘测试结果
├── network_test_20231219_140635.json     # 网络测试结果
├── network_diagnose_20231219_140650.txt  # 网络诊断输出
└── summary_20231219_140700.json          # 汇总报告
```

### 结果格式示例

**CPU 测试结果：**
```json
{
  "single_thread_events_per_sec": 1234.56,
  "multi_thread_events_per_sec": 4567.89,
  "cpu_threads": 4,
  "test_date": "2023-12-19T14:05:30+08:00"
}
```

**内存测试结果：**
```json
{
  "memory_bandwidth": {
    "write_mbs": 12345.67,
    "read_mbs": 13456.78,
    "random_access_ops_per_sec": 123456.78
  },
  "memory_allocation_latency_us": {
    "size_1kb": 0.123,
    "size_4kb": 0.234,
    "size_16kb": 0.345,
    "size_64kb": 0.456,
    "size_256kb": 0.567
  },
  "memory_copy_throughput_mbs": 10234.56,
  "test_date": "2023-12-19T14:05:45+08:00"
}
```

**网络测试结果：**
```json
{
  "network": {
    "latency_ms": 15.34,
    "download_bandwidth_mbs": 45.67,
    "upload_bandwidth_mbs": 12.34
  },
  "test_date": "2023-12-19T14:06:00+08:00"
}
```

**注意**：网络测试依赖外部网络连接，某些指标可能显示为 `null`（如在无外网环境中）。

## 对比：手动 vs 自动化

### 手动方式（旧）

```bash
# 1. 手动创建沙箱
e2b sbx create

# 2. 手动进入沙箱
e2b sbx ssh <sandbox-id>

# 3. 在沙箱内手动执行
bash run_cpu_test.sh

# 4. 手动复制结果
cat /tmp/sandbox_cpu_result.json

# 5. 手动关闭沙箱
exit
e2b sbx kill <sandbox-id>
```

### 自动化方式（新）

```bash
# 一条命令完成所有操作
python3 tests/sandbox/run_sandbox_tests.py
```

## 技术实现

使用 E2B SDK 的核心 API：

```python
# 创建沙箱
sandbox = Sandbox(api_key=E2B_API_KEY, timeout=1800)

# 上传脚本
sandbox.files.write("/tmp/test.sh", script_content)

# 执行命令（实时输出）
result = sandbox.commands.run(
    "/tmp/test.sh",
    on_stdout=lambda line: print(line),
    timeout=300,
    user="root"
)

# 读取结果
result_json = sandbox.files.read("/tmp/result.json")

# 关闭沙箱
sandbox.kill()
```

## 优势

1. **效率提升**：无需手动操作，一键完成所有测试
2. **可重复性**：脚本化保证测试过程一致
3. **结果管理**：自动保存和组织测试结果
4. **错误处理**：自动捕获和报告错误
5. **易于集成**：可以集成到 CI/CD 流程

## 注意事项

- 测试需要 root 权限来安装 sysbench 等工具
- CPU 和内存测试各需要约 1-2 分钟
- 磁盘测试可能需要 3-5 分钟
- 确保沙箱有足够的超时时间（默认 30 分钟）

## 故障排查

### 问题：测试超时

```bash
# 增加超时时间
# 在脚本中修改：timeout=1800  # 30分钟
```

### 问题：权限不足

```bash
# 确保使用 root 用户执行
# 在脚本中：user="root"
```

### 问题：结果读取失败

```bash
# 检查结果文件是否存在
sandbox.commands.run("ls -la /tmp/sandbox_*_result.json")
```

## 扩展

### 添加新测试

1. 创建测试脚本（如 `run_network_test.sh`）
2. 在 `SandboxTester` 类中添加对应方法
3. 在 `run_all_tests()` 中调用新方法

示例：

```python
def run_network_test(self):
    """运行网络性能测试"""
    script_path = self.test_scripts_dir / "run_network_test.sh"
    # ... 实现逻辑
```

### 批量测试

```python
# 创建脚本运行多个沙箱并行测试
for i in range(10):
    tester = SandboxTester(output_dir=f"outputs/batch_{i}")
    tester.run_all_tests()
```

## 相关文件

- `run_sandbox_tests.py` - 自动化测试主脚本
- `run_cpu_test.sh` - CPU 测试脚本（在沙箱内执行）
- `run_memory_test.sh` - 内存测试脚本（在沙箱内执行）
- `run_disk_test.sh` - 磁盘测试脚本（在沙箱内执行）
- `example_command_simple.py` - SDK 命令执行示例

## 许可证

与项目主许可证相同
