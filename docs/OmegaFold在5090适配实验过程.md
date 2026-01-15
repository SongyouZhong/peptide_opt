OmegaFold 安装与配置指南 (适配 NVIDIA RTX 5090)
更新日期： 2026-01-14 适用硬件： NVIDIA RTX 5090 (Blackwell Architecture) 核心问题： OmegaFold 官方代码库依赖旧版 PyTorch/CUDA (11.x)，而 RTX 5090 必须使用 CUDA 12.8+。 解决方案： 使用 Mamba 管理基础环境，手动注入最新的 PyTorch Nightly 版本，并以忽略依赖的方式安装 OmegaFold。

1. 准备工作
包管理器： 推荐使用 Mamba (包含在 Miniforge 中)。

网络环境： 需能访问 GitHub 和 PyTorch 官方源。

2. 安装步骤
第一步：创建并配置基础环境
创建一个干净的 Python 3.10 环境，并安装非 PyTorch 类的基础依赖。

Bash

# 1. 创建环境
mamba create -n omegafold_5090 python=3.10 -y

# 2. 激活环境
mamba activate omegafold_5090

# 3. 安装基础工具和生物学库
# 注意：此时不要通过 mamba 安装 PyTorch 或 fair-esm
mamba install biopython git -y
第二步：安装适配 RTX 5090 的 PyTorch
关键步骤： RTX 5090 需要 CUDA 12.8 或更高版本。我们需要从 PyTorch 的 Nightly（预览版）通道安装。

Bash

# 使用 pip 安装最新的 Nightly 版 PyTorch
pip3 install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128
验证： 输入 python -c "import torch; print(torch.cuda.get_device_name(0))" 应当输出：NVIDIA GeForce RTX 5090

第三步：安装 OmegaFold 主程序
由于官方 requirements.txt 锁死了旧版 PyTorch，必须使用 --no-deps 参数跳过依赖检查。

Bash

# 1. 克隆代码库
git clone https://github.com/HeliXonProtein/OmegaFold
cd OmegaFold

# 2. 强制安装本体（忽略依赖）
pip install . --no-deps
第四步：补全缺失依赖 (fair-esm)
由于上一步跳过了依赖，需要手动补充 fair-esm。

⚠️ 重要警告： 必须使用 pip 安装，严禁使用 mamba install fair-esm。 原因：Mamba 会检测到 PyTorch 版本不匹配，试图卸载你刚装好的 5090 版 PyTorch，导致环境崩溃。

Bash

pip install fair-esm
3. 验证安装
方法 A：快速脚本检查
创建一个 python 脚本检查环境完整性：

Python

import torch
import esm
import omegafold

print(f"CUDA Available: {torch.cuda.is_available()}")
print(f"Device: {torch.cuda.get_device_name(0)}")
print("Environment Check Passed ✅")
方法 B：实际推理测试
运行一条短序列进行测试（首次运行会自动下载约 2GB 模型权重）。

Bash

# 1. 创建测试序列
echo -e ">test\nMKTVRQERLKSIVRILERSKEPVSGAQLAEELSVSRQVIVQDIAYLRSLGYNIVATPRGYVLAGG" > test.fasta

# 2. 运行推理
omegafold test.fasta out_dir
预期输出：

终端显示 Loading weights...

推理耗时极短（约 1-2 秒）

out_dir 目录下生成 .pdb 文件

4. 常见问题 (FAQ)
Q1: 运行时出现红色警告 UserWarning: Using torch.cross without specifying the dim arg is deprecated，怎么办？

A: 直接忽略。这是因为 OmegaFold 代码较老，使用了旧版 API，而 PyTorch 2.x 发出了弃用警告。这不影响计算结果的准确性，也不会中断程序。

Q2: 为什么不能直接运行 pip install -r requirements.txt？

A: 官方文件里包含 torch==1.12.0+cu113。这会强制降级 PyTorch 到 2022 年的版本，该版本无法识别 RTX 5090，会导致 CUDA error: no kernel image is available。

Q3: 如果我手滑用了 mamba 安装 esm 导致报错怎么办？

A: 你会遇到 libmamba filesystem error 或环境损坏。解决方法是强制重装 PyTorch：

Bash

pip3 install --pre torch torchvision torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128 --force-reinstall
pip install fair-esm
Q4: 5090 显存很大，如何跑超长序列？

A: 直接运行即可。如果遇到 OOM (Out of Memory)，请添加 --subbatch_size 参数（例如设置为 256 或更小）来以时间换空间。