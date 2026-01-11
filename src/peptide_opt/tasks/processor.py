"""
肽段优化异步任务处理器
支持并发处理和进度更新
使用 PostgreSQL 数据库和 SeaweedFS 对象存储
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

import asyncpg

from peptide_opt.core.optimizer import PeptideOptimizer
from peptide_opt.core.validators import validate_fasta_file, validate_pdb_file
from peptide_opt.config.settings import settings
from peptide_opt.storage import get_storage

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
            
            # 更新数据库中的任务状态
            await self.connection.execute(
                "UPDATE tasks SET status = $1 WHERE id = $2",
                "processing", self.task_id
            )
                
            logger.info("Task %s progress: %.1f%% - %s", 
                        self.task_id, progress, step_name or info or "")
        except Exception as e:
            logger.error("Failed to update progress for task %s: %s", self.task_id, e)
    
    def mark_completed(self):
        """标记任务为已完成"""
        self._is_completed = True


class AsyncTaskProcessor:
    """异步任务处理器"""
    
    def __init__(self, max_workers: int = None):
        task_settings = settings().task_processor
        db_settings = settings().database
        
        self.max_workers = max_workers or task_settings.max_workers
        self.poll_interval = task_settings.poll_interval
        self.thread_executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=self.max_workers)
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.task_progress: Dict[str, Dict[str, Any]] = {}
        self.is_running = True
        self.polling_task = None
        self._db_pool: Optional[asyncpg.Pool] = None
        
        # 数据库配置
        self.db_config = {
            'host': db_settings.host,
            'port': db_settings.port,
            'user': db_settings.user,
            'password': db_settings.password,
            'database': db_settings.database,
        }
        
        logger.info("AsyncTaskProcessor initialized with %d workers", self.max_workers)
    
    async def start_polling(self):
        """启动数据库轮询"""
        if self.polling_task is None:
            await self._init_db_pool()
            logger.info("Starting database polling for peptide optimization tasks...")
            self.polling_task = asyncio.create_task(self._poll_database_tasks())
    
    async def _init_db_pool(self):
        """初始化数据库连接池"""
        if self._db_pool is None:
            try:
                logger.info("Creating PostgreSQL connection pool...")
                self._db_pool = await asyncpg.create_pool(
                    host=self.db_config['host'],
                    port=self.db_config['port'],
                    user=self.db_config['user'],
                    password=self.db_config['password'],
                    database=self.db_config['database'],
                    min_size=1,
                    max_size=5,
                )
                logger.info("PostgreSQL connection pool created successfully")
            except Exception as e:
                logger.error(f"Failed to create database pool: {e}")
                raise
    
    async def _poll_database_tasks(self):
        """定时从数据库获取待处理的peptide优化任务"""
        while self.is_running:
            try:
                async with self._db_pool.acquire() as connection:
                    pending_tasks = await connection.fetch(
                        "SELECT id, job_dir FROM tasks WHERE task_type = 'peptide_optimization' AND status = 'pending' LIMIT 5"
                    )
                    
                    if pending_tasks:
                        logger.info(f"Found {len(pending_tasks)} pending peptide optimization tasks")
                        
                    for task in pending_tasks:
                        task_id, job_dir = task['id'], task['job_dir']
                        if task_id not in self.active_tasks:
                            logger.info(f"Submitting peptide optimization task: {task_id}")
                            await self.submit_task(task_id, job_dir)
                        else:
                            logger.debug(f"Task {task_id} already in progress, skipping")
                        
            except Exception as e:
                logger.error(f"Error polling database for tasks: {e}")
            
            await asyncio.sleep(self.poll_interval)
        
        logger.info("Database polling stopped")
    
    async def get_db_connection(self):
        """从连接池获取数据库连接"""
        try:
            if self._db_pool is None:
                await self._init_db_pool()
            return await self._db_pool.acquire()
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            return None
    
    async def release_db_connection(self, connection):
        """释放数据库连接回连接池"""
        if connection and self._db_pool:
            await self._db_pool.release(connection)
    
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
    
    def _find_proteinmpnn_dir(self) -> str:
        """查找 ProteinMPNN 目录"""
        search_paths = [
            Path(__file__).parent.parent.parent.parent / "vendor" / "ProteinMPNN",
            Path(__file__).parent.parent.parent.parent / "ProteinMPNN",
            Path.cwd() / "ProteinMPNN",
            Path.cwd() / "vendor" / "ProteinMPNN",
        ]
        
        for path in search_paths:
            if path.exists() and (path / "protein_mpnn_run.py").exists():
                return str(path.resolve())
        
        # 默认路径
        return str(Path(__file__).parent.parent.parent.parent / "vendor" / "ProteinMPNN")
    
    async def process_peptide_optimization_task(self, task_id: str, job_dir: str):
        """处理肽段优化任务"""
        connection = None
        try:
            connection = await self.get_db_connection()
            if not connection:
                raise Exception("Failed to connect to database")
            
            progress_callback = TaskProgressCallback(task_id, connection, self)
            await progress_callback.update_progress(0, "Starting peptide optimization")
            
            original_cwd = os.getcwd()
            
            try:
                os.chdir(job_dir)
                
                input_dir = os.path.join(job_dir, "input")
                fasta_file = os.path.join(input_dir, "peptide.fasta")
                
                config = await self._read_task_config(job_dir)
                receptor_filename = config.get('receptor_pdb_filename', '5ffg.pdb')
                pdb_file = os.path.join(input_dir, receptor_filename)

                if not os.path.exists(fasta_file):
                    raise FileNotFoundError(f"FASTA file not found: {fasta_file}")
                if not os.path.exists(pdb_file):
                    raise FileNotFoundError(f"PDB file not found: {pdb_file}")

                await progress_callback.update_progress(10, "Validating input files")
                validate_fasta_file(fasta_file)
                validate_pdb_file(pdb_file)
                
                await progress_callback.update_progress(20, "Reading task configuration")
                
                def sync_progress_callback(progress, message):
                    logger.info(f"Task {task_id} progress: {progress:.1f}% - {message}")
                
                proteinmpnn_path = self._find_proteinmpnn_dir()
                
                optimizer = PeptideOptimizer(
                    input_dir=input_dir,
                    output_dir=os.path.join(job_dir, "output"),
                    proteinmpnn_dir=proteinmpnn_path,
                    cores=config.get('cores', 12),
                    cleanup=config.get('cleanup', True),
                    n_poses=config.get('n_poses', 10),
                    num_seq_per_target=config.get('num_seq_per_target', 10),
                    proteinmpnn_seed=config.get('proteinmpnn_seed', 37),
                    progress_callback=sync_progress_callback,
                    receptor_pdb_filename=config.get('receptor_pdb_filename')
                )
                
                await progress_callback.update_progress(30, "Running peptide optimization")
                await asyncio.get_event_loop().run_in_executor(
                    self.thread_executor, 
                    optimizer.run_full_pipeline
                )
                
                await progress_callback.update_progress(90, "Finalizing results")
                await progress_callback.update_progress(92, "Uploading results to storage")
                await self._upload_results_to_storage(task_id, job_dir)
                
                await connection.execute(
                    "UPDATE tasks SET status = $1, finished_at = NOW() WHERE id = $2",
                    "finished", task_id
                )
                
                progress_callback.mark_completed()
                logger.info("Task %s completed successfully", task_id)
                
                self.task_progress[task_id] = {
                    "overall_progress": 100,
                    "current_step": "Completed",
                    "step_progress": 100,
                    "details": "Optimization completed successfully",
                    "status": "finished",
                    "last_updated": time.time()
                }
                
            finally:
                os.chdir(original_cwd)
                
        except Exception as e:
            logger.error("Task %s failed: %s", task_id, str(e))
            
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
                    await connection.execute(
                        "UPDATE tasks SET status = $1, finished_at = NOW() WHERE id = $2",
                        "failed", task_id
                    )
                except Exception as db_error:
                    logger.error("Failed to update task status in database: %s", db_error)
        
        finally:
            if connection:
                await self.release_db_connection(connection)
            
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
            
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            connection = await self.get_db_connection()
            if connection:
                try:
                    await connection.execute(
                        "UPDATE tasks SET status = $1, finished_at = NOW() WHERE id = $2",
                        "cancelled", task_id
                    )
                finally:
                    await self.release_db_connection(connection)
            
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
        
        if self.polling_task:
            logger.info("Stopping database polling...")
            self.polling_task.cancel()
            try:
                await self.polling_task
            except asyncio.CancelledError:
                pass
        
        for task_id, task in self.active_tasks.items():
            logger.info("Cancelling task: %s", task_id)
            task.cancel()
        
        if self.active_tasks:
            await asyncio.gather(*self.active_tasks.values(), return_exceptions=True)
        
        if self._db_pool:
            logger.info("Closing database connection pool...")
            await self._db_pool.close()
            self._db_pool = None
        
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)
        
        logger.info("AsyncTaskProcessor shutdown complete")
    
    async def _upload_results_to_storage(self, task_id: str, job_dir: str):
        """上传任务结果到 SeaweedFS"""
        try:
            storage = get_storage()
            output_dir = Path(job_dir) / "output"
            
            if not output_dir.exists():
                logger.warning("Output directory not found: %s", output_dir)
                return
            
            uploaded_count = 0
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    relative_path = file_path.relative_to(output_dir)
                    remote_key = f"tasks/{task_id}/peptide/output/{relative_path}"
                    try:
                        await storage.upload_file(file_path, remote_key)
                        uploaded_count += 1
                    except Exception as e:
                        logger.error("Failed to upload file %s: %s", file_path, e)
            
            logger.info("Uploaded %d files to SeaweedFS for task %s", uploaded_count, task_id)
            
        except Exception as e:
            logger.error("Failed to upload results to storage for task %s: %s", task_id, e)
