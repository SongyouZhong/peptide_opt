#!/usr/bin/env python3
"""
FastAPI wrapper for Peptide Optimization Pipeline
"""

import os
import sys
import shutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Form

# Add current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from peptide_optimizer import PeptideOptimizer
except ImportError as e:
    print(f"Error importing PeptideOptimizer: {e}")
    print("Please make sure all dependencies are installed in your conda environment")
    sys.exit(1)

app = FastAPI(
    title="Peptide Optimization API",
    description="API for peptide optimization pipeline including structure prediction, docking, and sequence optimization",
    version="1.0.0"
)

def validate_file_exists(file_path: str, file_type: str) -> str:
    """验证文件是否存在"""
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=400, 
            detail=f"{file_type} file not found: {file_path}"
        )
    return file_path

def validate_fasta_file(file_path: str) -> str:
    """验证FASTA文件格式"""
    validate_file_exists(file_path, "FASTA")
    
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
            if not content.startswith('>'):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid FASTA format: file should start with '>'"
                )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error reading FASTA file: {str(e)}"
        )
    
    return file_path

def validate_pdb_file(file_path: str) -> str:
    """验证PDB文件格式"""
    validate_file_exists(file_path, "PDB")
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            if not any(line.startswith(('ATOM', 'HETATM')) for line in content.split('\n')):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid PDB format: no ATOM or HETATM records found"
                )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error reading PDB file: {str(e)}"
        )
    
    return file_path

@app.post("/optimize")
async def optimize(
    pdb_file_path: str = Form(..., description="Path to PDB file"),
    fasta_file_path: str = Form(..., description="Path to FASTA file"),
    output_path: str = Form(..., description="Output directory path"),
    cores: int = Form(12, description="Number of CPU cores"),
    cleanup: bool = Form(True, description="Clean up intermediate files")
):
    """
    执行肽段优化任务
    
    - **pdb_file_path**: PDB结构文件路径
    - **fasta_file_path**: FASTA序列文件路径  
    - **output_path**: 结果输出目录路径
    - **cores**: CPU核心数 (默认: 12)
    - **cleanup**: 是否清理中间文件 (默认: True)
    """
    
    try:
        # 验证输入文件
        validate_pdb_file(pdb_file_path)
        validate_fasta_file(fasta_file_path)
        
        # 创建临时工作目录
        work_dir = Path(f"./work/temp_{os.getpid()}")
        work_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 创建输入目录并复制文件
            input_dir = work_dir / "input"
            input_dir.mkdir(exist_ok=True)
            
            # 复制输入文件到工作目录
            shutil.copy2(pdb_file_path, input_dir / "5ffg.pdb")
            shutil.copy2(fasta_file_path, input_dir / "peptide.fasta")
            
            # 设置输出目录
            output_dir = work_dir / "output"
            output_dir.mkdir(exist_ok=True)
            
            # 创建优化器实例
            optimizer = PeptideOptimizer(
                input_dir=str(input_dir),
                output_dir=str(output_dir),
                proteinmpnn_dir="./ProteinMPNN/",
                cores=cores,
                cleanup=cleanup
            )
            
            # 运行优化流程
            optimizer.run_full_pipeline()
            
            # 将结果复制到用户指定的输出路径
            final_output_dir = Path(output_path)
            final_output_dir.mkdir(parents=True, exist_ok=True)
            
            # 复制结果文件
            result_files = []
            for file in output_dir.glob("*"):
                if file.is_file():
                    target_file = final_output_dir / file.name
                    shutil.copy2(file, target_file)
                    result_files.append(str(target_file))
            
            return {
                "status": "success",
                "message": "Optimization completed successfully",
                "output_path": output_path,
                "result_files": result_files
            }
            
        finally:
            # 清理工作目录
            if cleanup and work_dir.exists():
                shutil.rmtree(work_dir, ignore_errors=True)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Optimization failed: {str(e)}")

@app.get("/")
async def root():
    """API根路径"""
    return {
        "message": "Peptide Optimization API",
        "version": "1.0.0",
        "endpoints": {
            "/optimize": "POST - Execute optimization task"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
