# Peptide Optimization 迁移计划

## 📋 概述

本文档分析 `peptide_opt` 子组件需要进行的改造，以与主系统 `AstraMolecula` 保持一致，使用 PostgreSQL 数据库和 SeaweedFS 对象存储。

**分析日期：** 2025-01-05

---

## 🔍 当前状态分析

### 现有技术栈

| 组件 | peptide_opt 当前 | AstraMolecula 目标 |
|------|------------------|-------------------|
| 数据库 | MySQL (aiomysql) | PostgreSQL (psycopg2) |
| 存储 | 本地文件系统 | SeaweedFS |
| 配置 | 硬编码 | YAML + 环境变量 |
| 依赖管理 | environment.yml | environment.yml + config模块 |

---

## 🛠️ 需要改造的文件

### 1. 数据库相关改造 (高优先级)

#### 1.1 `async_task_processor.py`

**当前问题：**
- 使用 `aiomysql` 连接 MySQL 数据库
- 数据库配置硬编码在代码中
- SQL 语法为 MySQL 格式（使用 `%s` 占位符）

**需要修改的代码段：**

```python
# 当前代码 (第 16 行)
import aiomysql

# 当前代码 (第 73-81 行)
self.db_config = {
    'host': '127.0.0.1',
    'user': 'vina_user',
    'password': 'Aa7758258123',
    'db': 'project1',
    'charset': 'utf8mb4',
    'autocommit': True
}

# 当前代码 (第 118-122 行) - 获取数据库连接
async def get_db_connection(self):
    try:
        connection = await aiomysql.connect(**self.db_config)
        return connection
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None
```

**改造方案：**
1. 将 `aiomysql` 替换为 `psycopg2` 或 `asyncpg`
2. 导入并使用 AstraMolecula 的数据库模块
3. 参考 `AstraMolecula/database/db.py` 使用连接池

**目标代码示例：**
```python
# 方案一：使用同步 psycopg2（与 AstraMolecula 一致）
from database.db import get_connection

# 方案二：使用异步 asyncpg（保持异步特性）
import asyncpg
```

---

#### 1.2 `test_db_connection.py`

**当前问题：**
- 使用 `aiomysql` 测试 MySQL 连接
- 配置硬编码

**改造方案：**
- 改为使用 PostgreSQL 连接测试
- 从配置文件读取数据库参数

---

#### 1.3 `main.py`

**当前问题：**
- 文件下载接口直接从本地文件系统读取
- 数据库查询使用 MySQL 语法

**需要修改的代码段（第 199-315 行）：**

```python
# 当前代码 - 使用 MySQL 连接查询
connection = await async_processor.get_db_connection()
async with connection.cursor() as cursor:
    await cursor.execute(
        """
        SELECT job_dir, status 
        FROM tasks 
        WHERE id = %s AND task_type = 'peptide_optimization'
        """,
        (task_id,)
    )
```

**改造方案：**
1. 使用 `TaskService` 替代直接数据库操作
2. 集成 SeaweedFS 下载文件

---

### 2. 存储相关改造 (高优先级)

#### 2.1 创建 `services/storage/` 目录

**需要新增：**
- `services/__init__.py`
- `services/storage/__init__.py` - 从 AstraMolecula 复制
- `services/storage/seaweed_storage.py` - 从 AstraMolecula 复制
- `services/storage/config.py` - 存储配置

---

#### 2.2 `async_task_processor.py` - 存储集成

**当前问题：**
- 任务输入/输出文件仅存储在本地
- 无 SeaweedFS 集成

**需要添加的功能：**

```python
# 需要添加导入
from services.storage import get_storage

# 在任务处理完成后上传结果到 SeaweedFS
async def _upload_results_to_storage(self, task_id: str, job_dir: str):
    """上传任务结果到 SeaweedFS"""
    storage = get_storage()
    output_dir = Path(job_dir) / "output"
    
    for file_path in output_dir.glob("**/*"):
        if file_path.is_file():
            relative_path = file_path.relative_to(output_dir)
            remote_key = f"tasks/{task_id}/peptide/output/{relative_path}"
            await storage.upload_file(file_path, remote_key)
```

