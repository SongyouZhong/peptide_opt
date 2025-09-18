"""
肽段优化异步任务处理器
支持并发处理和进度更新
"""

import asyncio
import logging
import json
import time
import os
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import aiomysql
from peptide_optimizer import PeptideOptimizer
from utils import validate_fasta_file, validate_pdb_file

logger = logging.getLogger("async_task_processor")


class TaskProgressCallback:
    """任务进度回调类"""
    
    def __init__(self, task_id: str, connection):
        self.task_id = task_id
        self.connection = connection
        self._is_completed = False
        
    async def update_progress(self, progress: float, info: str = None):
        """更新任务进度"""
        if self._is_completed:
            logger.debug("Task %s already completed, skipping progress update", self.task_id)
            return
            
        try:
            # 更新数据库中的任务状态 - 只更新状态，不包含progress和info字段
            async with self.connection.cursor() as cursor:
                await cursor.execute(
                    "UPDATE tasks SET status = %s WHERE id = %s",
                    ("processing", self.task_id)
                )
                await self.connection.commit()
                
            logger.info("Task %s progress: %.1f%% - %s", 
                        self.task_id, progress, info or "")
        except Exception as e:
            logger.error("Failed to update progress for task %s: %s", self.task_id, e)
    
    def mark_completed(self):
        """标记任务为已完成"""
        self._is_completed = True


