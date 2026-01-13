#!/bin/bash
set -e

# Docker entrypoint script for Peptide Optimization Service

echo "=========================================="
echo "Peptide Optimization Service"
echo "=========================================="
echo "Starting at: $(date)"
echo ""

# Initialize conda
source /opt/conda/etc/profile.d/conda.sh
conda activate peptide

echo "Using Python: $(which python)"
echo "Python version: $(python --version)"
echo ""

# Default command
CMD=${1:-serve}

case "$CMD" in
    serve)
        echo "Starting API server..."
        exec python -m peptide_opt serve \
            --host ${HOST:-0.0.0.0} \
            --port ${PORT:-8000}
        ;;
    
    run)
        echo "Running peptide optimization..."
        shift
        exec python -m peptide_opt run "$@"
        ;;
    
    shell)
        echo "Starting shell..."
        exec /bin/bash
        ;;
    
    *)
        echo "Unknown command: $CMD"
        echo "Available commands: serve, run, shell"
        exit 1
        ;;
esac
