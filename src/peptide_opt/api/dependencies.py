"""
API 依赖注入
"""

from typing import Generator

from peptide_opt.storage import get_storage
from peptide_opt.db import get_async_pool


async def get_db_connection():
    """获取数据库连接"""
    pool = await get_async_pool()
    async with pool.acquire() as conn:
        yield conn


def get_storage_service():
    """获取存储服务"""
    return get_storage()
