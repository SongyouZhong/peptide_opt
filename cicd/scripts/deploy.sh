#!/bin/bash

# Peptide Optimization 一键部署脚本
# 统一管理服务的启动、停止和状态检查

set -e

# 项目路径
PROJECT_DIR="/home/davis/projects/peptide_opt"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# 检查脚本是否存在
check_scripts() {
    local missing_scripts=()
    
    if [ ! -f "$SCRIPT_DIR/start_peptide_service.sh" ]; then
        missing_scripts+=("start_peptide_service.sh")
    fi
    
    if [ ${#missing_scripts[@]} -ne 0 ]; then
        error "缺少必要的脚本文件:"
        for script in "${missing_scripts[@]}"; do
            echo "  - $script"
        done
        exit 1
    fi
}

# 启动服务
start_all() {
    log "🚀 启动Peptide Optimization服务..."
    
    "$SCRIPT_DIR/start_peptide_service.sh" start
    
    log "✅ 服务启动完成!"
    echo ""
    status_all
}

# 停止服务
stop_all() {
    log "🛑 停止Peptide Optimization服务..."
    
    "$SCRIPT_DIR/start_peptide_service.sh" stop
    
    log "✅ 服务已停止"
}

# 重启服务
restart_all() {
    log "🔄 重启Peptide Optimization服务..."
    stop_all
    sleep 3
    start_all
}

# 查看状态
status_all() {
    log "📊 服务状态检查..."
    echo ""
    
    "$SCRIPT_DIR/start_peptide_service.sh" status
    
    echo ""
    log "状态检查完成"
}

# 查看日志
logs_all() {
    log "📋 显示服务日志..."
    "$SCRIPT_DIR/start_peptide_service.sh" logs
}

# 测试连接
test_connection() {
    log "🔍 测试服务连接..."
    
    local service_url="http://localhost:8001"
    
    # 测试健康检查端点
    log "测试健康检查端点..."
    if curl -s "$service_url/health" > /dev/null; then
        log "✅ 健康检查端点正常"
        
        # 显示健康状态
        local health_response=$(curl -s "$service_url/health")
        echo "健康状态: $health_response"
    else
        error "❌ 健康检查端点无响应"
    fi
    
    # 测试根路径
    log "测试根路径..."
    if curl -s "$service_url/" > /dev/null; then
        log "✅ 根路径正常"
        
        # 显示根路径响应
        local root_response=$(curl -s "$service_url/")
        echo "根路径响应: $root_response"
    else
        error "❌ 根路径无响应"
    fi
    
    log "API文档地址: $service_url/docs"
}

# 环境检查
check_environment() {
    log "🔍 环境检查..."
    
    # 检查micromamba
    if command -v micromamba &> /dev/null; then
        log "✅ micromamba已安装: $(micromamba --version)"
    else
        error "❌ micromamba未安装"
        return 1
    fi
    
    # 检查Python
    if command -v python &> /dev/null; then
        log "✅ Python已安装: $(python --version)"
    else
        error "❌ Python未安装"
        return 1
    fi
    
    # 检查项目文件
    local required_files=("main.py" "peptide_optimizer.py" "environment.yml")
    for file in "${required_files[@]}"; do
        if [ -f "$PROJECT_DIR/$file" ]; then
            log "✅ 找到文件: $file"
        else
            error "❌ 缺少文件: $file"
            return 1
        fi
    done
    
    log "✅ 环境检查通过"
}

# 配置管理
config_service() {
    log "⚙️  服务配置管理..."
    
    echo "当前配置:"
    echo "  项目目录: $PROJECT_DIR"
    echo "  服务端口: 8001"
    echo "  日志目录: /home/davis/projects/serverlogs"
    echo "  micromamba环境: peptide"
    echo ""
    
    read -p "是否要修改配置? (y/N): " choice
    case "$choice" in 
        y|Y ) 
            log "配置修改功能待实现..."
            ;;
        * ) 
            log "保持当前配置"
            ;;
    esac
}

# 显示帮助信息
show_help() {
    echo "Peptide Optimization 部署管理脚本"
    echo ""
    echo "用法: $0 {start|stop|restart|status|logs|test|check|config}"
    echo ""
    echo "命令说明:"
    echo "  start    - 启动服务"
    echo "  stop     - 停止服务"
    echo "  restart  - 重启服务"
    echo "  status   - 查看状态"
    echo "  logs     - 查看日志"
    echo "  test     - 测试连接"
    echo "  check    - 环境检查"
    echo "  config   - 配置管理"
    echo ""
    echo "示例:"
    echo "  $0 start     # 启动服务"
    echo "  $0 status    # 查看状态"
    echo "  $0 logs      # 查看实时日志"
}

# 主函数
main() {
    # 检查必要的脚本
    check_scripts
    
    case "${1:-help}" in
        start)
            start_all
            ;;
        stop)
            stop_all
            ;;
        restart)
            restart_all
            ;;
        status)
            status_all
            ;;
        logs)
            logs_all
            ;;
        test)
            test_connection
            ;;
        check)
            check_environment
            ;;
        config)
            config_service
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            error "未知命令: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
