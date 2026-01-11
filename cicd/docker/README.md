# Peptide Optimization CI/CD Docker 配置

本目录包含用于 CI/CD 流程的 Docker 配置文件。

## 目录结构

```
cicd/docker/
├── Dockerfile.ci          # CI/CD 专用 Dockerfile（用于自动化测试）
├── docker-compose.ci.yml  # CI/CD 测试环境
└── README.md              # 本文件
```

## CI/CD 使用

### GitHub Actions 示例

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build and Test
        run: |
          docker compose -f cicd/docker/docker-compose.ci.yml up --build --abort-on-container-exit
          
      - name: Build Production Image
        run: |
          docker build -t peptide-opt:${{ github.sha }} .
```

### 本地 CI 测试

```bash
# 运行完整的 CI 测试
docker compose -f cicd/docker/docker-compose.ci.yml up --build

# 清理
docker compose -f cicd/docker/docker-compose.ci.yml down -v
```

## 生产部署

生产环境使用项目根目录的 Dockerfile 和 docker-compose.yml：

```bash
# 部署到生产环境
cd /path/to/peptide_opt
docker compose up -d
```

详见 [docs/DOCKER_DEPLOYMENT.md](../../docs/DOCKER_DEPLOYMENT.md)
