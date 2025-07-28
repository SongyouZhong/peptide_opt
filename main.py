#!/usr/bin/env python3
"""
FastAPI wrapper for Peptide Optimization Pipeline
"""

import os
import sys
import uuid
import shutil
import asyncio
from pathlib import Path
from typing import Optional
import traceback
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pandas as pd

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

# 全局任务状态存储
task_status = {}

class OptimizationRequest(BaseModel):
    pdb_file_path: str
    fasta_file_path: str
    output_path: str
    user_id: str
    cores: Optional[int] = 12
    cleanup: Optional[bool] = True

class TaskStatus(BaseModel):
    task_id: str
    user_id: str
    status: str  # "pending", "running", "completed", "failed"
    message: str
    created_at: str
    completed_at: Optional[str] = None
    output_path: Optional[str] = None
    error_message: Optional[str] = None

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

async def run_optimization_task(task_id: str, request: OptimizationRequest):
    """异步运行优化任务"""
    try:
        # 更新任务状态为运行中
        task_status[task_id]["status"] = "running"
        task_status[task_id]["message"] = "Optimization pipeline is running..."
        
        # 创建用户特定的工作目录
        user_work_dir = Path(f"./work/{request.user_id}_{task_id}")
        user_work_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建输入目录并复制文件
        input_dir = user_work_dir / "input"
        input_dir.mkdir(exist_ok=True)
        
        # 复制输入文件到工作目录
        shutil.copy2(request.pdb_file_path, input_dir / "5ffg.pdb")
        shutil.copy2(request.fasta_file_path, input_dir / "peptide.fasta")
        
        # 设置输出目录
        output_dir = user_work_dir / "output"
        output_dir.mkdir(exist_ok=True)
        
        # 创建优化器实例
        optimizer = PeptideOptimizer(
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            proteinmpnn_dir="./ProteinMPNN/",
            cores=request.cores,
            cleanup=request.cleanup
        )
        
        # 运行优化流程
        optimizer.run_full_pipeline()
        
        # 将结果复制到用户指定的输出路径
        final_output_dir = Path(request.output_path)
        final_output_dir.mkdir(parents=True, exist_ok=True)
        
        # 复制结果文件
        for file in output_dir.glob("*"):
            if file.is_file():
                shutil.copy2(file, final_output_dir / file.name)
        
        # 更新任务状态为完成
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["message"] = "Optimization completed successfully"
        task_status[task_id]["completed_at"] = datetime.now().isoformat()
        task_status[task_id]["output_path"] = request.output_path
        
        # 清理工作目录（如果需要）
        if request.cleanup:
            shutil.rmtree(user_work_dir, ignore_errors=True)
            
    except Exception as e:
        # 更新任务状态为失败
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["message"] = "Optimization failed"
        task_status[task_id]["error_message"] = str(e)
        task_status[task_id]["completed_at"] = datetime.now().isoformat()
        
        # 记录详细错误信息
        print(f"Task {task_id} failed with error: {str(e)}")
        print(f"Traceback: {traceback.format_exc()}")

@app.get("/")
async def root():
    """API根路径"""
    return {
        "message": "Peptide Optimization API",
        "version": "1.0.0",
        "endpoints": {
            "/optimize": "POST - Start optimization task",
            "/status/{task_id}": "GET - Check task status",
            "/health": "GET - Health check"
        }
    }

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/optimize", response_model=dict)
async def start_optimization(
    background_tasks: BackgroundTasks,
    pdb_file_path: str = Form(..., description="Path to PDB file"),
    fasta_file_path: str = Form(..., description="Path to FASTA file"),
    output_path: str = Form(..., description="Output directory path"),
    user_id: str = Form(..., description="User ID"),
    cores: int = Form(12, description="Number of CPU cores"),
    cleanup: bool = Form(True, description="Clean up intermediate files")
):
    """
    启动肽段优化任务
    
    - **pdb_file_path**: PDB结构文件路径
    - **fasta_file_path**: FASTA序列文件路径  
    - **output_path**: 结果输出目录路径
    - **user_id**: 用户ID
    - **cores**: CPU核心数 (默认: 12)
    - **cleanup**: 是否清理中间文件 (默认: True)
    """
    
    try:
        # 验证输入文件
        validate_pdb_file(pdb_file_path)
        validate_fasta_file(fasta_file_path)
        
        # 创建请求对象
        request = OptimizationRequest(
            pdb_file_path=pdb_file_path,
            fasta_file_path=fasta_file_path,
            output_path=output_path,
            user_id=user_id,
            cores=cores,
            cleanup=cleanup
        )
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 初始化任务状态
        task_status[task_id] = {
            "task_id": task_id,
            "user_id": user_id,
            "status": "pending",
            "message": "Task created, waiting to start...",
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
            "output_path": None,
            "error_message": None
        }
        
        # 添加后台任务
        background_tasks.add_task(run_optimization_task, task_id, request)
        
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "Optimization task started",
            "user_id": user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/status/{task_id}", response_model=TaskStatus)
async def get_task_status(task_id: str):
    """
    获取任务状态
    
    - **task_id**: 任务ID
    """
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskStatus(**task_status[task_id])

@app.get("/user/{user_id}/tasks")
async def get_user_tasks(user_id: str):
    """
    获取用户的所有任务
    
    - **user_id**: 用户ID
    """
    user_tasks = [
        TaskStatus(**task_data) 
        for task_data in task_status.values() 
        if task_data["user_id"] == user_id
    ]
    
    return {
        "user_id": user_id,
        "total_tasks": len(user_tasks),
        "tasks": user_tasks
    }

@app.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """
    删除任务记录
    
    - **task_id**: 任务ID
    """
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # 只能删除已完成或失败的任务
    if task_status[task_id]["status"] in ["running", "pending"]:
        raise HTTPException(status_code=400, detail="Cannot delete running or pending task")
    
    del task_status[task_id]
    return {"message": "Task deleted successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
