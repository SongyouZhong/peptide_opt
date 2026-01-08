"""
PostgreSQL 数据库连接模块
支持同步 (psycopg2) 和异步 (asyncpg) 连接
"""

import logging
from typing import Optional
import asyncpg

from config.database_config import DB_CONFIG, POOL_CONFIG

logger = logging.getLogger(__name__)

# 异步连接池
_async_pool: Optional[asyncpg.Pool] = None


async def get_async_pool() -> asyncpg.Pool:
    """获取或创建异步连接池"""
    global _async_pool
    if _async_pool is None:
        try:
            logger.info("Creating PostgreSQL async connection pool...")
            _async_pool = await asyncpg.create_pool(
                host=DB_CONFIG['host'],
                port=DB_CONFIG['port'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database'],
                min_size=POOL_CONFIG.get('min_size', 1),
                max_size=POOL_CONFIG.get('max_size', 5),
            )
            logger.info("PostgreSQL async connection pool created successfully")
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL async connection pool: {e}")
            raise
    return _async_pool


async def get_async_connection() -> asyncpg.Connection:
    """从异步连接池获取一个连接"""
    pool = await get_async_pool()
    return await pool.acquire()


async def release_async_connection(conn: asyncpg.Connection):
    """释放异步连接回连接池"""
    pool = await get_async_pool()
    await pool.release(conn)


class AsyncConnectionContext:
    """异步连接上下文管理器"""
    
    def __init__(self):
        self._conn: Optional[asyncpg.Connection] = None
    
    async def __aenter__(self) -> asyncpg.Connection:
        pool = await get_async_pool()
        self._conn = await pool.acquire()
        return self._conn
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            pool = await get_async_pool()
            await pool.release(self._conn)
            self._conn = None


def get_connection():
    """获取异步连接上下文管理器"""
    return AsyncConnectionContext()


async def close_pool():
    """关闭异步连接池"""
    global _async_pool
    if _async_pool:
        logger.info("Closing PostgreSQL async connection pool...")
        await _async_pool.close()
        _async_pool = None
        logger.info("PostgreSQL async connection pool closed")


# ============ 同步连接支持 (可选) ============

try:
    import psycopg2
    from psycopg2 import pool as sync_pool
    from psycopg2.extras import RealDictCursor
    
    _sync_pool = None
    
    def _get_sync_pool():
        """获取或创建同步连接池"""
        global _sync_pool
        if _sync_pool is None:
            try:
                logger.info("Creating PostgreSQL sync connection pool...")
                _sync_pool = sync_pool.ThreadedConnectionPool(
                    minconn=POOL_CONFIG.get("min_size", 1),
                    maxconn=POOL_CONFIG.get("max_size", 5),
                    host=DB_CONFIG["host"],
                    port=DB_CONFIG.get("port", 5432),
                    user=DB_CONFIG["user"],
                    password=DB_CONFIG["password"],
                    database=DB_CONFIG["database"],
                )
                logger.info("PostgreSQL sync connection pool created successfully")
            except Exception as e:
                logger.error(f"Failed to create PostgreSQL sync connection pool: {e}")
                raise
        return _sync_pool
    
    
    class SyncConnection:
        """同步连接包装器"""
        
        def __init__(self, conn):
            self._conn = conn
            self._conn.autocommit = True
        
        def cursor(self, dictionary=False):
            if dictionary:
                return self._conn.cursor(cursor_factory=RealDictCursor)
            return self._conn.cursor()
        
        def commit(self):
            self._conn.commit()
        
        def rollback(self):
            self._conn.rollback()
        
        def close(self):
            """将连接返回到连接池"""
            pool = _get_sync_pool()
            pool.putconn(self._conn)
        
        def __enter__(self):
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.close()
    
    
    def get_sync_connection():
        """从同步连接池获取一个连接"""
        pool = _get_sync_pool()
        conn = pool.getconn()
        return SyncConnection(conn)

except ImportError:
    logger.warning("psycopg2 not installed, sync connection not available")
    
    def get_sync_connection():
        raise ImportError("psycopg2 is required for sync connections")
