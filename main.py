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

async def process_peptide_optimization_task(task_id: str, job_dir: str, connection):
    """处理单个肽段优化任务"""
    # 保存当前工作目录
    original_cwd = os.getcwd()
    
    try:
        logger.info(f"开始处理肽段优化任务: {task_id}")
        
        # 切换到peptide_opt目录
        peptide_opt_dir = Path(__file__).parent.absolute()
        os.chdir(peptide_opt_dir)
        logger.info(f"切换工作目录到: {peptide_opt_dir}")
        
        # 读取任务配置文件
        job_path = Path(job_dir)
        config_file = job_path / "optimization_config.txt"
        
        if not config_file.exists():
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
        
        # 解析配置文件
        config = {}
        with open(config_file, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    # 转换数据类型
                    if value.lower() in ('true', 'false'):
                        config[key] = value.lower() == 'true'
                    elif value.isdigit():
                        config[key] = int(value)
                    else:
                        config[key] = value
        
        logger.info(f"任务配置: {config}")
        
        # 检查输入文件
        input_dir = job_path / "input"
        peptide_fasta = input_dir / "peptide.fasta"
        receptor_pdb = input_dir / "5ffg.pdb"
        
        if not peptide_fasta.exists():
            raise FileNotFoundError(f"肽段FASTA文件不存在: {peptide_fasta}")
        if not receptor_pdb.exists():
            raise FileNotFoundError(f"受体PDB文件不存在: {receptor_pdb}")
        
        # 设置输出目录
        output_dir = job_path / "output"
        output_dir.mkdir(exist_ok=True)
        
        # 创建PeptideOptimizer实例
        optimizer = PeptideOptimizer(
            input_dir=str(input_dir),
            output_dir=str(output_dir),
            proteinmpnn_dir="./ProteinMPNN/",  # 使用相对路径
            cores=config.get('cores', 12),
            cleanup=config.get('cleanup', True)
        )
        
        # 更新任务状态为running
        async with connection.cursor() as cursor:
            await cursor.execute(
                "UPDATE tasks SET status = %s, started_at = NOW() WHERE id = %s",
                ('running', task_id)
            )
        
        logger.info(f"任务 {task_id} 开始运行优化流程")
        
        # 运行优化流程
        if config.get('step'):
            # 运行指定步骤
            step = config['step']
            step_methods = {
                1: optimizer.step1_model_peptide,
                2: optimizer.step2_add_hydrogens,
                3: optimizer.step3_docking,
                4: optimizer.step4_sort_atoms,
                5: optimizer.step5_score_binding,
                6: optimizer.step6_merge_structures,
                7: optimizer.step7_proteinmpnn_optimization,
                8: optimizer.step8_final_analysis
            }
            
            if step in step_methods:
                logger.info(f"执行步骤 {step}")
                step_methods[step]()
            else:
                raise ValueError(f"无效的步骤号: {step}")
        else:
            # 运行完整流程
            if config.get('proteinmpnn_enabled', True):
                logger.info("执行完整的肽段优化流程（包含ProteinMPNN）")
                optimizer.run_full_pipeline()
            else:
                logger.info("执行肽段优化流程（不包含ProteinMPNN步骤7）")
                # 运行步骤1-6和8
                optimizer.step1_model_peptide()
                optimizer.step2_add_hydrogens()
                optimizer.step3_docking()
                optimizer.step4_sort_atoms()
                optimizer.step5_score_binding()
                optimizer.step6_merge_structures()
                optimizer.step8_final_analysis()
                
                # 清理中间文件
                if optimizer.cleanup:
                    optimizer.cleanup_intermediate_files()
        
        # 更新任务状态为finished
        async with connection.cursor() as cursor:
            await cursor.execute(
                "UPDATE tasks SET status = %s, finished_at = NOW() WHERE id = %s",
                ('finished', task_id)
            )
        
        logger.info(f"任务 {task_id} 完成")
        
    except Exception as e:
        logger.error(f"任务 {task_id} 执行失败: {str(e)}")
        # 更新任务状态为failed
        try:
            async with connection.cursor() as cursor:
                await cursor.execute(
                    "UPDATE tasks SET status = %s, finished_at = NOW() WHERE id = %s",
                    ('failed', task_id)
                )
        except Exception as db_error:
            logger.error(f"更新任务状态失败: {db_error}")
        raise
    finally:
        # 恢复原始工作目录
        os.chdir(original_cwd)

async def query_tasks():
    """查询tasks表中的待处理任务"""
    connection = await get_db_connection()
    if not connection:
        return
    
    try:
        async with connection.cursor() as cursor:
            # 查询状态为pending的肽段优化任务
            await cursor.execute(
                "SELECT id, user_id, task_type, job_dir, status FROM tasks WHERE status = %s AND task_type = %s",
                ('pending', 'peptide_optimization')
            )
            tasks = await cursor.fetchall()
            
            if tasks:
                logger.info(f"发现 {len(tasks)} 个待处理的肽段优化任务")
                for task in tasks:
                    task_id, user_id, task_type, job_dir, status = task
                    logger.info(f"处理任务: ID={task_id}, 用户={user_id}, 类型={task_type}")
                    
                    try:
                        # 处理肽段优化任务
                        await process_peptide_optimization_task(task_id, job_dir, connection)
                    except Exception as e:
                        logger.error(f"处理任务 {task_id} 时发生错误: {e}")
                        continue
            else:
                logger.info("没有发现待处理的肽段优化任务")
                
    except Exception as e:
        logger.error(f"查询任务时发生错误: {e}")
    finally:
        connection.close()

async def background_task_runner():
    """后台定时任务运行器"""
    logger.info("定时任务启动，每5分钟查询一次tasks表")
    while True:
        try:
            await query_tasks()
            await asyncio.sleep(300)  # 等待5分钟（300秒）
        except Exception as e:
            logger.error(f"定时任务执行错误: {e}")
            await asyncio.sleep(60)  # 发生错误时等待1分钟后重试

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)
