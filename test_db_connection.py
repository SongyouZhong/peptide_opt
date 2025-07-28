#!/usr/bin/env python3
"""
测试数据库连接和定时任务功能
"""

import asyncio
import aiomysql
import logging

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

async def test_db_connection():
    """测试数据库连接"""
    try:
        connection = await aiomysql.connect(**DB_CONFIG)
        logger.info("数据库连接成功!")
        
        async with connection.cursor() as cursor:
            # 测试查询
            await cursor.execute("SELECT COUNT(*) FROM tasks")
            count = await cursor.fetchone()
            logger.info(f"tasks表中共有 {count[0]} 条记录")
            
            # 查询pending任务
            await cursor.execute("SELECT id, task_type, status FROM tasks WHERE status = %s LIMIT 5", ('pending',))
            tasks = await cursor.fetchall()
            logger.info(f"发现 {len(tasks)} 个pending任务")
            
        connection.close()
        return True
        
    except Exception as e:
        logger.error(f"数据库连接测试失败: {e}")
        return False

async def main():
    """主函数"""
    logger.info("开始测试数据库连接...")
    success = await test_db_connection()
    
    if success:
        logger.info("数据库连接测试通过!")
    else:
        logger.error("数据库连接测试失败!")

if __name__ == "__main__":
    asyncio.run(main())
