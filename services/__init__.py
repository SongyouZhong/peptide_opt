"""
存储服务模块

提供统一的对象存储接口，使用 SeaweedFS 作为后端。

使用示例:
    from services.storage import get_storage
    
    storage = get_storage()
    
    # 上传文件
    await storage.upload_file(local_path, "tasks/task_id/peptide/output/file.pdb")
    
    # 下载文件
    await storage.download_file("tasks/task_id/peptide/output/file.pdb", local_path)
    
    # 生成下载 URL
    url = await storage.get_presigned_url("tasks/task_id/peptide/output/file.pdb")
    
    # 检查文件是否存在
    exists = await storage.file_exists("tasks/task_id/peptide/output/file.pdb")
"""
import logging
from typing import Optional

from .storage.seaweed_storage import SeaweedStorage
from config.settings import storage as storage_config

logger = logging.getLogger("storage")

_storage_instance: Optional[SeaweedStorage] = None


def get_storage() -> SeaweedStorage:
    """
    获取 SeaweedFS 存储实例（单例）
    
    Returns:
        SeaweedStorage 实例
    """
    global _storage_instance
    
    if _storage_instance is None:
        logger.info("Initializing SeaweedFS storage...")
        _storage_instance = SeaweedStorage()
    
    return _storage_instance


def reset_storage():
    """
    重置存储实例（主要用于测试）
    """
    global _storage_instance
    _storage_instance = None


__all__ = ['get_storage', 'reset_storage', 'SeaweedStorage', 'storage_config']
