# Peptide Optimization Service

肽段结构优化和序列设计服务，使用 ProteinMPNN 和分子对接技术。

## 📋 功能特性

- 🧬 使用 OmegaFold 进行肽段结构预测
- 🔬 分子对接和结合亲和力评分
- 🧪 使用 ProteinMPNN 进行序列优化
- 📊 性质分析和报告生成
- 🚀 异步任务处理
- 🗄️ PostgreSQL 数据库支持
- 📦 SeaweedFS 对象存储

## 🚀 快速开始

### 环境要求

- Python 3.10
- CUDA 11.3 (用于 GPU 加速)

### 依赖软件安装

#### 1. OmegaFold (肽段结构预测)

```bash
# 方式一：直接安装
pip install OmegaFold

# 方式二：从 GitHub 安装
pip install git+https://github.com/HeliXonProtein/OmegaFold
```

详情参考: https://github.com/HeliXonProtein/OmegaFold

#### 2. AutoDock CrankPep (分子对接)

```bash
# 下载 ADFRsuite
wget https://ccsb.scripps.edu/adfr/download/1038/ADFRsuite_Linux-x86_64_1.0.tar.gz

# 解压
tar zxvf ADFRsuite_Linux-x86_64_1.0.tar.gz

# 安装
cd ADFRsuite_x86_64Linux_1.0
./install.sh -d ~/ADFRsuite-1.0 -c 0
```

详情参考: https://ccsb.scripps.edu/adcp/downloads/

#### 3. AutoDock Vina (结合评分计算)

```bash
# 方式一：pip 安装
pip install vina

# 方式二：apt 安装
sudo apt-get install autodock-vina
```

#### 4. PyMOL (添加氢原子和突变)

```bash
conda install -c conda-forge -c schrodinger pymol-bundle
```

#### 5. BioPython

```bash
pip install biopython
```

#### 6. ProteinMPNN (序列优化)

```bash
# 克隆到 vendor 目录（无需安装）
git clone https://github.com/dauparas/ProteinMPNN vendor/ProteinMPNN
```

### 项目安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/peptide-opt.git
cd peptide-opt

# 方式一：使用 conda 环境（推荐）
conda env create -f environment.yml
conda activate peptide

# 方式二：使用 venv
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows
pip install -e ".[dev]"
```

### 运行

#### 1. 启动 API 服务

```bash
# 使用命令行工具
peptide-opt serve --host 0.0.0.0 --port 8000

# 或使用 python -m
python -m peptide_opt serve
```

#### 2. 直接运行优化

```bash
# 运行完整优化流程
peptide-opt run --input-dir ./data/input --output-dir ./data/output

# 指定参数
peptide-opt run \
    --input-dir ./data/input \
    --output-dir ./data/output \
    --cores 8 \
    --no-cleanup
```

### Docker 部署

```bash
# 复制环境变量配置
cp .env.example .env
# 编辑 .env 设置数据库密码等

# 构建并启动
cd docker
docker compose up -d

# 查看日志
docker compose logs -f peptide-opt
```

## 📁 项目结构

```
peptide_opt/
├── src/peptide_opt/          # 源代码
│   ├── api/                  # FastAPI 应用
│   ├── core/                 # 核心业务逻辑
│   ├── tasks/                # 异步任务处理
│   ├── db/                   # 数据库层
│   ├── storage/              # 存储服务
│   └── config/               # 配置管理
├── tests/                    # 测试
├── docker/                   # Docker 配置
├── docs/                     # 文档
├── vendor/                   # 第三方依赖 (ProteinMPNN)
└── data/                     # 数据目录
```

## 📖 API 文档

启动服务后访问:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🔧 配置

配置通过以下方式管理（优先级从高到低）:

1. 环境变量 (`PEPTIDE_*`)
2. `.env` 文件
3. `config/settings.yaml`

主要配置项:

```yaml
# 数据库配置
DB_HOST=localhost
DB_PORT=5432
DB_USER=admin
DB_PASSWORD=secret
DB_NAME=peptide_opt

# 存储配置
SEAWEED_FILER_ENDPOINT=http://localhost:8888
SEAWEED_BUCKET=peptide-opt

# 任务处理器
MAX_WORKERS=2
POLL_INTERVAL=30
```

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行并显示覆盖率
pytest --cov=src/peptide_opt --cov-report=html

# 运行特定测试
pytest tests/unit/test_validators.py -v
```

## 📝 优化流程

1. **步骤1**: 使用 OmegaFold 预测肽段结构
2. **步骤2**: 添加氢原子到受体和肽段
3. **步骤3**: 分子对接
4. **步骤4**: 原子排序和添加氢原子
5. **步骤5**: 计算结合亲和力评分
6. **步骤6**: 合并肽段和蛋白质结构
7. **步骤7**: 使用 ProteinMPNN 进行序列优化
8. **步骤8**: 最终分析和报告生成

## 📂 输入文件要求

输入目录需要包含:
- `peptide.fasta`: 肽段序列文件
- `*.pdb`: 受体蛋白质结构文件

## 🤝 贡献

欢迎贡献代码！请查看 [CONTRIBUTING.md](docs/CONTRIBUTING.md)。

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE)
