#!/usr/bin/env python3
"""
命令行入口点
支持 python -m peptide_opt 方式运行
"""

import argparse
import os
import sys
import uvicorn


def main():
    """主入口函数"""
    parser = argparse.ArgumentParser(
        prog="peptide-opt",
        description="Peptide Optimization Service"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # serve 子命令 - 启动 API 服务
    serve_parser = subparsers.add_parser("serve", help="Start the API server")
    serve_parser.add_argument(
        "--host", 
        default="0.0.0.0", 
        help="Host to bind (default: 0.0.0.0)"
    )
    serve_parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="Port to bind (default: 8000)"
    )
    serve_parser.add_argument(
        "--reload", 
        action="store_true", 
        help="Enable auto-reload for development"
    )
    serve_parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )
    
    # run 子命令 - 直接运行优化
    run_parser = subparsers.add_parser("run", help="Run peptide optimization directly")
    run_parser.add_argument(
        "--input-dir",
        default="./data/input",
        help="Input directory containing peptide.fasta and receptor PDB"
    )
    run_parser.add_argument(
        "--output-dir",
        default="./data/output",
        help="Output directory for results"
    )
    run_parser.add_argument(
        "--cores",
        type=int,
        default=int(os.getenv("CPU_CORES", "4")),
        help="Number of CPU cores for docking (default: from CPU_CORES env or 4, ~20%% of host)"
    )
    run_parser.add_argument(
        "--step",
        type=int,
        choices=range(1, 9),
        help="Run specific step (1-8)"
    )
    run_parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep intermediate files"
    )
    
    args = parser.parse_args()
    
    if args.command == "serve":
        # 启动 API 服务
        uvicorn.run(
            "peptide_opt.api.app:create_app",
            factory=True,
            host=args.host,
            port=args.port,
            reload=args.reload,
            workers=args.workers if not args.reload else 1,
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
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
