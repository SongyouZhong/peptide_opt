#!/bin/bash

# Peptide Optimization Docker 构建脚本
# 用于构建和推送 Docker 镜像

set -e

# 默认配置
REGISTRY="${REGISTRY:-}"
IMAGE_NAME="${IMAGE_NAME:-peptide-opt}"
TAG="${TAG:-latest}"
BUILD_TYPE="${BUILD_TYPE:-cpu}"  # cpu 或 gpu

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[BUILD]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# 显示帮助
show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -t, --tag TAG        镜像标签 (默认: latest)"
    echo "  -r, --registry REG   镜像仓库地址"
    echo "  -n, --name NAME      镜像名称 (默认: peptide-opt)"
    echo "  --gpu                构建 GPU 版本"
    echo "  --push               构建后推送到仓库"
    echo "  --no-cache           不使用构建缓存"
    echo "  -h, --help           显示帮助"
    echo ""
    echo "Examples:"
    echo "  $0                              # 构建 CPU 版本"
    echo "  $0 --gpu                        # 构建 GPU 版本"
    echo "  $0 -t v1.0.0 --push             # 构建并推送带版本标签"
    echo "  $0 -r myregistry.io -t v1.0.0   # 使用自定义仓库"
}

# 解析参数
PUSH=false
NO_CACHE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--tag)
            TAG="$2"
            shift 2
            ;;
        -r|--registry)
            REGISTRY="$2"
            shift 2
            ;;
        -n|--name)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --gpu)
            BUILD_TYPE="gpu"
            shift
            ;;
        --push)
            PUSH=true
            shift
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
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

# 构建完整镜像名
if [ -n "$REGISTRY" ]; then
    FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}"
else
    FULL_IMAGE="${IMAGE_NAME}"
fi

# 选择 Dockerfile
if [ "$BUILD_TYPE" = "gpu" ]; then
    DOCKERFILE="Dockerfile.gpu"
    FULL_IMAGE="${FULL_IMAGE}:${TAG}-gpu"
else
    DOCKERFILE="Dockerfile"
    FULL_IMAGE="${FULL_IMAGE}:${TAG}"
fi

# 检查 Dockerfile 存在
if [ ! -f "$DOCKERFILE" ]; then
    error "Dockerfile 不存在: $DOCKERFILE"
fi

log "=========================================="
log "构建配置:"
log "  镜像名称: ${FULL_IMAGE}"
log "  Dockerfile: ${DOCKERFILE}"
log "  构建类型: ${BUILD_TYPE}"
log "  推送: ${PUSH}"
log "=========================================="

# 构建镜像
log "开始构建镜像..."
docker build \
    ${NO_CACHE} \
    -f "$DOCKERFILE" \
    -t "$FULL_IMAGE" \
    --build-arg BUILD_DATE="$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    --build-arg VERSION="${TAG}" \
    .

log "镜像构建成功: ${FULL_IMAGE}"

# 同时标记 latest
if [ "$TAG" != "latest" ]; then
    if [ "$BUILD_TYPE" = "gpu" ]; then
        LATEST_TAG="${FULL_IMAGE%:*}:latest-gpu"
    else
        LATEST_TAG="${FULL_IMAGE%:*}:latest"
    fi
    docker tag "$FULL_IMAGE" "$LATEST_TAG"
    log "已标记为: ${LATEST_TAG}"
fi

# 推送镜像
if [ "$PUSH" = true ]; then
    if [ -z "$REGISTRY" ]; then
        warn "未指定仓库地址，跳过推送"
    else
        log "推送镜像到仓库..."
        docker push "$FULL_IMAGE"
        if [ "$TAG" != "latest" ]; then
            docker push "$LATEST_TAG"
        fi
        log "镜像推送成功"
    fi
fi

log "=========================================="
log "构建完成!"
log "运行命令: docker run -d -p 8001:8001 ${FULL_IMAGE}"
log "=========================================="
