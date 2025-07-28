# Peptide Optimization FastAPI Interface

## 项目概述

这是一个基于FastAPI的肽段优化流程接口，将原有的肽段优化管道包装成RESTful API服务，支持异步任务处理和状态监控。

## 核心功能

- **结构预测**: 基于FASTA序列进行肽段3D结构预测
- **分子对接**: 肽段与目标蛋白的分子对接计算
- **序列优化**: 使用ProteinMPNN进行序列优化
- **性质分析**: 理化性质和结合亲和力分析

## 环境要求

### 前提条件
- 已激活的conda环境
- Python 3.8+
- 必要的科学计算包

### 依赖包检查
项目启动时会自动检查必需的Python包：
- fastapi
- uvicorn  
- biopython
- pandas
- pydantic
- python-multipart

如有缺失包，请在您的conda环境中安装相应依赖。

### 验证ProteinMPNN
确保 `ProteinMPNN/` 目录存在且包含必要的模型文件。

## 启动服务

### 方法1: 使用启动脚本
```bash
python start_server.py
```

### 方法2: 直接启动
```bash
python main.py
```

### 方法3: 使用uvicorn
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

服务启动后访问：
- **API服务**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **交互式文档**: http://localhost:8000/redoc

## API接口说明

### 1. 健康检查
```http
GET /health
```

**响应示例**:
```json
{
  "status": "healthy",
  "timestamp": "2025-07-27T10:30:00"
}
```

### 2. 启动优化任务
```http
POST /optimize
```

**请求参数**:
- `pdb_file_path` (string, 必需): PDB结构文件的绝对路径
- `fasta_file_path` (string, 必需): FASTA序列文件的绝对路径
- `output_path` (string, 必需): 结果输出目录路径
- `user_id` (string, 必需): 用户ID标识
- `cores` (int, 可选): CPU核心数，默认12
- `cleanup` (bool, 可选): 是否清理中间文件，默认true

**请求示例**:
```bash
curl -X POST "http://localhost:8000/optimize" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "pdb_file_path=/absolute/path/to/protein.pdb" \
  -d "fasta_file_path=/absolute/path/to/peptide.fasta" \
  -d "output_path=/absolute/path/to/output" \
  -d "user_id=user123" \
  -d "cores=8" \
  -d "cleanup=true"
```

**响应示例**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Optimization task started",
  "user_id": "user123"
}
```

### 3. 查询任务状态
```http
GET /status/{task_id}
```

**响应示例**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "user123",
  "status": "running",
  "message": "Optimization pipeline is running...",
  "created_at": "2025-07-27T10:30:00",
  "completed_at": null,
  "output_path": null,
  "error_message": null
}
```

**状态值说明**:
- `pending`: 任务已创建，等待开始
- `running`: 任务正在执行
- `completed`: 任务成功完成
- `failed`: 任务执行失败

### 4. 获取用户任务列表
```http
GET /user/{user_id}/tasks
```

**响应示例**:
```json
{
  "user_id": "user123",
  "total_tasks": 2,
  "tasks": [
    {
      "task_id": "task1",
      "status": "completed",
      "message": "Optimization completed successfully"
    },
    {
      "task_id": "task2", 
      "status": "running",
      "message": "Optimization pipeline is running..."
    }
  ]
}
```

### 5. 删除任务记录
```http
DELETE /task/{task_id}
```

**说明**: 只能删除已完成或失败的任务，不能删除运行中的任务。

## 测试脚本使用

### 准备测试数据
确保输入文件存在：
- `./input/5ffg.pdb`: 目标蛋白结构文件
- `./input/peptide.fasta`: 肽段序列文件

### 运行测试
```bash
python test_api.py
```

测试脚本会自动：
1. 检查服务器健康状态
2. 启动优化任务
3. 监控任务执行进度
4. 验证结果输出

### 自定义测试参数
编辑 `test_api.py` 中的配置：
```python
BASE_URL = "http://localhost:8000"
PDB_FILE = "./input/5ffg.pdb"
FASTA_FILE = "./input/peptide.fasta"
OUTPUT_DIR = "./test_output"
USER_ID = "test_user_001"
```

## 输入文件要求

### PDB文件格式
- 标准PDB格式
- 必须包含ATOM或HETATM记录
- 推荐使用清洁的蛋白质结构（无缺失残基）

### FASTA文件格式
```
>peptide_sequence
MKLLHQKLSFLLLGLLLLGLLLPGCCNKKPTCRKGKLPIYHRNIMDVRHAQRKKRHKKKRISK
```

- 标准FASTA格式
- 必须以">"开头
- 支持单条肽段序列

## 输出结果

优化完成后，输出目录将包含：

### 主要结果文件
- `result.csv`: 详细分析报告
- `complex1.pdb` - `complex10.pdb`: 优化后的复合物结构

### 分析报告内容
- 序列优化结果
- 结合亲和力预测
- 理化性质分析
- 结构质量评估

## 错误处理

### 常见错误类型
1. **文件不存在**: 检查输入文件路径是否正确
2. **格式错误**: 验证PDB和FASTA文件格式
3. **依赖缺失**: 确保所有Python包已在conda环境中正确安装
4. **权限问题**: 检查输出目录写入权限

### 调试建议
1. 查看任务状态中的`error_message`字段
2. 设置`cleanup=false`保留中间文件
3. 检查服务器日志输出

## 性能优化

### 建议配置
- **CPU核心数**: 根据系统配置调整`cores`参数
- **内存要求**: 建议至少8GB RAM
- **存储空间**: 每个任务约需要1-2GB临时空间

### 并发处理
- API支持多个任务并行执行
- 每个用户任务在独立的工作目录中运行
- 自动资源清理避免磁盘空间耗尽

## 示例工作流

```python
import requests

# 1. 启动优化任务
response = requests.post("http://localhost:8000/optimize", data={
    "pdb_file_path": "/path/to/protein.pdb",
    "fasta_file_path": "/path/to/peptide.fasta", 
    "output_path": "/path/to/output",
    "user_id": "researcher_001",
    "cores": 8
})

task_id = response.json()["task_id"]

# 2. 监控任务状态
import time
while True:
    status = requests.get(f"http://localhost:8000/status/{task_id}").json()
    print(f"Status: {status['status']} - {status['message']}")
    
    if status['status'] in ['completed', 'failed']:
        break
    time.sleep(30)

# 3. 处理结果
if status['status'] == 'completed':
    print(f"Results available at: {status['output_path']}")
```

## 技术架构

- **框架**: FastAPI + Uvicorn
- **任务处理**: 异步后台任务
- **存储**: 文件系统（本地存储）
- **监控**: 内存状态跟踪
- **文档**: 自动生成OpenAPI规范

## 扩展建议

1. **数据库集成**: 替换内存状态存储
2. **文件上传**: 支持直接文件上传接口
3. **结果下载**: 添加结果文件下载端点
4. **用户认证**: 集成身份验证系统
5. **队列管理**: 使用Celery等任务队列
6. **容器化**: Docker部署支持
