#!/bin/bash

# Peptide Optimization 服务启动脚本
# 用于在本地启动peptide_opt服务并保持后台运行

set -e  # 遇到错误立即退出

# 配置变量
PROJECT_DIR="/home/davis/projects/peptide_opt"
micromamba_ENV_NAME="peptide"
SERVICE_PORT=8001
LOG_DIR="/home/davis/projects/serverlogs/peptide_opt"
PID_FILE="$LOG_DIR/peptide_opt.pid"
LOG_FILE="$LOG_DIR/peptide_opt.log"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

# 创建必要的目录
create_directories() {
    log "创建必要的目录..."
    mkdir -p "$LOG_DIR"
    mkdir -p "$PROJECT_DIR/middlefiles"
    mkdir -p "$PROJECT_DIR/input"
    mkdir -p "$PROJECT_DIR/logs"
}

# 检查micromamba环境
check_micromamba_env() {
    log "检查micromamba环境: $micromamba_ENV_NAME"
    
    if ! micromamba env list | grep -q "$micromamba_ENV_NAME"; then
        warn "micromamba环境 $micromamba_ENV_NAME 不存在，正在创建..."
        
        # 检查环境文件
        if [ -f "$PROJECT_DIR/environment.yml" ]; then
            log "使用environment.yml创建micromamba环境..."
            micromamba env create -f "$PROJECT_DIR/environment.yml"
        else
            error "未找到environment.yml文件"
            exit 1
        fi
    else
        log "micromamba环境 $micromamba_ENV_NAME 已存在"
    fi
}

# 检查端口是否被占用
check_port() {
    log "检查端口 $SERVICE_PORT 是否可用..."
    
    if lsof -i:$SERVICE_PORT > /dev/null 2>&1; then
        warn "端口 $SERVICE_PORT 已被占用"
        
        # 尝试找到占用端口的进程
        local pid=$(lsof -ti:$SERVICE_PORT)
        if [ ! -z "$pid" ]; then
            log "找到占用端口的进程: $pid"
            local process_info=$(ps -p $pid -o comm= 2>/dev/null || echo "unknown")
            log "进程信息: $process_info"
            
            read -p "是否要终止占用端口的进程? (y/N): " choice
            case "$choice" in 
                y|Y ) 
                    log "终止进程 $pid..."
                    kill -9 $pid
                    sleep 2
                    ;;
                * ) 
                    error "端口被占用，无法启动服务"
                    exit 1
                    ;;
            esac
        fi
    else
        log "端口 $SERVICE_PORT 可用"
    fi
}

# 检查服务是否正在运行
is_service_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p $pid > /dev/null 2>&1; then
            return 0  # 服务正在运行
        else
            log "PID文件存在但进程不存在，清理PID文件"
            rm -f "$PID_FILE"
        fi
    fi
    return 1  # 服务未运行
}

# 启动服务
start_service() {
    log "启动Peptide Optimization服务..."
    
    # 切换到项目目录
    cd "$PROJECT_DIR"
    
    # 激活micromamba环境并启动服务
    log "激活micromamba环境并启动FastAPI服务..."
    
    # 使用nohup在后台启动服务
    nohup micromamba run -n "$micromamba_ENV_NAME" python main.py > "$LOG_FILE" 2>&1 &
    local service_pid=$!
    
    # 保存PID
    echo $service_pid > "$PID_FILE"
    
    log "服务启动中... PID: $service_pid"
    log "日志文件: $LOG_FILE"
    
    # 等待服务启动
    sleep 5
    
    # 检查服务是否成功启动
    if is_service_running; then
        log "✅ Peptide Optimization服务启动成功!"
        log "服务地址: http://localhost:$SERVICE_PORT"
        log "API文档: http://localhost:$SERVICE_PORT/docs"
        
        # 显示最近的日志
        log "最近的日志输出:"
        tail -n 10 "$LOG_FILE" | sed 's/^/  /'
        
    else
        error "❌ 服务启动失败"
        if [ -f "$LOG_FILE" ]; then
            error "最近的错误日志:"
            tail -n 20 "$LOG_FILE" | sed 's/^/  /'
        fi
        exit 1
    fi
}

# 停止服务
stop_service() {
    log "停止Peptide Optimization服务..."
    
    if is_service_running; then
        local pid=$(cat "$PID_FILE")
        log "终止进程: $pid"
        
        # 优雅关闭
        kill -TERM $pid
        
        # 等待进程结束
        local count=0
        while ps -p $pid > /dev/null 2>&1 && [ $count -lt 10 ]; do
            sleep 1
            count=$((count + 1))
        done
        
        # 如果进程仍在运行，强制终止
        if ps -p $pid > /dev/null 2>&1; then
            log "强制终止进程..."
            kill -9 $pid
        fi
        
        rm -f "$PID_FILE"
        log "✅ 服务已停止"
    else
        log "服务未运行"
    fi
}

# 重启服务
restart_service() {
    log "重启Peptide Optimization服务..."
    stop_service
    sleep 2
    start_service
}

# 查看服务状态
status_service() {
    log "检查Peptide Optimization服务状态..."
    
    if is_service_running; then
        local pid=$(cat "$PID_FILE")
        log "✅ 服务正在运行 (PID: $pid)"
        log "服务地址: http://localhost:$SERVICE_PORT"
        
        # 检查端口是否监听
        if lsof -i:$SERVICE_PORT > /dev/null 2>&1; then
            log "✅ 端口 $SERVICE_PORT 正在监听"
        else
            warn "⚠️  端口 $SERVICE_PORT 未监听"
        fi
        
        # 显示最近的日志
        if [ -f "$LOG_FILE" ]; then
            log "最近的日志 (最后5行):"
            tail -n 5 "$LOG_FILE" | sed 's/^/  /'
        fi
        
    else
        log "❌ 服务未运行"
    fi
}

# 查看日志
logs_service() {
    if [ -f "$LOG_FILE" ]; then
        log "显示实时日志 (Ctrl+C退出):"
        tail -f "$LOG_FILE"
    else
        error "日志文件不存在: $LOG_FILE"
    fi
}

# 主函数
main() {
    case "${1:-start}" in
        start)
            create_directories
            check_micromamba_env
            
            if is_service_running; then
                log "服务已在运行"
                status_service
            else
                check_port
                start_service
            fi
            ;;
        stop)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        status)
            status_service
            ;;
        logs)
            logs_service
            ;;
        *)
            echo "用法: $0 {start|stop|restart|status|logs}"
            echo ""
            echo "命令说明:"
            echo "  start   - 启动服务"
            echo "  stop    - 停止服务"  
            echo "  restart - 重启服务"
            echo "  status  - 查看状态"
            echo "  logs    - 查看日志"
            exit 1
            ;;
    esac
}

main "$@"
