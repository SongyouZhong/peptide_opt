#!/usr/bin/env python3
"""
Simple runner script for the peptide optimizer
简化的运行脚本
"""

import sys
import os
from pathlib import Path

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from peptide_optimizer import PeptideOptimizer
except ImportError as e:
    print(f"Error importing PeptideOptimizer: {e}")
    print("Please make sure all dependencies are installed in your conda environment")
    sys.exit(1)

def main():
    """简化的主函数"""
    print("=== 肽段优化流程 ===")
    print("开始运行完整的肽段优化流程...")
    
    # 检查必要的输入文件
    input_dir = Path("./input")
    if not input_dir.exists():
        print("错误: input 目录不存在")
        sys.exit(1)

    peptide_fasta = input_dir / "peptide.fasta"

    if not peptide_fasta.exists():
        print(f"错误: 找不到肽段序列文件 {peptide_fasta}")
        sys.exit(1)

    # 自动检测受体PDB文件
    pdb_files = list(input_dir.glob("*.pdb")) + list(input_dir.glob("*.pdbqt"))
    if not pdb_files:
        print(f"错误: 在 {input_dir} 中找不到受体蛋白质结构文件 (.pdb 或 .pdbqt)")
        sys.exit(1)

    protein_pdb = pdb_files[0]
    print(f"使用受体文件: {protein_pdb.name}")
    
    # 创建优化器实例（会自动检测受体文件名）
    optimizer = PeptideOptimizer(cleanup=True, receptor_pdb_filename=protein_pdb.name)
    
    try:
        # 运行完整流程
        optimizer.run_full_pipeline()
        print("\n=== 流程完成 ===")
        print("结果文件保存在 ./output/ 目录中")
        print("- result.csv: 详细的分析报告")
        print("- complex1.pdb - complex10.pdb: 优化后的复合物结构")
        print("- 中间文件已自动清理")
        
    except Exception as e:
        print(f"流程执行失败: {e}")
        print("中间文件保留在 ./middlefiles/ 目录中用于调试")
        sys.exit(1)

if __name__ == "__main__":
    main()
