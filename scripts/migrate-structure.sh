#!/bin/bash
# ===========================================
# 项目结构迁移脚本
# ===========================================
# 此脚本将旧文件结构迁移到新结构
# 运行前请确保已备份重要文件

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=========================================="
echo "Peptide Optimization - 项目结构迁移"
echo "=========================================="
echo ""

# 创建必要目录
echo "1. 创建目录结构..."
mkdir -p vendor
mkdir -p data/input
mkdir -p data/output

# 创建 .gitkeep 文件
touch data/input/.gitkeep
touch data/output/.gitkeep

# 移动 ProteinMPNN 到 vendor
if [ -d "ProteinMPNN" ] && [ ! -d "vendor/ProteinMPNN" ]; then
    echo "2. 移动 ProteinMPNN 到 vendor/..."
    mv ProteinMPNN vendor/
elif [ -d "vendor/ProteinMPNN" ]; then
    echo "2. ProteinMPNN 已在 vendor/ 目录中"
else
    echo "2. 警告: 未找到 ProteinMPNN 目录"
fi

# 移动输入文件
if [ -d "input" ] && [ "$(ls -A input 2>/dev/null)" ]; then
    echo "3. 移动输入文件到 data/input/..."
    cp -r input/* data/input/ 2>/dev/null || true
else
    echo "3. 跳过输入文件移动 (目录为空或不存在)"
fi

echo ""
echo "=========================================="
echo "迁移完成!"
echo "=========================================="
echo ""
echo "下一步操作:"
echo "1. 安装新包: pip install -e '.[dev]'"
echo "2. 测试: pytest"
echo "3. 启动服务: peptide-opt serve"
echo ""
echo "详细说明请参考: docs/RESTRUCTURE.md"
