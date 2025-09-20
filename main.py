#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI wrapper for Peptide Optimization Pipeline
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.logging_config import setup_logging, get_log_file_path
from async_task_processor import AsyncTaskProcessor

# 设置日志系统
log_file = get_log_file_path()
setup_logging(level="INFO", log_file=log_file)
logger = logging.getLogger(__name__)

# 全局异步任务处理器
async_processor = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # —— 应用启动时执行 —— 
    global async_processor
    
    logger.info("Starting Peptide Optimization API...")
    
    # 初始化异步任务处理器
    logger.info("Initializing async task processor...")
    async_processor = AsyncTaskProcessor()
    
    # 启动数据库轮询
    logger.info("Starting database polling for peptide optimization tasks...")
    await async_processor.start_polling()
    
    logger.info("Peptide Optimization API startup complete")
    yield
    
    # —— 应用关闭时执行 ——
    logger.info("Shutting down Peptide Optimization API...")
    if async_processor:
        await async_processor.shutdown()
    logger.info("Peptide Optimization API shutdown complete")

app = FastAPI(
    lifespan=lifespan,
    title="Peptide Optimization API", 
    description="Peptide structure optimization and sequence design service using ProteinMPNN and molecular docking.",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 异常处理器
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.error(f"Validation error: {exc}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP error: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unexpected error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# 基本路由
@app.get("/")
async def root():
    """API根路径"""
    return {
        "message": "Peptide Optimization API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "active_tasks": async_processor.get_task_count() if async_processor else 0
    }

@app.get("/status")
async def status():
    """获取服务状态"""
    if not async_processor:
        return {"status": "initializing"}
    
    return {
        "status": "running",
        "active_tasks": async_processor.get_task_count(),
        "active_task_ids": async_processor.get_active_tasks()
    }

# 进度监控API
@app.get("/tasks/progress")
async def get_all_tasks_progress():
    """获取所有活动任务的进度"""
    if not async_processor:
        return {"error": "Task processor not initialized"}
    
    tasks_progress = async_processor.get_all_tasks_progress()
    
    return {
        "active_tasks": len(tasks_progress),
        "tasks": tasks_progress
    }

@app.get("/tasks/{task_id}/progress")
async def get_task_progress(task_id: str):
    """获取特定任务的详细进度"""
    if not async_processor:
        return {"error": "Task processor not initialized"}
    
    progress_info = async_processor.get_task_progress(task_id)
    
    if not progress_info:
        return {"error": "Task not found or no progress information available"}
    
    return {
        "task_id": task_id,
        **progress_info
    }

@app.get("/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """获取特定任务的详细状态"""
    if not async_processor:
        return {"error": "Service not initialized"}
    
    # 检查任务是否在活动列表中
    if task_id in async_processor.get_active_tasks():
        # 从数据库获取最新状态
        try:
            connection = await async_processor.get_db_connection()
            if connection:
                try:
                    async with connection.cursor() as cursor:
                        await cursor.execute(
                            "SELECT id, status, created_at, updated_at FROM tasks WHERE id = %s",
                            (task_id,)
                        )
                        result = await cursor.fetchone()
                        if result:
                            return {
                                "task_id": result[0],
                                "status": result[1],
                                "created_at": result[2].isoformat() if result[2] else None,
                                "updated_at": result[3].isoformat() if result[3] else None,
                                "is_active": True
                            }
                finally:
                    connection.close()
        except Exception as e:
            logger.error(f"Error fetching task status: {e}")
            return {"error": "Database error"}
    
    return {"task_id": task_id, "status": "not_found", "is_active": False}

@app.get("/tasks/{task_id}/peptide/download/{filename}")
async def download_peptide_file(task_id: str, filename: str):
    """下载肽优化任务的输出文件（PDB等）
    此API端点用于获取肽优化任务的结果文件，主要用于3D显示
    """
    from fastapi.responses import FileResponse
    import os
    import re
    import mimetypes
    from fastapi import HTTPException, Response
    
    logger.info(f"接收到文件下载请求: task_id={task_id}, filename={filename}")
    
    # 安全检查：验证文件名，防止目录遍历攻击
    if not re.match(r'^[\w\-. ]+$', filename):
        logger.warning(f"请求的文件名无效: {filename}")
        raise HTTPException(status_code=400, detail=f"Invalid filename: {filename}")
    
    # 检查async_processor是否已初始化
    if not async_processor:
        logger.error("服务未初始化，无法处理文件下载请求")
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # 检查任务状态
    connection = await async_processor.get_db_connection()
    if not connection:
        logger.error("无法连接到数据库，无法处理文件下载请求")
        raise HTTPException(status_code=500, detail="Database connection failed")
        
    try:
        # 获取任务目录
        async with connection.cursor() as cursor:
            # 获取任务详细信息
            await cursor.execute(
                """
                SELECT job_dir, status 
                FROM tasks 
                WHERE id = %s AND task_type = 'peptide_optimization'
                """,
                (task_id,)
            )
            result = await cursor.fetchone()
            
            if not result:
                logger.warning(f"找不到任务: {task_id}")
                raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
                
            job_dir, task_status = result
            logger.info(f"找到任务: {task_id}, 任务目录: {job_dir}, 状态: {task_status}")
            
            # 构建所有可能的文件路径
            file_paths = [
                # 主要输出目录路径
                os.path.join(job_dir, "output", filename),  # 直接在output目录
                os.path.join(job_dir, "output", "complexes", filename),  # complexes子目录
                os.path.join(job_dir, "output", "complex", filename),  # complex子目录 (单数形式)
                os.path.join(job_dir, "output", "pdb", filename),  # pdb子目录
                os.path.join(job_dir, "output", "pdbs", filename),  # pdbs子目录
                
                # 中间文件路径
                os.path.join(job_dir, "middlefiles", filename),  # 中间文件目录
                os.path.join(job_dir, "middlefiles", "pdb", filename),  # 中间文件的pdb子目录
                
                # 输入文件路径 (有时结果文件会被复制到这里)
                os.path.join(job_dir, "input", filename),  # 输入目录
                
                # 根目录
                os.path.join(job_dir, filename),  # 直接在任务根目录
            ]
            
            # 详细记录搜索路径
            logger.debug(f"搜索文件 {filename} 的路径列表:")
            for i, path in enumerate(file_paths):
                logger.debug(f"  [{i+1}] {path}")
            
            # 检查文件是否存在
            found_file = None
            for file_path in file_paths:
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    found_file = file_path
                    logger.info(f"找到文件: {file_path}")
                    break
            
            if not found_file:
                # 尝试额外的目录扫描
                logger.debug(f"在预定义路径中未找到文件，尝试扩展搜索...")
                
                # 递归扫描所有可能的子目录 (最多2级)
                for base_dir in [os.path.join(job_dir, "output"), os.path.join(job_dir, "middlefiles")]:
                    if os.path.exists(base_dir) and os.path.isdir(base_dir):
                        # 扫描第一级子目录
                        for subdir in os.listdir(base_dir):
                            subdir_path = os.path.join(base_dir, subdir)
                            if os.path.isdir(subdir_path):
                                # 检查第一级
                                test_path = os.path.join(subdir_path, filename)
                                if os.path.exists(test_path) and os.path.isfile(test_path):
                                    found_file = test_path
                                    logger.info(f"在扩展搜索中找到文件: {test_path}")
                                    break
                                
                                # 检查第二级子目录
                                for subsubdir in os.listdir(subdir_path):
                                    subsubdir_path = os.path.join(subdir_path, subsubdir)
                                    if os.path.isdir(subsubdir_path):
                                        test_path = os.path.join(subsubdir_path, filename)
                                        if os.path.exists(test_path) and os.path.isfile(test_path):
                                            found_file = test_path
                                            logger.info(f"在第二级扩展搜索中找到文件: {test_path}")
                                            break
                            if found_file:
                                break
                    if found_file:
                        break
            
            if found_file:
                # 确定适当的MIME类型
                mime_type = None
                if filename.lower().endswith('.pdb'):
                    mime_type = 'chemical/x-pdb'
                elif filename.lower().endswith('.sdf'):
                    mime_type = 'chemical/x-mdl-sdfile'
                elif filename.lower().endswith('.mol'):
                    mime_type = 'chemical/x-mdl-molfile'
                elif filename.lower().endswith('.mol2'):
                    mime_type = 'chemical/x-mol2'
                else:
                    mime_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                
                logger.info(f"提供文件: {found_file} (MIME类型: {mime_type})")
                
                # 记录文件大小
                file_size = os.path.getsize(found_file)
                logger.info(f"文件大小: {file_size} bytes")
                
                # 返回文件响应
                return FileResponse(
                    path=found_file,
                    filename=filename,
                    media_type=mime_type
                )
            
            # 如果所有路径都不存在，返回404
            logger.warning(f"找不到文件: {filename} (任务ID: {task_id})")
            # 列出任务目录内容以便调试
            if os.path.exists(job_dir):
                output_dir = os.path.join(job_dir, "output")
                if os.path.exists(output_dir) and os.path.isdir(output_dir):
                    logger.debug(f"输出目录内容 ({output_dir}):")
                    for item in os.listdir(output_dir):
                        item_path = os.path.join(output_dir, item)
                        if os.path.isdir(item_path):
                            logger.debug(f"  目录: {item}/")
                            # 列出子目录的内容
                            try:
                                for subitem in os.listdir(item_path):
                                    logger.debug(f"    - {item}/{subitem}")
                            except Exception as e:
                                logger.debug(f"    无法列出子目录内容: {str(e)}")
                        else:
                            logger.debug(f"  文件: {item}")
                else:
                    logger.debug(f"输出目录不存在: {output_dir}")
            
            raise HTTPException(
                status_code=404, 
                detail=f"File {filename} not found for task {task_id}. Please ensure the file exists and the task has completed successfully."
            )
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        logger.error(f"提供文件时出错 {filename} (任务ID: {task_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")
    finally:
        # 确保关闭数据库连接
        if connection:
            connection.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)
