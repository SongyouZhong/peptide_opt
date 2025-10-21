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
    
    def __init__(self, task_id: str, connection, processor):
        self.task_id = task_id
        self.connection = connection
        self.processor = processor
        self._is_completed = False
        
    async def update_progress(self, progress: float, info: str = None, step_name: str = None, step_progress: float = None):
        """更新任务进度"""
        if self._is_completed:
            logger.debug("Task %s already completed, skipping progress update", self.task_id)
            return
            
        try:
            # 更新内存中的进度信息
            self.processor.task_progress[self.task_id] = {
                "overall_progress": progress,
                "current_step": step_name or info or "Processing...",
                "step_progress": step_progress,
                "details": info,
                "status": "processing",
                "last_updated": time.time()
            }
            
            # 更新数据库中的任务状态 - 只更新状态，不包含progress和info字段
            async with self.connection.cursor() as cursor:
                await cursor.execute(
                    "UPDATE tasks SET status = %s WHERE id = %s",
                    ("processing", self.task_id)
                )
                await self.connection.commit()
                
            logger.info("Task %s progress: %.1f%% - %s", 
                        self.task_id, progress, step_name or info or "")
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
        self.task_progress: Dict[str, Dict[str, Any]] = {}  # 存储任务进度信息
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
    
    async def _read_task_config(self, job_dir: str) -> Dict[str, Any]:
        """读取任务配置文件"""
        config_path = os.path.join(job_dir, "optimization_config.txt")
        config = {}
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if '=' in line and not line.startswith('#'):
                            key, value = line.split('=', 1)
                            # 尝试转换数据类型
                            if value.lower() in ('true', 'false'):
                                config[key] = value.lower() == 'true'
                            elif value.isdigit():
                                config[key] = int(value)
                            elif value.replace('.', '').isdigit():
                                config[key] = float(value)
                            else:
                                config[key] = value
                logger.info("Loaded task config for job %s: %s", job_dir, config)
            except Exception as e:
                logger.error("Failed to read config file %s: %s", config_path, e)
        else:
            logger.warning("Config file not found at %s, using default values", config_path)
        
        return config
    
    async def process_peptide_optimization_task(self, task_id: str, job_dir: str):
        """处理肽段优化任务"""
        connection = None
        try:
            # 获取数据库连接
            connection = await self.get_db_connection()
            if not connection:
                raise Exception("Failed to connect to database")
            
            # 创建进度回调
            progress_callback = TaskProgressCallback(task_id, connection, self)
            
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
                
                # 读取任务配置
                await progress_callback.update_progress(20, "Reading task configuration")
                config = await self._read_task_config(job_dir)
                
                # 读取peptide序列以计算长度和其他参数
                fasta_file = os.path.join(input_dir, "peptide.fasta")
                peptide_sequence = ""
                peptide_length = 0
                if os.path.exists(fasta_file):
                    with open(fasta_file, 'r') as f:
                        lines = f.readlines()
                        if len(lines) > 1:
                            peptide_sequence = lines[1].strip()
                            peptide_length = len(peptide_sequence)
                
                # 计算复杂度因子和计算单元
                n_iterations = config.get('n_iterations', 5)
                n_rosetta_runs = config.get('n_rosetta_runs', 20)
                total_calculations = n_iterations * n_rosetta_runs
                complexity_factor = (peptide_length / 10) ** 1.5 if peptide_length > 0 else 1.0
                total_compute_units = total_calculations * complexity_factor
                
                # 输出完整的优化参数信息到日志
                logger.info("=== PEPTIDE OPTIMIZATION PARAMETERS ===")
                logger.info("Task ID: %s", task_id)
                logger.info("Job Directory: %s", job_dir)
                logger.info("")
                logger.info("--- Peptide Sequence Parameters ---")
                logger.info("Peptide Sequence: %s", peptide_sequence or config.get('peptide_sequence', 'N/A'))
                logger.info("Peptide Length: %d amino acids", peptide_length or len(config.get('peptide_sequence', '')))
                logger.info("Receptor PDB Filename: %s", config.get('receptor_pdb_filename', 'N/A'))
                logger.info("")
                logger.info("--- Optimization Parameters ---")
                logger.info("Number of Iterations: %d", n_iterations)
                logger.info("Rosetta Runs per Iteration: %d", n_rosetta_runs)
                logger.info("Number of Docking Poses: %d", config.get('n_poses', 10))
                logger.info("")
                logger.info("--- ProteinMPNN Parameters ---")
                logger.info("Sequences per Target: %d", config.get('num_seq_per_target', 10))
                logger.info("ProteinMPNN Seed: %d", config.get('proteinmpnn_seed', 37))
                logger.info("ProteinMPNN Enabled: %s", config.get('proteinmpnn_enabled', True))
                logger.info("")
                logger.info("--- Computational Parameters ---")
                logger.info("CPU Cores: %d", config.get('cores', 12))
                logger.info("Total Calculations: %d", total_calculations)
                logger.info("Complexity Factor: %.3f", complexity_factor)
                logger.info("Total Compute Units: %.2f", total_compute_units)
                logger.info("")
                logger.info("--- System Parameters ---")
                logger.info("Cleanup Intermediate Files: %s", config.get('cleanup', True))
                logger.info("==========================================")
                
                # 创建优化器 - 传递目录路径而不是文件路径
                await progress_callback.update_progress(25, "Initializing optimizer")
                
                # 创建一个同步的进度回调函数
                def sync_progress_callback(progress, message):
                    # 这个函数会在同步上下文中被调用，我们需要记录进度
                    # 由于在线程池中运行，我们只记录日志，实际的数据库更新由主循环处理
                    logger.info(f"Task {task_id} progress: {progress:.1f}% - {message}")
                
                # 获取peptide_opt根目录的绝对路径
                peptide_opt_root = os.path.dirname(os.path.abspath(__file__))
                proteinmpnn_path = os.path.join(peptide_opt_root, "ProteinMPNN")
                
                optimizer = PeptideOptimizer(
                    input_dir=input_dir,
                    output_dir=os.path.join(job_dir, "output"),
                    proteinmpnn_dir=proteinmpnn_path,  # 使用绝对路径
                    cores=config.get('cores', 12),
                    cleanup=config.get('cleanup', True),
                    n_poses=config.get('n_poses', 10),
                    num_seq_per_target=config.get('num_seq_per_target', 10),
                    proteinmpnn_seed=config.get('proteinmpnn_seed', 37),
                    progress_callback=sync_progress_callback
                )
                
                # 执行优化步骤
                await progress_callback.update_progress(30, "Running peptide optimization")
                result = await asyncio.get_event_loop().run_in_executor(
                    self.thread_executor, 
                    optimizer.run_full_pipeline
                )
                
                await progress_callback.update_progress(90, "Finalizing results")
                
                # 更新数据库为完成状态 - 使用NOW()确保时区一致
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        """UPDATE tasks 
                           SET status = %s, finished_at = NOW()
                           WHERE id = %s""",
                        ("finished", task_id)
                    )
                    await connection.commit()
                
                progress_callback.mark_completed()
                logger.info("Task %s completed successfully", task_id)
                
                # 更新进度信息为完成状态
                self.task_progress[task_id] = {
                    "overall_progress": 100,
                    "current_step": "Completed",
                    "step_progress": 100,
                    "details": "Optimization completed successfully",
                    "status": "finished",
                    "last_updated": time.time()
                }
                
            finally:
                # 恢复原始工作目录
                os.chdir(original_cwd)
                
        except Exception as e:
            logger.error("Task %s failed: %s", task_id, str(e))
            
            # 更新进度信息为失败状态
            self.task_progress[task_id] = {
                "overall_progress": 0,
                "current_step": "Failed",
                "step_progress": 0,
                "details": f"Task failed: {str(e)}",
                "status": "failed",
                "last_updated": time.time()
            }
            
            if connection:
                try:
                    async with connection.cursor() as cursor:
                        await cursor.execute(
                            "UPDATE tasks SET status = %s, finished_at = NOW() WHERE id = %s",
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
                            "UPDATE tasks SET status = %s, finished_at = NOW() WHERE id = %s",
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
    
    def get_task_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取特定任务的进度信息"""
        return self.task_progress.get(task_id)
    
    def get_all_tasks_progress(self) -> Dict[str, Dict[str, Any]]:
        """获取所有任务的进度信息"""
        return self.task_progress.copy()
    
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
