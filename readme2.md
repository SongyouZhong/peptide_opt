# Peptide Optimization Pipeline 安装指南

## 系统要求
- Ubuntu 20.04+ 或其他 Linux 发行版
- Python 3.10
- 至少 8GB RAM
- 20GB+ 可用磁盘空间

## 1. 安装系统依赖

首先安装必要的系统依赖包：

```bash
# 更新包列表
sudo apt update

# 安装基础依赖
sudo apt install -y curl wget git build-essential

# 安装 X11 和 OpenGL 相关库 (ADFRsuite 需要)
sudo apt install -y libsm6 libxext6 libxrender-dev libgl1-mesa-glx libice6 libxt6 libxmu6 libxi6

# 安装 Python 2.7 相关库 (ADFRsuite 需要)
sudo apt install -y python2.7 python2.7-dev libpython2.7

# 安装 OpenMP 库
sudo apt install -y libgomp1

# 安装下载工具
sudo apt install -y axel aria2
```

## 2. 安装 Micromamba (如果尚未安装)

```bash
# 如果尚未安装 micromamba，先安装它
curl -Ls https://micro.mamba.pm/api/micromamba/linux-64/latest | tar -xvj bin/micromamba
sudo mv bin/micromamba /usr/local/bin/
rm -rf bin

# 初始化 micromamba
micromamba shell init -s bash
source ~/.bashrc
```

## 3. 创建 Micromamba 环境

```bash
# 创建新的 micromamba 环境
micromamba create -n peptide python=3.10 -y
micromamba activate peptide

# 安装基础 Python 包
micromamba install -y numpy scipy pandas biopython pymol-open-source
micromamba install -y -c conda-forge vina
```

## 3. 安装 OmegaFold

```bash
# 方法1: 从 GitHub 安装 (推荐)
pip install "git+https://github.com/HeliXonProtein/OmegaFold.git"

# 方法2: 如果没有 SSH 密钥配置，使用 HTTPS
# pip install "git+https://github.com/HeliXonProtein/OmegaFold.git"

# 下载 OmegaFold 模型文件
mkdir -p ~/.cache/omegafold_ckpt
wget -O ~/.cache/omegafold_ckpt/model2.pt https://helixon.s3.amazonaws.com/release2.pt

# 验证模型文件
ls -la ~/.cache/omegafold_ckpt/model2.pt
```

## 4. 安装 OmegaFold

```bash
# 方法1: 从 GitHub 安装 (推荐)
pip install "git+https://github.com/HeliXonProtein/OmegaFold.git"

# 方法2: 如果没有 SSH 密钥配置，使用 HTTPS
# pip install "git+https://github.com/HeliXonProtein/OmegaFold.git"

# 下载 OmegaFold 模型文件
mkdir -p ~/.cache/omegafold_ckpt
wget -O ~/.cache/omegafold_ckpt/model2.pt https://helixon.s3.amazonaws.com/release2.pt

# 验证模型文件
ls -la ~/.cache/omegafold_ckpt/model2.pt
```

## 5. 安装 ADFRsuite

```bash
# 下载 ADFRsuite
axel -n 10 -o ADFRsuite_Linux-x86_64_1.0.tar.gz "https://ccsb.scripps.edu/adfr/download/1038/"

# 解压和安装
tar zxvf ADFRsuite_Linux-x86_64_1.0.tar.gz
cd ADFRsuite_x86_64Linux_1.0
./install.sh -d ~/ADFRsuite-1.0 -c 0

# 添加到环境变量
echo 'export PATH=$HOME/ADFRsuite-1.0/bin:$PATH' >> ~/.bashrc
source ~/.bashrc

# 验证安装
which agfr
agfr --help
```

## 6. 安装 AutoDock Vina

```bash
# 通过 micromamba 安装 (推荐，包含命令行工具)
micromamba install -c conda-forge vina

# 或者通过 pip 安装
# pip install vina

# 验证安装
which vina
vina --help
```

## 7. 安装其他 Python 依赖

```bash
# 安装分子建模相关包
pip install meeko openbabel-wheel

# 安装机器学习相关包 (如果需要 ProteinMPNN)
pip install torch torchvision torchaudio

# 安装其他工具包
pip install prody mdanalysis
```

## 8. 验证安装

创建一个测试脚本来验证所有工具是否正常工作：

```bash
# 测试 OmegaFold
python -c "import omegafold; print('OmegaFold OK')"

# 测试 Vina
vina --version

# 测试 ADFRsuite
prepare_receptor --help > /dev/null && echo "ADFRsuite OK"

# 测试 PyMOL
python -c "import pymol; print('PyMOL OK')"

# 测试 BioPython
python -c "from Bio.PDB import PDBParser; print('BioPython OK')"
```

## 9. 可选：安装 ProteinMPNN

如果需要使用 ProteinMPNN 进行序列优化：

```bash
# 克隆 ProteinMPNN 仓库
git clone https://github.com/dauparas/ProteinMPNN.git
cd ProteinMPNN

# 安装依赖
pip install torch
```

## 故障排除

### OmegaFold 模型下载问题
如果模型下载失败或放在错误位置：
```bash
# 确保模型在正确位置
mv ~/.cache/omegafold_ckpt/home/davis/.cache/omegafold_ckpt/model2.pt ~/.cache/omegafold_ckpt/ 2>/dev/null || true
rm -rf ~/.cache/omegafold_ckpt/home/ 2>/dev/null || true
```

### ADFRsuite 依赖问题
如果遇到 "libSM.so.6: cannot open shared object file" 错误：
```bash
sudo apt install -y libsm6 libxext6 libxrender-dev libgl1-mesa-glx
```

### Vina 搜索空间问题
使用 `--autobox` 参数进行自动搜索空间设置：
```bash
vina --ligand ligand.pdbqt --receptor receptor.pdbqt --score_only --autobox
```

## 使用说明

1. 确保所有依赖都已正确安装
2. 激活 micromamba 环境：`micromamba activate peptide`
3. 运行 peptide optimizer：`python peptide_optimizer.py`