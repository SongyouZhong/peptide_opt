#!/usr/bin/env python3
"""
FastAPI wrapper for Peptide Optimization Pipeline
"""

import os
import sys
import shutil
import asyncio
import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Form
import aiomysql
from contextlib import asynccontextmanager

from peptide_optimizer import PeptideOptimizer
from utils import validate_fasta_file, validate_pdb_file

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 数据库配置
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'vina_user',
    'password': 'Aa7758258123',
    'db': 'project1',
    'charset': 'utf8mb4',
    'autocommit': True
}

# 全局变量用于控制定时任务
background_task = None

async def get_db_connection():
    """获取数据库连接"""
    try:
        connection = await aiomysql.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None

async def query_tasks():
    """查询tasks表中的待处理任务"""
    connection = await get_db_connection()
    if not connection:
        return
    
    try:
        async with connection.cursor() as cursor:
            # 查询状态为pending的任务
            await cursor.execute(
                "SELECT id, user_id, task_type, job_dir, status FROM tasks WHERE status = %s",
                ('pending',)
            )
            tasks = await cursor.fetchall()
            
            if tasks:
                logger.info(f"发现 {len(tasks)} 个待处理任务")
                for task in tasks:
                    task_id, user_id, task_type, job_dir, status = task
                    logger.info(f"任务ID: {task_id}, 用户ID: {user_id}, 类型: {task_type}, 状态: {status}")
                    
                    # 这里可以添加具体的任务处理逻辑
                    # 例如：更新任务状态为processing
                    await cursor.execute(
                        "UPDATE tasks SET status = %s, started_at = NOW() WHERE id = %s",
                        ('processing', task_id)
                    )
                    logger.info(f"任务 {task_id} 状态已更新为processing")
            else:
                logger.info("没有发现待处理任务")
                
    except Exception as e:
        logger.error(f"查询任务时发生错误: {e}")
    finally:
        connection.close()

async def background_task_runner():
    """后台定时任务运行器"""
    logger.info("定时任务启动，每30秒查询一次tasks表")
    while True:
        try:
            await query_tasks()
            await asyncio.sleep(30)  # 等待30秒
        except Exception as e:
            logger.error(f"定时任务执行错误: {e}")
            await asyncio.sleep(30)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global background_task
    
    # 启动时执行
    logger.info("启动FastAPI应用...")
    background_task = asyncio.create_task(background_task_runner())
    
    yield
    
    # 关闭时执行
    logger.info("关闭FastAPI应用...")
    if background_task:
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            logger.info("定时任务已停止")


app = FastAPI(
    title="Peptide Optimization API",
    description="API for peptide optimization pipeline including structure prediction, docking, and sequence optimization",
    version="1.0.0",
    lifespan=lifespan
)

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

@app.get("/tasks/check")
async def check_tasks():
    """
    手动检查数据库中的任务状态
    """
    connection = await get_db_connection()
    if not connection:
        raise HTTPException(status_code=500, detail="数据库连接失败")
    
    try:
        async with connection.cursor() as cursor:
            # 查询所有任务
            await cursor.execute(
                "SELECT id, user_id, task_type, job_dir, status, created_at FROM tasks ORDER BY created_at DESC LIMIT 10"
            )
            tasks = await cursor.fetchall()
            
            task_list = []
            for task in tasks:
                task_id, user_id, task_type, job_dir, status, created_at = task
                task_list.append({
                    "id": task_id,
                    "user_id": user_id,
                    "task_type": task_type,
                    "job_dir": job_dir,
                    "status": status,
                    "created_at": str(created_at)
                })
            
            return {
                "status": "success",
                "task_count": len(task_list),
                "tasks": task_list
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查询任务失败: {str(e)}")
    finally:
        connection.close()

@app.get("/health")
async def health_check():
    """
    健康检查端点
    """
    return {"status": "healthy", "message": "Peptide Optimization API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
