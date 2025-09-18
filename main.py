#!/usr/bin/env python3
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)
