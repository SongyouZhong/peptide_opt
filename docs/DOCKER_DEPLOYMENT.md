# Peptide Optimization Docker 部署指南

## 概述

本指南介绍如何使用 Docker 部署 Peptide Optimization 服务。提供了以下几种部署方式：

| 部署方式 | 说明 | 适用场景 |
|---------|------|---------|
| `docker-compose.yml` | 完整版，包含 PostgreSQL 和 SeaweedFS | 全新部署、测试环境 |
| `docker-compose.standalone.yml` | 仅应用服务，连接外部依赖 | 已有数据库和存储服务 |
| `docker-compose.gpu.yml` | GPU 加速版 | 需要 CUDA 加速的场景 |

## 快速开始

### 1. 准备环境

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 安装 Docker Compose (如果未包含)
sudo apt-get install docker-compose-plugin

# 添加当前用户到 docker 组（避免每次使用 sudo）
sudo usermod -aG docker $USER
newgrp docker
```

### 2. 配置环境变量

```bash
# 复制环境变量模板
cp .env.docker .env

# 编辑配置
vim .env
```

主要配置项：
```env
# 数据库配置
DB_HOST=postgres
DB_PORT=5432
DB_USER=admin
DB_PASSWORD=your_secure_password  # 修改为安全密码
DB_NAME=mydatabase

# SeaweedFS 配置
SEAWEED_FILER_ENDPOINT=http://seaweedfs:8888
SEAWEED_BUCKET=astramolecula

# 任务处理配置
MAX_WORKERS=2
POLL_INTERVAL=30
```

### 3. 构建和启动

#### 完整部署（推荐新用户）

```bash
# 构建镜像
docker compose build

# 启动所有服务
docker compose up -d

# 查看日志
docker compose logs -f peptide-opt
```

#### 仅部署应用（连接外部服务）

```bash
# 修改 .env 中的数据库和存储地址
vim .env

# 启动
docker compose -f docker-compose.standalone.yml up -d
```

#### GPU 加速部署

```bash
# 确保安装了 NVIDIA Container Toolkit
# https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html

# 构建 GPU 镜像
docker build -f Dockerfile.gpu -t peptide-opt:gpu .

# 启动
docker compose -f docker-compose.gpu.yml up -d
```

## 常用命令

### 服务管理

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 重启服务
docker compose restart

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f [service_name]

# 进入容器
docker compose exec peptide-opt bash
```

### 镜像管理

```bash
# 构建镜像
docker compose build

# 重新构建（不使用缓存）
docker compose build --no-cache

# 拉取最新镜像
docker compose pull
```

### 数据管理

```bash
# 查看数据卷
docker volume ls

# 备份数据库
docker compose exec postgres pg_dump -U admin mydatabase > backup.sql

# 恢复数据库
cat backup.sql | docker compose exec -T postgres psql -U admin mydatabase

# 清理未使用的数据卷（谨慎使用）
docker volume prune
```

## 目录挂载说明

| 容器路径 | 说明 |
|---------|------|
| `/app/input` | 输入文件目录 |
| `/app/output` | 输出文件目录 |
| `/app/logs` | 日志目录 |
| `/tmp/peptide_opt` | 临时文件目录 |

## 端口映射

| 端口 | 服务 | 说明 |
|------|------|------|
| 8001 | peptide-opt | Peptide API 服务 |
| 5432 | postgres | PostgreSQL 数据库 |
| 9333 | seaweedfs | SeaweedFS Master |
| 8080 | seaweedfs | SeaweedFS Volume |
| 8888 | seaweedfs | SeaweedFS Filer |
| 8333 | seaweedfs | SeaweedFS S3 API |

## 健康检查

服务内置健康检查，可通过以下方式验证：

```bash
# 检查 API 服务
curl http://localhost:8001/

# 检查数据库
docker compose exec postgres pg_isready -U admin

# 检查 SeaweedFS
curl http://localhost:9333/cluster/status
```

## 生产环境建议

### 1. 安全配置

```yaml
# docker-compose.override.yml
services:
  postgres:
    environment:
      - POSTGRES_PASSWORD=${SECURE_DB_PASSWORD}
    # 不暴露端口到外部
    ports: []
```

### 2. 资源限制

已在 docker-compose 中配置了资源限制，可根据实际情况调整：

```yaml
deploy:
  resources:
    limits:
      cpus: '4'
      memory: 8G
    reservations:
      cpus: '2'
      memory: 4G
```

### 3. 日志轮转

已配置 JSON 日志驱动和大小限制：

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### 4. 数据备份

建议定期备份以下数据卷：
- `peptide-postgres-data`: 数据库数据
- `peptide-seaweedfs-data`: 对象存储数据
- `peptide-output`: 输出文件

## 故障排除

### 容器无法启动

```bash
# 查看详细日志
docker compose logs peptide-opt

# 检查依赖服务状态
docker compose ps
```

### 数据库连接失败

```bash
# 检查数据库是否正常
docker compose exec postgres psql -U admin -c "SELECT 1;"

# 检查网络连接
docker compose exec peptide-opt nc -zv postgres 5432
```

### GPU 不可用

```bash
# 检查 NVIDIA 驱动
nvidia-smi

# 检查 Docker GPU 支持
docker run --rm --gpus all nvidia/cuda:11.8-base nvidia-smi
```

### 清理重建

```bash
# 停止并删除所有容器、网络
docker compose down

# 删除数据卷（会丢失数据！）
docker compose down -v

# 重新构建
docker compose build --no-cache
docker compose up -d
```

## 开发模式

开发时可以挂载本地代码：

```bash
# 创建 docker-compose.override.yml
cat > docker-compose.override.yml << 'EOF'
services:
  peptide-opt:
    volumes:
      - ./main.py:/app/main.py:ro
      - ./async_task_processor.py:/app/async_task_processor.py:ro
      - ./peptide_optimizer.py:/app/peptide_optimizer.py:ro
      - ./config:/app/config:ro
      - ./services:/app/services:ro
    environment:
      - LOG_LEVEL=DEBUG
EOF

# 启动（会自动合并 override 配置）
docker compose up -d
```

## 版本更新

```bash
# 拉取最新代码
git pull

# 重新构建镜像
docker compose build

# 滚动更新（无中断）
docker compose up -d --no-deps peptide-opt
```
