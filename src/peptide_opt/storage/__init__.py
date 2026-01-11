"""
存储服务模块

提供统一的对象存储接口，使用 SeaweedFS 作为后端。

使用示例:
    from peptide_opt.storage import get_storage
    
    storage = get_storage()
    
    # 上传文件
    await storage.upload_file(local_path, "tasks/task_id/output/file.pdb")
    
    # 下载文件
    await storage.download_file("tasks/task_id/output/file.pdb", local_path)
"""

from peptide_opt.storage.seaweed import SeaweedStorage, get_storage, reset_storage

__all__ = ["SeaweedStorage", "get_storage", "reset_storage"]
