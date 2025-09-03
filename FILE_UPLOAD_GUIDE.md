# 📁 Peptide优化系统 - 文件上传和处理指南

## 📋 概述

本文档详细说明用户在使用Peptide优化系统时需要上传什么文件，以及这些文件在系统中如何被处理和转换。

## 🔍 用户需要提供的文件

### 1. 必需文件

#### 🧬 受体蛋白结构文件 (必须上传)
- **文件格式**: `.pdb` 或 `.pdbqt`
- **文件描述**: 目标蛋白质的3D结构文件
- **上传方式**: 通过API `/upload_pdbqt` 端点上传
- **示例文件名**: `5ffg.pdb`, `receptor.pdb`, `protein.pdb`
- **文件要求**:
  - 有效的PDB格式
  - 包含完整的蛋白质3D坐标信息
  - 建议文件大小 < 50MB
  - 可以包含水分子和其他杂原子

#### 🧪 肽段序列 (通过API参数提供)
- **输入方式**: API参数 `peptide_sequence`
- **格式**: 单字母氨基酸序列
- **示例**: `"MKFLVNVAL"`, `"ACDEFGHIKLMNPQRSTVWY"`
- **要求**:
  - 只能包含标准20种氨基酸的单字母代码
  - 长度建议: 5-50个氨基酸
  - 不包含特殊字符或空格

### 2. 系统自动生成的文件

用户只需提供受体蛋白文件，系统会根据肽段序列自动生成相应的FASTA文件。

## 🔄 完整的文件处理流程

### Phase 1: 文件上传阶段

```
用户操作: 上传受体蛋白文件
POST /upload_pdbqt
Files: receptor.pdb (用户原始文件)

存储位置:
uploads/{user_id}/receptor.pdb ✅ 原始文件，永不修改
```

### Phase 2: 任务创建阶段

```
用户操作: 创建优化任务
POST /peptide/optimize
参数: {
    "peptide_sequence": "MKFLVNVAL",
    "receptor_pdb_filename": "receptor.pdb"
}

系统处理:
1. 创建任务目录: jobs/peptide_optimization/{task_id}/
2. 文件复制和重命名:
   uploads/{user_id}/receptor.pdb 
   → jobs/{task_id}/input/5ffg.pdb (系统标准命名)

3. 自动生成肽段文件:
   → jobs/{task_id}/input/peptide.fasta
   内容:
   >peptide
   MKFLVNVAL
```

### Phase 3: 优化处理阶段

#### 🔬 Step 1: 结构预测
```
输入: input/peptide.fasta
工具: OmegaFold AI结构预测
输出: middlefiles/peptide.pdb (肽段的3D结构)
变化: 序列 → 3D结构坐标
```

#### 🧪 Step 2: 氢原子处理
```
受体处理:
input/5ffg.pdb 
→ [BioPython清理] → middlefiles/receptor.pdb (去除HETATM)
→ [PyMOL处理] → middlefiles/receptorH.pdb (添加氢原子)

肽段处理:
middlefiles/peptide.pdb 
→ [PyMOL处理] → middlefiles/peptideH.pdb (添加氢原子)

变化: 原子数量增加，结构更完整
```

#### ⚛️ Step 3: 分子对接准备
```
格式转换:
middlefiles/receptorH.pdb → middlefiles/receptorH.pdbqt
middlefiles/peptideH.pdb → middlefiles/peptideH.pdbqt

工具: ADFRsuite (prepare_receptor, prepare_ligand)
变化: PDB格式 → PDBQT格式 (包含原子类型和电荷信息)
```

#### 🎯 Step 3: 分子对接执行
```
输入: receptorH.pdbqt + peptideH.pdbqt
工具: AGFR + ADCP
参数: n_poses (对接构象数量)

输出: (n_poses = 10的示例)
middlefiles/peptide_ranked_1.pdb  (最佳构象)
middlefiles/peptide_ranked_2.pdb
middlefiles/peptide_ranked_3.pdb
...
middlefiles/peptide_ranked_10.pdb (第10个构象)

变化: 单一肽段结构 → 多个对接构象
```

#### 📊 Step 4: 结构整理
```
每个对接构象的处理:
peptide_ranked_N.pdb 
→ [BioPython排序] → peptide_ranked_N_sorted.pdb
→ [PyMOL加氢] → peptide_ranked_N_sorted_H.pdb

变化: 原子顺序规范化，氢原子补全
```

#### 🔬 Step 5: 亲和力评分
```
评分处理:
peptide_ranked_N_sorted_H.pdb 
→ [prepare_ligand] → peptide_ranked_N_sorted_H.pdbqt
→ [Vina评分] → 亲和力数值

输出: middlefiles/score_rank_1_{n_poses}.dat
内容示例:
  1         -8.1
  2         -7.9
  3         -7.6
  ...

变化: 结构文件 → 数值评分
```

#### 🧬 Step 6: 结构合并
```
复合物构建:
peptide_ranked_N_sorted_H.pdb + receptorH.pdb 
→ [BioPython合并] → middlefiles/pmpnn/complexN/complex.pdb

链ID分配:
- 肽段: 链A
- 受体蛋白: 链B, C, D... (按原有链分配)

变化: 分离的分子 → 合并的复合物结构
```

#### 🤖 Step 7: 序列优化 (可选)
```
AI序列优化:
complex.pdb 
→ [ProteinMPNN解析] → parsed_pdbs.jsonl
→ [ProteinMPNN优化] → 优化后的序列

输出: middlefiles/pmpnn/complexN/seqs/complex.fa
内容示例:
>complex, score=2.5134, global_score=0.8723
MKFLVNVAL
>T=0.1, sample=0, score=1.8234, global_score=0.9156
MKYLVNVAL  (优化后序列)
>T=0.1, sample=1, score=1.9876, global_score=0.8945
MKILMNVAL  (优化后序列)
...

变化: 原始序列 → 多个优化序列候选
```

