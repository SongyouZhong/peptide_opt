#!/usr/bin/env python3
"""
Test script for Peptide Optimization API
测试肽段优化API的Python脚本
"""

import requests
import json
import time
import os
from pathlib import Path

class PeptideOptimizationAPITester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        
    def test_health_check(self):
        """测试健康检查端点"""
        print("=== Testing Health Check ===")
        try:
            response = requests.get(f"{self.base_url}/health")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.json()}")
            return response.status_code == 200
        except Exception as e:
            print(f"Health check failed: {e}")
            return False
    
    def test_root_endpoint(self):
        """测试根端点"""
        print("\n=== Testing Root Endpoint ===")
        try:
            response = requests.get(f"{self.base_url}/")
            print(f"Status Code: {response.status_code}")
            print(f"Response: {json.dumps(response.json(), indent=2)}")
            return response.status_code == 200
        except Exception as e:
            print(f"Root endpoint test failed: {e}")
            return False
    
    def start_optimization_task(self, pdb_file_path, fasta_file_path, output_path, user_id, cores=12, cleanup=True):
        """启动优化任务"""
        print("\n=== Starting Optimization Task ===")
        
        # 验证输入文件存在
        if not os.path.exists(pdb_file_path):
            print(f"Error: PDB file not found: {pdb_file_path}")
            return None
            
        if not os.path.exists(fasta_file_path):
            print(f"Error: FASTA file not found: {fasta_file_path}")
            return None
        
        # 准备请求数据
        data = {
            "pdb_file_path": pdb_file_path,
            "fasta_file_path": fasta_file_path,
            "output_path": output_path,
            "user_id": user_id,
            "cores": cores,
            "cleanup": cleanup
        }
        
        try:
            response = requests.post(f"{self.base_url}/optimize", data=data)
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Response: {json.dumps(result, indent=2)}")
                return result.get("task_id")
            else:
                print(f"Error Response: {response.text}")
                return None
                
        except Exception as e:
            print(f"Failed to start optimization task: {e}")
            return None
    
    def check_task_status(self, task_id):
        """检查任务状态"""
        try:
            response = requests.get(f"{self.base_url}/status/{task_id}")
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error checking task status: {response.text}")
                return None
        except Exception as e:
            print(f"Failed to check task status: {e}")
            return None
    
    def monitor_task(self, task_id, max_wait_time=3600, check_interval=30):
        """监控任务执行"""
        print(f"\n=== Monitoring Task {task_id} ===")
        
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            status = self.check_task_status(task_id)
            if status:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Status: {status['status']} - {status['message']}")
                
                if status['status'] == 'completed':
                    print(f"Task completed successfully!")
                    print(f"Output path: {status.get('output_path', 'N/A')}")
                    return True
                elif status['status'] == 'failed':
                    print(f"Task failed: {status.get('error_message', 'Unknown error')}")
                    return False
            
            if status and status['status'] in ['completed', 'failed']:
                break
                
            time.sleep(check_interval)
        
        print("Task monitoring timed out")
        return False
    
    def get_user_tasks(self, user_id):
        """获取用户任务列表"""
        print(f"\n=== Getting Tasks for User {user_id} ===")
        try:
            response = requests.get(f"{self.base_url}/user/{user_id}/tasks")
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Total tasks: {result['total_tasks']}")
                for task in result['tasks']:
                    print(f"  Task {task['task_id']}: {task['status']} - {task['message']}")
                return result
            else:
                print(f"Error: {response.text}")
                return None
        except Exception as e:
            print(f"Failed to get user tasks: {e}")
            return None
    
    def run_full_test(self, pdb_file_path, fasta_file_path, output_path, user_id):
        """运行完整测试"""
        print("🧪 Starting Full API Test")
        print("=" * 50)
        
        # 1. 健康检查
        if not self.test_health_check():
            print("❌ Health check failed. Is the server running?")
            return False
        
        # 2. 测试根端点
        if not self.test_root_endpoint():
            print("❌ Root endpoint test failed")
            return False
        
        # 3. 启动优化任务
        task_id = self.start_optimization_task(
            pdb_file_path=pdb_file_path,
            fasta_file_path=fasta_file_path,
            output_path=output_path,
            user_id=user_id,
            cores=4,  # 使用较少的核心数进行测试
            cleanup=False  # 保留中间文件用于调试
        )
        
        if not task_id:
            print("❌ Failed to start optimization task")
            return False
        
        print(f"✅ Optimization task started with ID: {task_id}")
        
        # 4. 监控任务执行（缩短等待时间用于测试）
        success = self.monitor_task(task_id, max_wait_time=1800, check_interval=10)
        
        # 5. 获取用户任务列表
        self.get_user_tasks(user_id)
        
        if success:
            print("\n🎉 All tests passed!")
            return True
        else:
            print("\n❌ Some tests failed")
            return False

def main():
    """主测试函数"""
    # 配置测试参数
    BASE_URL = "http://localhost:8000"
    
    # 使用项目中的示例文件
    PDB_FILE = "./input/5ffg.pdb"
    FASTA_FILE = "./input/peptide.fasta"
    OUTPUT_DIR = "./test_output"
    USER_ID = "test_user_001"
    
    # 创建输出目录
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # 验证输入文件
    if not os.path.exists(PDB_FILE):
        print(f"❌ PDB file not found: {PDB_FILE}")
        print("Please make sure the input files are in the correct location")
        return
    
    if not os.path.exists(FASTA_FILE):
        print(f"❌ FASTA file not found: {FASTA_FILE}")
        print("Please make sure the input files are in the correct location")
        return
    
    # 创建测试器实例
    tester = PeptideOptimizationAPITester(BASE_URL)
    
    print("🚀 Peptide Optimization API Tester")
    print(f"🌐 Server URL: {BASE_URL}")
    print(f"📁 PDB File: {PDB_FILE}")
    print(f"📁 FASTA File: {FASTA_FILE}")
    print(f"📁 Output Directory: {OUTPUT_DIR}")
    print(f"👤 User ID: {USER_ID}")
    print()
    
    # 运行完整测试
    tester.run_full_test(
        pdb_file_path=os.path.abspath(PDB_FILE),
        fasta_file_path=os.path.abspath(FASTA_FILE),
        output_path=os.path.abspath(OUTPUT_DIR),
        user_id=USER_ID
    )

if __name__ == "__main__":
    main()
