StanleyCurtis200268: 请分析我的代码，如果使用命令行参数来调用这个方法，我需要提供什么参数，请你提供示例

GitHub Copilot: 分析你的代码后，这是一个肽段优化流程的python3脚本。以下是命令行参数的详细说明和使用示例：

## 命令行参数说明

- `--input_dir`: 输入目录（默认: input）
- `--output_dir`: 输出目录（默认: output）
- `--proteinmpnn_dir`: ProteinMPNN目录（默认: ProteinMPNN）
- `--cores`: 对接使用的CPU核心数（默认: 12）
- `--step`: 运行特定步骤（1-8），可选参数
- `--no-cleanup`: 保留中间文件，用于调试

## 使用示例

### 1. 运行完整流程（默认参数）
```bash
python3 peptide_optimizer.py
```

### 2. 自定义目录和核心数
```bash
python3 peptide_optimizer.py --input_dir ./my_input --output_dir ./my_output --cores 8
```

### 3. 指定ProteinMPNN路径
```bash
python3 peptide_optimizer.py --proteinmpnn_dir /path/to/ProteinMPNN/ --cores 16
```

### 4. 运行特定步骤
```bash
# 只运行步骤1（结构预测）
python3 peptide_optimizer.py --step 1

# 只运行步骤3（分子对接）
python3 peptide_optimizer.py --step 3 --cores 8

# 只运行步骤8（最终分析）
python3 peptide_optimizer.py --step 8 --input_dir ./custom_input
```

### 5. 保留中间文件用于调试
```bash
python3 peptide_optimizer.py --no-cleanup --cores 8
```

### 6. 完整参数示例
```bash
python3 peptide_optimizer.py \
    --input_dir ./input_data \
    --output_dir ./results \
    --proteinmpnn_dir ./ProteinMPNN/ \
    --cores 16 \
    --no-cleanup
```

## 输入文件要求

根据代码分析，输入目录需要包含：
- `peptide.fasta`: 肽段序列文件
- `5ffg.pdb`: 受体蛋白质结构文件

## 8个步骤说明

1. **步骤1**: 使用OmegaFold预测肽段结构
2. **步骤2**: 添加氢原子到受体和肽段
3. **步骤3**: 分子对接
4. **步骤4**: 原子排序和添加氢原子
5. **步骤5**: 计算结合亲和力评分
6. **步骤6**: 合并肽段和蛋白质结构
7. **步骤7**: 使用ProteinMPNN进行序列优化
8. **步骤8**: 最终分析和报告生成

使用`--step`参数可以单独运行任意步骤，这对于调试或重新运行特定部分很有用。