---

#### 2.3 `main.py` - 文件下载端点

**当前问题（第 199-315 行）：**
- `download_peptide_file` 仅从本地读取文件
- 不支持从 SeaweedFS 获取

**改造方案：**
```python
async def download_peptide_file(task_id: str, filename: str):
    # 优先从 SeaweedFS 获取
    storage = get_storage()
    remote_key = f"tasks/{task_id}/peptide/output/{filename}"
    
    if await storage.file_exists(remote_key):
        # 从 SeaweedFS 下载
        url = await storage.get_presigned_url(remote_key)
        return RedirectResponse(url)
    
    # 回退到本地文件
    # ... 现有的本地文件查找逻辑
```

---

### 3. 配置管理改造 (中优先级)

#### 3.1 创建 `config/` 目录结构

**需要新增/修改的文件：**

| 文件 | 说明 |
|------|------|
| `config/__init__.py` | 配置模块初始化 |
| `config/database_config.py` | 数据库配置（从 AstraMolecula 复制并修改） |
| `config/storage.py` | 存储配置 |
| `config/settings.py` | 设置加载器 |
| `config/settings.yaml` | YAML 配置文件 |

**示例 `config/settings.yaml`：**
```yaml
# Peptide Optimization 配置文件

# 数据库配置
database:
  host: "127.0.0.1"
  port: 5432
  user: "admin"
  password: "secret"
  database: "mydatabase"
  pool:
    min_size: 1
    max_size: 5

# 存储配置 (SeaweedFS)
storage:
  api_type: "filer"
  filer_endpoint: "http://localhost:8888"
  bucket: "astramolecula"  # 与主系统共用
  temp_dir: "/tmp/peptide_opt"

# 服务配置
server:
  host: "0.0.0.0"
  port: 8001
```

---

#### 3.2 `config/logging_config.py`

**当前问题：**
- 日志路径硬编码为 `/home/davis/projects/serverlogs`

**需要修改：**
```python
# 当前代码 (第 56 行)
log_dir = Path("/home/davis/projects/serverlogs")

# 改为
log_dir = Path(os.environ.get("LOG_DIR", "/var/log/peptide_opt"))
```

---

### 4. 依赖管理改造 (中优先级)

#### 4.1 `environment.yml`

**需要添加的依赖：**

```yaml
dependencies:
  # 移除
  # - aiomysql  # MySQL 异步驱动

  # 添加
  - psycopg2-binary  # PostgreSQL 驱动
  - asyncpg          # PostgreSQL 异步驱动（可选）
  - aiohttp          # SeaweedFS HTTP 客户端
  - pyyaml           # YAML 配置解析
```

---

### 5. 数据库服务层改造 (中优先级)

#### 5.1 创建 `database/` 目录

**需要新增：**

| 文件 | 说明 |
|------|------|
| `database/__init__.py` | 模块初始化 |
| `database/db.py` | 数据库连接（从 AstraMolecula 复制） |
| `database/models/task.py` | 任务模型定义 |
| `database/services/task_service.py` | 任务服务层 |

**或者更简单的方案：**
- 直接导入 AstraMolecula 的 database 模块
- 确保 peptide_opt 可以 import AstraMolecula 的包

---

## 📊 改造优先级排序

| 优先级 | 改造项 | 工作量 | 影响范围 |
|--------|--------|--------|----------|
| P0 | 数据库驱动替换 (MySQL → PostgreSQL) | 中 | 核心功能 |
| P0 | 存储服务集成 (SeaweedFS) | 中 | 文件处理 |
| P1 | 配置管理统一 (YAML) | 低 | 运维友好 |
| P1 | 依赖更新 (environment.yml) | 低 | 部署 |
| P2 | 日志配置改进 | 低 | 调试 |
| P2 | 数据库服务层抽象 | 中 | 代码质量 |