#### 📈 Step 8: 最终分析和输出
```
数据汇总:
所有中间结果 + 序列分析 
→ [性质计算] → output/result.csv

复合物复制:
middlefiles/pmpnn/complexN/complex.pdb 
→ output/complexN.pdb

最终输出文件:
output/
├── result.csv          (完整分析报告)
├── complex1.pdb        (最佳复合物结构)
├── complex2.pdb
└── ...

变化: 分散的数据 → 结构化报告和可用结构文件
```

## 📊 文件大小和格式变化统计

### 典型文件大小变化

```
原始受体文件 (receptor.pdb): ~2-10 MB
├── 5ffg.pdb: 相同大小
├── receptor.pdb: 略小 (去除HETATM)
├── receptorH.pdb: +20-30% (添加氢原子)
└── receptorH.pdbqt: 相似大小 (格式转换)

肽段相关:
peptide.fasta: <1 KB (纯序列)
├── peptide.pdb: 5-50 KB (3D结构)
├── peptideH.pdb: +20-30% (添加氢原子)
└── 对接构象: 5-50 KB × n_poses个

最终输出:
├── result.csv: 5-20 KB (数据表格)
└── complex*.pdb: 2-15 MB (合并结构)
```

### 文件格式转换链

```
用户输入格式 → 系统内部格式 → 最终输出格式

受体蛋白:
.pdb/.pdbqt → .pdb → .pdbqt → .pdb (合并后)

肽段序列:
字符串 → .fasta → .pdb → .pdbqt → .pdb (合并后)

分析结果:
多种数据 → .csv 表格
```

## 🔒 文件保护和管理策略

### ✅ 文件保护保证

1. **原始文件永不修改**
   ```
   uploads/{user_id}/receptor.pdb ← 用户原文件，永久保存
   ```

2. **任务隔离**
   ```
   jobs/peptide_optimization/{task_id}/ ← 每个任务独立目录
   ```

3. **多任务复用**
   ```
   同一个受体文件可以用于多个不同的肽段优化任务
   ```

### 🗂️ 文件清理策略

#### 根据 `cleanup` 参数:

**cleanup = true (默认)**
```
保留:
├── uploads/{user_id}/        (原始文件)
├── jobs/{task_id}/input/     (任务输入)
└── jobs/{task_id}/output/    (最终结果)

删除:
└── jobs/{task_id}/middlefiles/  (中间文件，节省空间)
```

**cleanup = false (调试模式)**
```
全部保留:
├── uploads/{user_id}/           (原始文件)
├── jobs/{task_id}/input/        (任务输入)
├── jobs/{task_id}/middlefiles/  (中间文件，便于调试)
└── jobs/{task_id}/output/       (最终结果)
```

## 📁 目录结构总览

```
peptide_opt系统完整目录结构:

/dockingVina/
├── uploads/{user_id}/
│   └── receptor.pdb              ← 用户上传的原始文件
└── jobs/peptide_optimization/{task_id}/
    ├── input/
    │   ├── 5ffg.pdb             ← 受体文件副本 (重命名)
    │   └── peptide.fasta        ← 自动生成的肽段序列
    ├── middlefiles/             ← 所有中间处理文件
    │   ├── peptide.pdb          ← OmegaFold预测结构
    │   ├── receptorH.pdb        ← 添加氢原子的受体
    │   ├── peptideH.pdb         ← 添加氢原子的肽段
    │   ├── peptide_ranked_*.pdb ← 对接构象
    │   ├── score_rank_*.dat     ← 评分结果
    │   └── pmpnn/               ← ProteinMPNN优化结果
    ├── output/
    │   ├── result.csv           ← 最终分析报告
    │   └── complex*.pdb         ← 最终复合物结构
    └── optimization_config.txt  ← 任务配置参数
```

## 🚀 用户使用流程总结

### 1. 准备阶段
```bash
# 用户需要准备的文件:
receptor.pdb  # 目标蛋白质结构文件
"MKFLVNVAL"   # 肽段序列 (字符串形式)
```

### 2. 上传阶段
```bash
# 上传受体文件
curl -X POST "http://localhost:8000/upload_pdbqt" \
     -F "files=@receptor.pdb"
```

### 3. 任务创建
```bash
# 创建优化任务
curl -X POST "http://localhost:8000/peptide/optimize" \
     -H "Content-Type: application/json" \
     -d '{
         "peptide_sequence": "MKFLVNVAL",
         "receptor_pdb_filename": "receptor.pdb"
     }'
```

### 4. 结果获取
```bash
# 任务完成后，用户可获得:
output/result.csv     # 详细分析报告
output/complex*.pdb   # 优化后的复合物结构
```

## ⚠️ 重要注意事项

1. **文件安全性**: 用户上传的原始文件永远不会被修改或删除
2. **任务独立性**: 每个优化任务在完全独立的目录中执行，互不干扰
3. **存储优化**: 系统会根据设置自动清理中间文件以节省存储空间
4. **格式兼容性**: 系统自动处理各种文件格式转换，用户无需手动处理
5. **可重复性**: 同一个受体文件可以用于多个不同的肽段优化任务

## 🔗 相关文档

- [Peptide Optimizer API文档](API_Documentation.md)
- [系统安装和配置指南](README.md)
- [故障排除指南](troubleshooting.md)

---

📝 *本文档最后更新: 2025年9月3日*
