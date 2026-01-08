#!/usr/bin/env python3
"""
测试 PostgreSQL 数据库连接和定时任务功能
"""

import asyncio
import asyncpg
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 从配置模块加载数据库配置
from config.database_config import DB_CONFIG


async def test_db_connection():
    """测试数据库连接"""
    try:
        connection = await asyncpg.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
        )
        logger.info("PostgreSQL 数据库连接成功!")
        
        # 测试查询
        count = await connection.fetchval("SELECT COUNT(*) FROM tasks")
        logger.info(f"tasks表中共有 {count} 条记录")
        
        # 查询pending任务
        tasks = await connection.fetch(
            "SELECT id, task_type, status FROM tasks WHERE status = $1 LIMIT 5", 
            'pending'
        )
        logger.info(f"发现 {len(tasks)} 个pending任务")
        for task in tasks:
            logger.info(f"  - Task ID: {task['id']}, Type: {task['task_type']}, Status: {task['status']}")
            
        await connection.close()
        return True
        
    except Exception as e:
        logger.error(f"数据库连接测试失败: {e}")
        return False


async def test_storage_connection():
    """测试 SeaweedFS 存储连接"""
    try:
        from services import get_storage
        
        storage = get_storage()
        logger.info(f"SeaweedFS 存储初始化成功: {storage.filer_endpoint}")
        
        # 检查 bucket 是否存在
        exists = await storage.ensure_bucket_exists()
        logger.info(f"Bucket '{storage.bucket}' 状态: {'存在' if exists else '已创建'}")
        
        return True
    except Exception as e:
        logger.error(f"SeaweedFS 存储连接测试失败: {e}")
        return False


async def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("开始测试 peptide_opt 服务连接...")
    logger.info("=" * 50)
    
    # 测试数据库连接
    logger.info("\n[1/2] 测试 PostgreSQL 数据库连接...")
    db_success = await test_db_connection()
    
    # 测试存储连接
    logger.info("\n[2/2] 测试 SeaweedFS 存储连接...")
    storage_success = await test_storage_connection()
    
    # 输出结果
    logger.info("\n" + "=" * 50)
    logger.info("测试结果:")
    logger.info(f"  PostgreSQL 数据库: {'✓ 通过' if db_success else '✗ 失败'}")
    logger.info(f"  SeaweedFS 存储: {'✓ 通过' if storage_success else '✗ 失败'}")
    logger.info("=" * 50)
    
    if db_success and storage_success:
        logger.info("所有测试通过!")
    else:
        logger.error("部分测试失败，请检查配置!")


if __name__ == "__main__":
    asyncio.run(main())
