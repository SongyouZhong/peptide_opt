#!/usr/bin/env python3
"""
CLI 工具 - 命令行直接运行肽段优化
"""

import sys
from pathlib import Path


def run_optimizer(
    input_dir: str = "./data/input",
    output_dir: str = "./data/output",
    cores: int = 12,
    step: int = None,
    cleanup: bool = True,
    n_poses: int = 10,
    num_seq_per_target: int = 10,
    proteinmpnn_seed: int = 37,
):
    """运行肽段优化流程"""
    from peptide_opt.core.optimizer import PeptideOptimizer
    
    print("=== 肽段优化流程 ===")
    print("开始运行肽段优化流程...")
    
    input_path = Path(input_dir)
    if not input_path.exists():
        print(f"错误: 输入目录不存在: {input_dir}")
        sys.exit(1)
    
    # 检查必要的输入文件
    peptide_fasta = input_path / "peptide.fasta"
    if not peptide_fasta.exists():
        print(f"错误: 找不到肽段序列文件 {peptide_fasta}")
        sys.exit(1)
    
    # 自动检测受体 PDB 文件
    pdb_files = list(input_path.glob("*.pdb")) + list(input_path.glob("*.pdbqt"))
    if not pdb_files:
        print(f"错误: 在 {input_dir} 中找不到受体蛋白质结构文件 (.pdb 或 .pdbqt)")
        sys.exit(1)
    
    receptor_file = pdb_files[0]
    print(f"使用受体文件: {receptor_file.name}")
    
    # 查找 ProteinMPNN 目录
    proteinmpnn_dir = _find_proteinmpnn_dir()
    
    # 创建优化器实例
    optimizer = PeptideOptimizer(
        input_dir=str(input_path),
        output_dir=output_dir,
        proteinmpnn_dir=str(proteinmpnn_dir),
        cores=cores,
        cleanup=cleanup,
        n_poses=n_poses,
        num_seq_per_target=num_seq_per_target,
        proteinmpnn_seed=proteinmpnn_seed,
        receptor_pdb_filename=receptor_file.name
    )
    
    try:
        if step:
            # 运行特定步骤
            print(f"运行步骤 {step}...")
            optimizer.run_step(step)
        else:
            # 运行完整流程
            optimizer.run_full_pipeline()
        
        print("\n=== 优化流程完成 ===")
        print(f"结果保存在: {output_dir}")
        
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def _find_proteinmpnn_dir() -> Path:
    """查找 ProteinMPNN 目录"""
    # 按优先级查找
    search_paths = [
        Path(__file__).parent.parent.parent.parent / "vendor" / "ProteinMPNN",  # src/../vendor/
        Path(__file__).parent.parent.parent.parent / "ProteinMPNN",  # 项目根目录
        Path.cwd() / "ProteinMPNN",  # 当前工作目录
        Path.cwd() / "vendor" / "ProteinMPNN",
    ]
    
    for path in search_paths:
        if path.exists() and (path / "protein_mpnn_run.py").exists():
            return path.resolve()
    
    # 默认返回项目根目录下的路径
    return Path(__file__).parent.parent.parent.parent / "vendor" / "ProteinMPNN"


if __name__ == "__main__":
    run_optimizer()
