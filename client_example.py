#!/usr/bin/env python3
"""
Simple client example for Peptide Optimization API
肽段优化API的简单客户端示例
"""

import requests
import time
import json
import os
from pathlib import Path

class PeptideOptimizationClient:
    """肽段优化API客户端"""
    
    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url.rstrip('/')
        
    def submit_optimization(self, pdb_file, fasta_file, output_dir, user_id, cores=12, cleanup=True):
        """提交优化任务"""
        
        # 验证输入文件
        if not os.path.exists(pdb_file):
            raise FileNotFoundError(f"PDB file not found: {pdb_file}")
        if not os.path.exists(fasta_file):
            raise FileNotFoundError(f"FASTA file not found: {fasta_file}")
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 准备请求数据
        data = {
            "pdb_file_path": os.path.abspath(pdb_file),
            "fasta_file_path": os.path.abspath(fasta_file),
            "output_path": os.path.abspath(output_dir),
            "user_id": user_id,
            "cores": cores,
            "cleanup": cleanup
        }
        
        # 发送请求
        response = requests.post(f"{self.api_url}/optimize", data=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Task submitted successfully!")
            print(f"📋 Task ID: {result['task_id']}")
            print(f"👤 User ID: {result['user_id']}")
            return result['task_id']
        else:
            error_msg = response.text
            print(f"❌ Failed to submit task: {error_msg}")
            raise Exception(f"API request failed: {error_msg}")
    
    def get_task_status(self, task_id):
        """获取任务状态"""
        response = requests.get(f"{self.api_url}/status/{task_id}")
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            print(f"❌ Task {task_id} not found")
            return None
        else:
            print(f"❌ Error getting task status: {response.text}")
            return None
    
    def wait_for_completion(self, task_id, check_interval=30, max_wait_hours=2):
        """等待任务完成"""
        print(f"⏳ Waiting for task {task_id} to complete...")
        
        max_wait_seconds = max_wait_hours * 3600
        start_time = time.time()
        
        while time.time() - start_time < max_wait_seconds:
            status = self.get_task_status(task_id)
            
            if not status:
                return False
            
            current_status = status['status']
            message = status['message']
            
            # 显示进度
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed:04d}s] {current_status.upper()}: {message}")
            
            if current_status == 'completed':
                print(f"🎉 Task completed successfully!")
                print(f"📁 Results saved to: {status.get('output_path', 'N/A')}")
                return True
            elif current_status == 'failed':
                error_msg = status.get('error_message', 'Unknown error')
                print(f"💥 Task failed: {error_msg}")
                return False
            
            time.sleep(check_interval)
        
        print(f"⏰ Task did not complete within {max_wait_hours} hours")
        return False
    
    def run_optimization(self, pdb_file, fasta_file, output_dir, user_id, **kwargs):
        """运行完整的优化流程"""
        print("🚀 Starting peptide optimization...")
        print(f"📄 PDB file: {pdb_file}")
        print(f"🧬 FASTA file: {fasta_file}")
        print(f"📁 Output directory: {output_dir}")
        print(f"👤 User ID: {user_id}")
        print("-" * 50)
        
        try:
            # 1. 提交任务
            task_id = self.submit_optimization(pdb_file, fasta_file, output_dir, user_id, **kwargs)
            
            # 2. 等待完成
            success = self.wait_for_completion(task_id)
            
            # 3. 返回结果
            if success:
                final_status = self.get_task_status(task_id)
                return {
                    'success': True,
                    'task_id': task_id,
                    'output_path': final_status.get('output_path'),
                    'status': final_status
                }
            else:
                return {
                    'success': False,
                    'task_id': task_id,
                    'output_path': None,
                    'status': self.get_task_status(task_id)
                }
                
        except Exception as e:
            print(f"💥 Optimization failed: {e}")
            return {
                'success': False,
                'task_id': None,
                'output_path': None,
                'error': str(e)
            }

def main():
    """示例用法"""
    print("🧪 Peptide Optimization Client Example")
    print("=" * 50)
    
    # 配置参数
    API_URL = "http://localhost:8000"
    PDB_FILE = "./input/5ffg.pdb"  # 蛋白质结构文件
    FASTA_FILE = "./input/peptide.fasta"  # 肽段序列文件
    OUTPUT_DIR = "./client_output"  # 输出目录
    USER_ID = "example_user"
    
    # 检查输入文件
    if not os.path.exists(PDB_FILE):
        print(f"❌ PDB file not found: {PDB_FILE}")
        print("请确保输入文件存在于正确位置")
        return
    
    if not os.path.exists(FASTA_FILE):
        print(f"❌ FASTA file not found: {FASTA_FILE}")
        print("请确保输入文件存在于正确位置")
        return
    
    # 创建客户端
    client = PeptideOptimizationClient(API_URL)
    
    # 运行优化
    result = client.run_optimization(
        pdb_file=PDB_FILE,
        fasta_file=FASTA_FILE,
        output_dir=OUTPUT_DIR,
        user_id=USER_ID,
        cores=4,  # 使用4个CPU核心
        cleanup=False  # 保留中间文件用于调试
    )
    
    # 显示结果
    print("\n" + "=" * 50)
    if result['success']:
        print("🎉 优化完成!")
        print(f"📋 任务ID: {result['task_id']}")
        print(f"📁 结果路径: {result['output_path']}")
        
        # 显示输出文件
        output_path = Path(result['output_path'])
        if output_path.exists():
            print("\n📄 输出文件:")
            for file in output_path.glob("*"):
                if file.is_file():
                    print(f"  - {file.name}")
        
    else:
        print("💥 优化失败!")
        if 'error' in result:
            print(f"错误: {result['error']}")
        elif result['status']:
            print(f"状态: {result['status']['status']}")
            if result['status'].get('error_message'):
                print(f"错误信息: {result['status']['error_message']}")

if __name__ == "__main__":
    main()
