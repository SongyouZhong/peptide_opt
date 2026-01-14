"""
肽段优化异步任务处理器
支持并发处理和进度更新
使用 PostgreSQL 数据库和 SeaweedFS 对象存储
"""

import asyncio
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Optional, Dict, Any

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
    """
    异步任务处理器
    
    支持多容器 Worker 模式:
    - 使用数据库行级锁 (SELECT FOR UPDATE SKIP LOCKED) 防止任务重复处理
    - 每个实例每次只处理一个任务 (max_workers=1)
    - 支持 docker compose up --scale peptide-opt=N 水平扩展
    """
    
    def __init__(self):
        task_settings = settings().task_processor
        db_settings = settings().database
        
        self.poll_interval = task_settings.poll_interval
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.task_progress: Dict[str, Dict[str, Any]] = {}
        self.is_running = True
        self.polling_task = None
        self._db_pool: Optional[asyncpg.Pool] = None
        
        # 每个容器实例每次只处理一个任务，便于水平扩展
        # 使用 docker compose up --scale peptide-opt=N 启动多个实例
        from concurrent.futures import ThreadPoolExecutor
        self.max_workers = 1  # 单任务模式
        self.thread_executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        # 数据库配置
        self.db_config = {
            'host': db_settings.host,
            'port': db_settings.port,
            'user': db_settings.user,
            'password': db_settings.password,
            'database': db_settings.database,
        }
        
        # 生成唯一的 worker ID 用于日志追踪
        import uuid
        self.worker_id = str(uuid.uuid4())[:8]
        
        logger.info("AsyncTaskProcessor initialized (worker_id=%s, max_workers=%d)", 
                   self.worker_id, self.max_workers)
    
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
        """
        定时从数据库获取待处理的peptide优化任务
        
        使用 SELECT FOR UPDATE SKIP LOCKED 实现行级锁:
        - 防止多个 worker 同时获取同一个任务
        - SKIP LOCKED 确保如果任务被锁定，则跳过而不是等待
        - 每个 worker 每次只获取一个任务 (单任务模式)
        """
        while self.is_running:
            try:
                # 如果已有任务在执行，则等待
                if len(self.active_tasks) >= self.max_workers:
                    logger.debug("[Worker %s] Already processing %d task(s), waiting...", 
                                self.worker_id, len(self.active_tasks))
                    await asyncio.sleep(self.poll_interval)
                    continue
                
                async with self._db_pool.acquire() as connection:
                    # 使用事务和行级锁获取任务
                    async with connection.transaction():
                        # SELECT FOR UPDATE SKIP LOCKED:
                        # - FOR UPDATE: 锁定选中的行
                        # - SKIP LOCKED: 跳过已被其他 worker 锁定的行
                        # - LIMIT 1: 每次只获取一个任务
                        task = await connection.fetchrow(
                            """
                            SELECT id, job_dir 
                            FROM tasks 
                            WHERE task_type = 'peptide_optimization' 
                              AND status = 'pending' 
                            ORDER BY created_at ASC
                            LIMIT 1
                            FOR UPDATE SKIP LOCKED
                            """
                        )
                        
                        if task:
                            task_id, job_dir = task['id'], task['job_dir']
                            
                            if task_id not in self.active_tasks:
                                # 立即将任务状态更新为 processing 并设置 started_at，防止其他 worker 获取
                                await connection.execute(
                                    "UPDATE tasks SET status = $1, started_at = NOW() WHERE id = $2",
                                    "processing", task_id
                                )
                                
                                logger.info("[Worker %s] Claimed task: %s", 
                                           self.worker_id, task_id)
                                
                                # 提交任务到执行队列
                                await self.submit_task(task_id, job_dir)
                            else:
                                logger.debug("[Worker %s] Task %s already in progress, skipping", 
                                            self.worker_id, task_id)
                        else:
                            logger.debug("[Worker %s] No pending tasks available", self.worker_id)
                        
            except Exception as e:
                logger.error("[Worker %s] Error polling database for tasks: %s", 
                            self.worker_id, e)
            
            await asyncio.sleep(self.poll_interval)
        
        logger.info("[Worker %s] Database polling stopped", self.worker_id)
    
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
        import os
        
        # 首先检查环境变量
        env_path = os.environ.get('PROTEINMPNN_PATH')
        if env_path:
            env_path = Path(env_path)
            if env_path.exists() and (env_path / "protein_mpnn_run.py").exists():
                return str(env_path.resolve())
        
        search_paths = [
            Path("/app/vendor/ProteinMPNN"),  # Docker 容器路径
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
    
    def _get_temp_dir(self) -> Path:
        """获取临时目录"""
        storage_settings = settings().storage
        temp_dir = Path(storage_settings.temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir
    
    def _is_seaweedfs_path(self, job_dir: str) -> bool:
        """
        判断 job_dir 是否是 SeaweedFS 存储前缀格式
        
        本地路径格式: /tmp/astramolecula/jobs/peptide_optimization/{job_id}
        SeaweedFS 前缀格式: jobs/peptide_optimization/{job_id}
        """
        # 如果以 / 开头且包含 /tmp，则是本地路径格式
        if job_dir.startswith('/'):
            return False
        return True
    
    def _convert_to_storage_prefix(self, job_dir: str) -> str:
        """
        将 job_dir 转换为 SeaweedFS 存储前缀
        
        本地路径: /tmp/astramolecula/jobs/peptide_optimization/{job_id}
        转换为: jobs/peptide_optimization/{job_id}
        """
        if self._is_seaweedfs_path(job_dir):
            return job_dir
        
        # 从本地路径提取存储前缀
        # 格式: /tmp/astramolecula/jobs/peptide_optimization/{job_id}
        parts = job_dir.split('/tmp/astramolecula/')
        if len(parts) > 1:
            return parts[1]
        
        # 退而求其次，提取 jobs/ 开始的部分
        if '/jobs/' in job_dir:
            idx = job_dir.index('/jobs/') + 1
            return job_dir[idx:]
        
        # 无法识别的格式，返回原值
        logger.warning("Cannot convert job_dir to storage prefix: %s", job_dir)
        return job_dir
    
    async def _download_input_files(self, storage_prefix: str, temp_input_dir: Path) -> Dict[str, Any]:
        """
        从 SeaweedFS 下载输入文件到临时目录
        
        Returns:
            包含配置信息的字典
        """
        storage = get_storage()
        config = {}
        
        # 下载配置文件（如果存在）
        # 注意：AstraMolecula 上传配置文件到 {job_prefix}/optimization_config.txt（不在 input 子目录下）
        config_key = f"{storage_prefix}/optimization_config.txt"
        config_file = temp_input_dir / "optimization_config.txt"
        try:
            await storage.download_file(config_key, config_file)
            logger.info("Downloaded config file: %s", config_key)
            # 解析配置文件
            with open(config_file, 'r') as f:
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
        except FileNotFoundError:
            logger.warning("Config file not found in storage: %s", config_key)
        except Exception as e:
            logger.error("Failed to download config file: %s", e)
        
        # 下载 FASTA 文件
        fasta_key = f"{storage_prefix}/input/peptide.fasta"
        fasta_file = temp_input_dir / "peptide.fasta"
        try:
            await storage.download_file(fasta_key, fasta_file)
            logger.info("Downloaded FASTA file: %s", fasta_key)
        except Exception as e:
            logger.error("Failed to download FASTA file: %s", e)
            raise FileNotFoundError(f"FASTA file not found in storage: {fasta_key}")
        
        # 下载 PDB 受体文件
        receptor_filename = config.get('receptor_pdb_filename', '5ffg.pdb')
        pdb_key = f"{storage_prefix}/input/{receptor_filename}"
        pdb_file = temp_input_dir / receptor_filename
        try:
            await storage.download_file(pdb_key, pdb_file)
            logger.info("Downloaded PDB file: %s", pdb_key)
        except Exception as e:
            logger.error("Failed to download PDB file: %s", e)
            raise FileNotFoundError(f"PDB file not found in storage: {pdb_key}")
        
        return config
    
    async def process_peptide_optimization_task(self, task_id: str, job_dir: str):
        """处理肽段优化任务（支持 SeaweedFS 存储）"""
        connection = None
        temp_job_dir = None
        
        try:
            connection = await self.get_db_connection()
            if not connection:
                raise Exception("Failed to connect to database")
            
            progress_callback = TaskProgressCallback(task_id, connection, self)
            await progress_callback.update_progress(0, "Starting peptide optimization")
            
            original_cwd = os.getcwd()
            
            try:
                # 将 job_dir 转换为 SeaweedFS 存储前缀
                storage_prefix = self._convert_to_storage_prefix(job_dir)
                logger.info("Task %s: storage_prefix=%s (original job_dir=%s)", 
                           task_id, storage_prefix, job_dir)
                
                # 创建临时目录
                temp_base = self._get_temp_dir()
                temp_job_dir = temp_base / task_id
                temp_job_dir.mkdir(parents=True, exist_ok=True)
                temp_input_dir = temp_job_dir / "input"
                temp_input_dir.mkdir(exist_ok=True)
                temp_output_dir = temp_job_dir / "output"
                temp_output_dir.mkdir(exist_ok=True)
                
                logger.info("Task %s: Created temp directory: %s", task_id, temp_job_dir)
                
                # 从 SeaweedFS 下载输入文件
                await progress_callback.update_progress(5, "Downloading input files from storage")
                config = await self._download_input_files(storage_prefix, temp_input_dir)
                
                # 切换到临时目录
                os.chdir(temp_job_dir)
                
                fasta_file = str(temp_input_dir / "peptide.fasta")
                receptor_filename = config.get('receptor_pdb_filename', '5ffg.pdb')
                pdb_file = str(temp_input_dir / receptor_filename)

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
                    input_dir=str(temp_input_dir),
                    output_dir=str(temp_output_dir),
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
                await self._upload_results_to_storage(task_id, str(temp_job_dir), storage_prefix)
                
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
                
                # 清理临时目录
                if temp_job_dir and temp_job_dir.exists():
                    try:
                        shutil.rmtree(temp_job_dir, ignore_errors=True)
                        logger.info("Task %s: Cleaned up temp directory: %s", task_id, temp_job_dir)
                    except Exception as e:
                        logger.warning("Task %s: Failed to cleanup temp directory: %s", task_id, e)
                
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
        
        # 关闭线程池
        if self.thread_executor:
            logger.info("Shutting down thread executor...")
            self.thread_executor.shutdown(wait=False)
        
        logger.info("AsyncTaskProcessor shutdown complete")
    
    async def _upload_results_to_storage(self, task_id: str, job_dir: str, storage_prefix: str = None):
        """
        上传任务结果到 SeaweedFS
        
        Args:
            task_id: 任务ID
            job_dir: 本地任务目录（临时目录）
            storage_prefix: SeaweedFS 存储前缀（可选，用于保持原始路径结构）
        """
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
                    
                    # 使用存储前缀或默认路径
                    if storage_prefix:
                        remote_key = f"{storage_prefix}/output/{relative_path}"
                    else:
                        remote_key = f"tasks/{task_id}/peptide/output/{relative_path}"
                    
                    try:
                        await storage.upload_file(file_path, remote_key)
                        uploaded_count += 1
                    except Exception as e:
                        logger.error("Failed to upload file %s: %s", file_path, e)
            
            logger.info("Uploaded %d files to SeaweedFS for task %s", uploaded_count, task_id)
            
        except Exception as e:
            logger.error("Failed to upload results to storage for task %s: %s", task_id, e)
