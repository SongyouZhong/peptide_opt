# 肽段优化程序 - Python整合版

这个程序将原来分散在多个shell脚本和Python文件中的肽段优化流程整合到了一个统一的Python程序中。

## 主要特性

- **统一的Python接口**: 所有步骤都通过Python控制
- **模块化设计**: 每个步骤都可以单独运行
- **详细的日志输出**: 跟踪每个步骤的执行状态
- **错误处理**: 完善的异常处理和错误提示
- **灵活配置**: 支持自定义参数

## 文件说明

- `peptide_optimizer.py`: 主要的优化程序类
- `run_optimization.py`: 简化的运行脚本
- `requirements.txt`: Python依赖包列表

## 安装依赖

### 1. Python包
```bash
pip install -r requirements.txt
```

### 2. PyMOL
```bash
conda install -c conda-forge -c schrodinger pymol-bundle
```

### 3. 外部软件
确保以下软件已安装并在PATH中:
- OmegaFold
- AutoDock工具套件 (prepare_receptor, prepare_ligand, agfr, adcp)
- AutoDock Vina
- ProteinMPNN

## 使用方法

### 基本使用
```bash
python run_optimization.py
```

### 高级使用
```bash
# 运行完整流程（默认会清理中间文件）
python peptide_optimizer.py

# 保留中间文件（用于调试）
python peptide_optimizer.py --no-cleanup

# 只运行特定步骤
python peptide_optimizer.py --step 1  # 只运行步骤1
python peptide_optimizer.py --step 3  # 只运行步骤3

# 自定义参数
python peptide_optimizer.py --input_dir ./my_input --output_dir ./my_output --cores 8

# 手动清理中间文件
rm -rf ./middlefiles
```

## 输入文件

需要在 `input/` 目录中准备:
- `peptide.fasta`: 肽段序列文件
- `5ffg.pdb`: 目标蛋白质PDB文件

## 输出文件

结果保存在 `output/` 目录中:
- `result.csv`: 详细的分析报告
- `complex1.pdb - complex10.pdb`: 优化后的复合物结构

## 中间文件管理

程序会在 `middlefiles/` 目录中生成大量中间文件：
```
./middlefiles/
├── peptide.pdb                       # OmegaFold预测的肽段结构
├── receptor.pdb, receptorH.pdb       # 处理后的受体结构
├── peptideH.pdb                      # 添加氢原子的肽段
├── *.pdbqt                           # AutoDock格式文件
├── complex.trg, complex.log          # 对接配置文件
├── peptide_ranked_*.pdb              # 对接结果
├── score_rank_1_10.dat               # 亲和力评分
└── pmpnn/                            # ProteinMPNN工作目录
    ├── complex1/
    ├── complex2/
    └── ...
```

**默认行为**: 程序成功完成后会自动删除 `middlefiles/` 目录
**调试模式**: 使用 `--no-cleanup` 参数可以保留中间文件

## 流程步骤

1. **结构预测**: 使用OmegaFold预测肽段3D结构
2. **氢原子添加**: 为分子对接准备结构
3. **分子对接**: 使用AutoDock进行蛋白质-肽段对接
4. **原子排序**: 整理对接结果
5. **亲和力评分**: 使用Vina计算结合亲和力
6. **结构合并**: 准备ProteinMPNN输入
7. **序列优化**: 使用ProteinMPNN优化肽段序列
8. **最终分析**: 生成详细报告

## 故障排除

### 常见问题

1. **导入错误**: 确保所有Python依赖都已安装
2. **命令未找到**: 确保外部软件在PATH中
3. **文件不存在**: 检查输入文件是否正确放置

### 调试模式

可以通过运行单个步骤来调试问题:
```bash
python peptide_optimizer.py --step 1  # 测试OmegaFold
python peptide_optimizer.py --step 3  # 测试AutoDock
```

## 性能优化

- 调整 `--cores` 参数来利用多核处理器
- 对于大型蛋白质，可能需要增加内存
- 步骤3(对接)和步骤7(ProteinMPNN)是最耗时的步骤

## 代码结构

```
PeptideOptimizer类:
├── __init__(): 初始化配置
├── step1_model_peptide(): OmegaFold结构预测
├── step2_add_hydrogens(): PyMOL氢原子添加
├── step3_docking(): AutoDock分子对接
├── step4_sort_atoms(): 结构整理
├── step5_score_binding(): Vina评分
├── step6_merge_structures(): 结构合并
├── step7_proteinmpnn_optimization(): 序列优化
├── step8_final_analysis(): 结果分析
└── run_full_pipeline(): 完整流程执行
```
