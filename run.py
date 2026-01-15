#!/usr/bin/env python3
"""
开发环境快速启动脚本

使用方法:
    python run.py              # 启动 API 服务 (默认 --reload)
    python run.py serve        # 启动 API 服务
    python run.py serve --port 8080  # 指定端口
    python run.py run          # 运行优化流程
    python run.py run --input-dir ./data/input --output-dir ./data/output
"""

import os
import sys

# 将 src 目录添加到 Python 路径，确保可以导入 peptide_opt
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)


def main():
    """主入口函数"""
    import argparse
    import uvicorn
    
    parser = argparse.ArgumentParser(
        prog="peptide-opt",
        description="Peptide Optimization Service - 开发环境快速启动"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # serve 子命令 - 启动 API 服务
    serve_parser = subparsers.add_parser("serve", help="启动 API 服务")
    serve_parser.add_argument(
        "--host", 
        default="0.0.0.0", 
        help="绑定主机 (默认: 0.0.0.0)"
    )
    serve_parser.add_argument(
        "--port", 
        type=int, 
        default=8022, 
        help="绑定端口 (默认: 8022)"
    )
    serve_parser.add_argument(
        "--reload", 
        action="store_true",
        default=True,
        help="启用自动重载 (开发模式默认开启)"
    )
    serve_parser.add_argument(
        "--no-reload",
        action="store_true",
        help="禁用自动重载"
    )
    serve_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="工作进程数 (默认: 1)"
    )
    serve_parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="日志级别 (默认: info)"
    )
    
    # run 子命令 - 直接运行优化
    run_parser = subparsers.add_parser("run", help="直接运行肽段优化")
    run_parser.add_argument(
        "--input-dir",
        default="./data/input",
        help="输入目录，包含 peptide.fasta 和受体 PDB 文件"
    )
    run_parser.add_argument(
        "--output-dir",
        default="./data/output",
        help="输出目录"
    )
    run_parser.add_argument(
        "--cores",
        type=int,
        default=None,  # None 表示自动检测（80% CPU）
        help="对接使用的 CPU 核心数 (默认: 自动检测，使用 80%% 的可用 CPU)"
    )
    run_parser.add_argument(
        "--step",
        type=int,
        choices=range(1, 9),
        help="运行特定步骤 (1-8)"
    )
    run_parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="保留中间文件"
    )
    
    args = parser.parse_args()
    
    # 如果没有指定命令，默认启动 API 服务
    if args.command is None:
        print("🚀 默认启动 API 服务 (开发模式，自动重载已启用)")
        print("   访问 API 文档: http://localhost:8022/docs")
        print("   按 Ctrl+C 停止服务\n")
        uvicorn.run(
            "peptide_opt.api.app:create_app",
            factory=True,
            host="0.0.0.0",
            port=8022,
            reload=True,
            log_level="info",
        )
    elif args.command == "serve":
        # 启动 API 服务
        reload_enabled = args.reload and not args.no_reload
        print(f"🚀 启动 API 服务")
        print(f"   主机: {args.host}")
        print(f"   端口: {args.port}")
        print(f"   自动重载: {'开启' if reload_enabled else '关闭'}")
        print(f"   访问 API 文档: http://{args.host if args.host != '0.0.0.0' else 'localhost'}:{args.port}/docs")
        print(f"   按 Ctrl+C 停止服务\n")
        uvicorn.run(
            "peptide_opt.api.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=reload_enabled,
            workers=args.workers if not reload_enabled else 1,
            log_level=args.log_level,
        )
    elif args.command == "run":
        # 直接运行优化
        from peptide_opt.cli import run_optimizer
        run_optimizer(
            input_dir=args.input_dir,
            output_dir=args.output_dir,
            cores=args.cores,
            step=args.step,
            cleanup=not args.no_cleanup
        )


if __name__ == "__main__":
    main()