---

## 🔄 改造步骤

### 阶段 1: 基础设施 (预计 2-3 小时)

1. **更新依赖**
   - [ ] 修改 `environment.yml`，添加 PostgreSQL 和 aiohttp
   - [ ] 重建 conda 环境

2. **复制存储模块**
   - [ ] 创建 `services/storage/` 目录
   - [ ] 复制 SeaweedStorage 相关文件
   - [ ] 调整导入路径

3. **创建配置模块**
   - [ ] 创建 `config/settings.yaml`
   - [ ] 创建配置加载器

### 阶段 2: 数据库改造 (预计 3-4 小时)

4. **数据库连接改造**
   - [ ] 替换 `aiomysql` 为 PostgreSQL 驱动
   - [ ] 修改 `async_task_processor.py` 中的数据库操作
   - [ ] 更新 SQL 语法（如有差异）

5. **测试数据库连接**
   - [ ] 修改 `test_db_connection.py`
   - [ ] 验证连接和查询

### 阶段 3: 存储集成 (预计 2-3 小时)

6. **任务结果上传**
   - [ ] 在 `async_task_processor.py` 中添加上传逻辑
   - [ ] 任务完成后将输出上传到 SeaweedFS

7. **文件下载改造**
   - [ ] 修改 `main.py` 中的 `download_peptide_file`
   - [ ] 支持从 SeaweedFS 获取文件

### 阶段 4: 测试验证 (预计 2 小时)

8. **集成测试**
   - [ ] 提交测试任务
   - [ ] 验证任务处理流程
   - [ ] 验证文件下载功能

---

## 📁 最终目录结构

```
peptide_opt/
├── config/
│   ├── __init__.py
│   ├── database_config.py    # PostgreSQL 配置
│   ├── storage.py            # SeaweedFS 配置
│   ├── settings.py           # 配置加载器
│   ├── settings.yaml         # YAML 配置文件
│   └── logging_config.py     # 日志配置（已更新）
├── database/
│   ├── __init__.py
│   ├── db.py                 # PostgreSQL 连接池
│   └── services/
│       └── task_service.py   # 任务服务
├── services/
│   ├── __init__.py
│   └── storage/
│       ├── __init__.py
│       └── seaweed_storage.py
├── async_task_processor.py   # 已改造
├── main.py                   # 已改造
├── peptide_optimizer.py      # 无需修改
├── utils.py                  # 无需修改
└── environment.yml           # 已更新依赖
```

---

## ⚠️ 注意事项

1. **PostgreSQL vs MySQL 语法差异**
   - MySQL: `NOW()` → PostgreSQL: `NOW()` ✅ (兼容)
   - MySQL: `%s` 占位符 → PostgreSQL: `%s` ✅ (psycopg2 兼容)
   - 字符串连接：MySQL 使用 `CONCAT()`, PostgreSQL 可用 `||`

2. **异步 vs 同步**
   - 当前使用 `aiomysql`（异步）
   - AstraMolecula 使用 `psycopg2`（同步）
   - 可选择使用 `asyncpg` 保持异步特性

3. **共享 Bucket**
   - peptide_opt 将使用与 AstraMolecula 相同的 bucket `astramolecula`
   - 使用 `tasks/{task_id}/peptide/` 前缀区分

4. **向后兼容**
   - 文件下载应支持本地文件回退
   - 渐进式迁移，不影响历史数据

---

## 📚 参考文件

- `AstraMolecula/database/db.py` - PostgreSQL 连接池实现
- `AstraMolecula/services/storage/seaweed_storage.py` - SeaweedFS 客户端
- `AstraMolecula/config/settings.yaml` - 配置文件示例
- `AstraMolecula/async_task_processor.py` - 改造后的任务处理器
