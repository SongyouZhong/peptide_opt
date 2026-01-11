#!/bin/bash

# Peptide Optimization Docker 一键部署脚本
# 简化 docker-compose 操作

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
info() { echo -e "${BLUE}[INFO]${NC} $1"; }

# 检查 Docker
check_docker() {
    if ! command -v docker &> /dev/null; then
        error "Docker 未安装，请先安装 Docker"
    fi
    
    if ! docker info &> /dev/null; then
        error "Docker 服务未运行或当前用户无权限"
    fi
}

# 检查 GPU 支持
check_gpu() {
    if command -v nvidia-smi &> /dev/null; then
        if nvidia-smi &> /dev/null; then
            echo "gpu"
            return
        fi
    fi
    echo "cpu"
}

# 显示帮助
show_help() {
    echo "Peptide Optimization Docker 部署脚本"
    echo ""
    echo "用法: $0 <命令> [选项]"
    echo ""
    echo "命令:"
    echo "  start       启动服务"
    echo "  stop        停止服务"
    echo "  restart     重启服务"
    echo "  status      查看服务状态"
    echo "  logs        查看日志"
    echo "  build       构建镜像"
    echo "  clean       清理容器和镜像"
    echo "  shell       进入容器 shell"
    echo "  health      检查服务健康状态"
    echo ""
    echo "选项:"
    echo "  --gpu       使用 GPU 版本"
    echo "  --standalone  使用独立模式（连接外部服务）"
    echo "  -f          跟随日志输出"
    echo ""
    echo "示例:"
    echo "  $0 start              # 启动完整服务栈"
    echo "  $0 start --gpu        # 启动 GPU 版本"
    echo "  $0 start --standalone # 仅启动应用服务"
    echo "  $0 logs -f            # 查看实时日志"
}

# 选择 compose 文件
get_compose_file() {
    local mode="$1"
    local gpu="$2"
    
    if [ "$mode" = "standalone" ]; then
        echo "docker-compose.standalone.yml"
    elif [ "$gpu" = "true" ]; then
        echo "docker-compose.gpu.yml"
    else
        echo "docker-compose.yml"
    fi
}

# 启动服务
cmd_start() {
    local compose_file=$(get_compose_file "$MODE" "$USE_GPU")
    log "使用配置文件: $compose_file"
    
    # 检查 .env 文件
    if [ ! -f ".env" ]; then
        warn ".env 文件不存在，复制模板..."
        cp .env.docker .env
    fi
    
    log "启动服务..."
    docker compose -f "$compose_file" up -d
    
    log "等待服务就绪..."
    sleep 5
    cmd_status
}

# 停止服务
cmd_stop() {
    local compose_file=$(get_compose_file "$MODE" "$USE_GPU")
    log "停止服务..."
    docker compose -f "$compose_file" down
    log "服务已停止"
}

# 重启服务
cmd_restart() {
    cmd_stop
    cmd_start
}

# 查看状态
cmd_status() {
    local compose_file=$(get_compose_file "$MODE" "$USE_GPU")
    echo ""
    info "服务状态:"
    docker compose -f "$compose_file" ps
    echo ""
}

# 查看日志
cmd_logs() {
    local compose_file=$(get_compose_file "$MODE" "$USE_GPU")
    local follow_flag=""
    
    if [ "$FOLLOW_LOGS" = "true" ]; then
        follow_flag="-f"
    fi
    
    docker compose -f "$compose_file" logs $follow_flag peptide-opt
}

# 构建镜像
cmd_build() {
    local compose_file=$(get_compose_file "$MODE" "$USE_GPU")
    log "构建镜像..."
    docker compose -f "$compose_file" build --no-cache
    log "构建完成"
}

# 清理
cmd_clean() {
    local compose_file=$(get_compose_file "$MODE" "$USE_GPU")
    
    warn "这将删除容器和网络，数据卷将保留"
    read -p "确认继续？[y/N] " confirm
    
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        log "清理容器和网络..."
        docker compose -f "$compose_file" down --rmi local
        log "清理完成"
    else
        log "已取消"
    fi
}

# 进入容器
cmd_shell() {
    local compose_file=$(get_compose_file "$MODE" "$USE_GPU")
    log "进入容器..."
    docker compose -f "$compose_file" exec peptide-opt bash
}

# 健康检查
cmd_health() {
    echo ""
    info "健康检查:"
    
    # 检查 API
    echo -n "  API 服务: "
    if curl -s -f http://localhost:8001/ > /dev/null 2>&1; then
        echo -e "${GREEN}正常${NC}"
    else
        echo -e "${RED}异常${NC}"
    fi
    
    # 检查数据库
    echo -n "  数据库:   "
    if docker compose exec -T postgres pg_isready -U admin > /dev/null 2>&1; then
        echo -e "${GREEN}正常${NC}"
    else
        echo -e "${YELLOW}未运行或连接外部${NC}"
    fi
    
    # 检查 SeaweedFS
    echo -n "  SeaweedFS: "
    if curl -s -f http://localhost:9333/cluster/status > /dev/null 2>&1; then
        echo -e "${GREEN}正常${NC}"
    else
        echo -e "${YELLOW}未运行或连接外部${NC}"
    fi
    
    echo ""
}

# 主函数
main() {
    check_docker
    
    # 解析参数
    COMMAND=""
    USE_GPU="false"
    MODE="full"
    FOLLOW_LOGS="false"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            start|stop|restart|status|logs|build|clean|shell|health)
                COMMAND="$1"
                shift
                ;;
            --gpu)
                USE_GPU="true"
                shift
                ;;
            --standalone)
                MODE="standalone"
                shift
                ;;
            -f)
                FOLLOW_LOGS="true"
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                error "未知参数: $1"
                ;;
        esac
    done
    
    if [ -z "$COMMAND" ]; then
        show_help
        exit 1
    fi
    
    # 执行命令
    case $COMMAND in
        start)   cmd_start ;;
        stop)    cmd_stop ;;
        restart) cmd_restart ;;
        status)  cmd_status ;;
        logs)    cmd_logs ;;
        build)   cmd_build ;;
        clean)   cmd_clean ;;
        shell)   cmd_shell ;;
        health)  cmd_health ;;
    esac
}

main "$@"