class AsyncTaskProcessor:
    """异步任务处理器"""
    
    def __init__(self, max_workers: int = 2):
        self.max_workers = max_workers
        self.thread_executor = ThreadPoolExecutor(max_workers=max_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=max_workers)
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.is_running = True
        self.polling_task = None
        
        # 数据库配置
        self.db_config = {
            'host': '127.0.0.1',
            'user': 'vina_user',
            'password': 'Aa7758258123',
            'db': 'project1',
            'charset': 'utf8mb4',
            'autocommit': True
        }
        
        logger.info("AsyncTaskProcessor initialized with %d workers", max_workers)
    
    async def start_polling(self):
        """启动数据库轮询"""
        if self.polling_task is None:
            logger.info("Starting database polling for peptide optimization tasks...")
            self.polling_task = asyncio.create_task(self._poll_database_tasks())
    
    async def _poll_database_tasks(self):
        """定时从数据库获取待处理的peptide优化任务"""
        while self.is_running:
            try:
                connection = await self.get_db_connection()
                if connection:
                    try:
                        async with connection.cursor() as cursor:
                            # 查询状态为pending的peptide_optimization任务
                            await cursor.execute(
                                "SELECT id, job_dir FROM tasks WHERE task_type = 'peptide_optimization' AND status = 'pending' LIMIT 5"
                            )
                            pending_tasks = await cursor.fetchall()
                            
                            if pending_tasks:
                                logger.info(f"Found {len(pending_tasks)} pending peptide optimization tasks")
                                
                            for task in pending_tasks:
                                task_id, job_dir = task
                                # 检查任务是否已在处理中
                                if task_id not in self.active_tasks:
                                    logger.info(f"Submitting peptide optimization task: {task_id}")
                                    await self.submit_task(task_id, job_dir)
                                else:
                                    logger.debug(f"Task {task_id} already in progress, skipping")
                    finally:
                        connection.close()
                        
            except Exception as e:
                logger.error(f"Error polling database for tasks: {e}")
            
            # 等待30秒后再次轮询
            await asyncio.sleep(30)
        
        logger.info("Database polling stopped")
    
    async def get_db_connection(self):
        """获取数据库连接"""
        try:
            connection = await aiomysql.connect(**self.db_config)
            return connection
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return None
    
    async def process_peptide_optimization_task(self, task_id: str, job_dir: str):
        """处理肽段优化任务"""
        connection = None
        try:
            # 获取数据库连接
            connection = await self.get_db_connection()
            if not connection:
                raise Exception("Failed to connect to database")
            
            # 创建进度回调
            progress_callback = TaskProgressCallback(task_id, connection)
            
            # 更新任务状态为处理中
            await progress_callback.update_progress(0, "Starting peptide optimization")
            
            # 保存当前工作目录
            original_cwd = os.getcwd()
            
            try:
                # 切换到任务目录
                os.chdir(job_dir)
                
                # 检查必要文件 - 文件在input子目录中
                input_dir = os.path.join(job_dir, "input")
                fasta_file = os.path.join(input_dir, "peptide.fasta")
                pdb_file = os.path.join(input_dir, "5ffg.pdb")
                
                if not os.path.exists(fasta_file):
                    raise FileNotFoundError(f"FASTA file not found: {fasta_file}")
                if not os.path.exists(pdb_file):
                    raise FileNotFoundError(f"PDB file not found: {pdb_file}")
                
                # 验证文件格式
                await progress_callback.update_progress(10, "Validating input files")
                if not validate_fasta_file(fasta_file):
                    raise ValueError("Invalid FASTA file format")
                if not validate_pdb_file(pdb_file):
                    raise ValueError("Invalid PDB file format")
                
                # 创建优化器 - 传递目录路径而不是文件路径
                await progress_callback.update_progress(20, "Initializing optimizer")
                optimizer = PeptideOptimizer(
                    input_dir=input_dir,
                    output_dir=os.path.join(job_dir, "output"),
                    cores=12,  # 可以从配置文件读取
                    cleanup=True
                )
                
                # 执行优化步骤
                await progress_callback.update_progress(30, "Running peptide optimization")
                result = await asyncio.get_event_loop().run_in_executor(
                    self.thread_executor, 
                    optimizer.run_full_pipeline
                )
                
                await progress_callback.update_progress(90, "Finalizing results")
                
                # 更新数据库为完成状态
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        """UPDATE tasks 
                           SET status = %s 
                           WHERE id = %s""",
                        ("finished", task_id)
                    )
                    await connection.commit()
                
                progress_callback.mark_completed()
                logger.info("Task %s completed successfully", task_id)
                
            finally:
                # 恢复原始工作目录
                os.chdir(original_cwd)
                
        except Exception as e:
            logger.error("Task %s failed: %s", task_id, str(e))
            
            if connection:
                try:
                    async with connection.cursor() as cursor:
                        await cursor.execute(
                            "UPDATE tasks SET status = %s WHERE id = %s",
                            ("failed", task_id)
                        )
                        await connection.commit()
                except Exception as db_error:
                    logger.error("Failed to update task status in database: %s", db_error)
        
        finally:
            if connection:
                connection.close()
            
            # 从活动任务中移除
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]
    
    async def submit_task(self, task_id: str, job_dir: str) -> bool:
        """提交新任务"""
        if not self.is_running:
            logger.warning("TaskProcessor is not running, cannot submit task %s", task_id)
            return False
        
        if task_id in self.active_tasks:
            logger.warning("Task %s is already running", task_id)
            return False
        
        try:
            # 创建并启动任务
            task = asyncio.create_task(
                self.process_peptide_optimization_task(task_id, job_dir)
            )
            self.active_tasks[task_id] = task
            
            logger.info("Task %s submitted successfully", task_id)
            return True
            
        except Exception as e:
            logger.error("Failed to submit task %s: %s", task_id, e)
            return False
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id not in self.active_tasks:
            logger.warning("Task %s not found in active tasks", task_id)
            return False
        
        try:
            task = self.active_tasks[task_id]
            task.cancel()
            
            # 等待任务真正取消
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            # 更新数据库状态
            connection = await self.get_db_connection()
            if connection:
                try:
                    async with connection.cursor() as cursor:
                        await cursor.execute(
                            "UPDATE tasks SET status = %s WHERE id = %s",
                            ("cancelled", task_id)
                        )
                        await connection.commit()
                finally:
                    connection.close()
            
            del self.active_tasks[task_id]
            logger.info("Task %s cancelled successfully", task_id)
            return True
            
        except Exception as e:
            logger.error("Failed to cancel task %s: %s", task_id, e)
            return False
    
    def get_active_tasks(self) -> list:
        """获取活动任务列表"""
        return list(self.active_tasks.keys())
    
    def get_task_count(self) -> int:
        """获取活动任务数量"""
        return len(self.active_tasks)
    
    async def shutdown(self):
        """关闭任务处理器"""
        logger.info("Shutting down AsyncTaskProcessor...")
        self.is_running = False
        
        # 停止数据库轮询
        if self.polling_task:
            logger.info("Stopping database polling...")
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
        
        # 取消所有活动任务
        for task_id, task in self.active_tasks.items():
            logger.info("Cancelling task: %s", task_id)
            task.cancel()
        
        # 等待所有任务完成或被取消
        if self.active_tasks:
            await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)
        
        # 关闭执行器
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)
        
        logger.info("AsyncTaskProcessor shutdown complete")
