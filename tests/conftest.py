"""
Pytest 配置和 fixtures
"""

import os
import sys
from pathlib import Path

import pytest

# 添加 src 目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def sample_fasta_content():
    """示例 FASTA 文件内容"""
    return """>test_peptide
ACDEFGHIKLMNPQRSTVWY
"""


@pytest.fixture
def sample_pdb_content():
    """示例 PDB 文件内容"""
    return """HEADER    TEST STRUCTURE
ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.458   0.000   0.000  1.00  0.00           C
ATOM      3  C   ALA A   1       2.009   1.420   0.000  1.00  0.00           C
ATOM      4  O   ALA A   1       1.246   2.390   0.000  1.00  0.00           O
END
"""


@pytest.fixture
def temp_input_dir(tmp_path, sample_fasta_content, sample_pdb_content):
    """创建临时输入目录"""
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    
    # 创建 FASTA 文件
    fasta_file = input_dir / "peptide.fasta"
    fasta_file.write_text(sample_fasta_content)
    
    # 创建 PDB 文件
    pdb_file = input_dir / "receptor.pdb"
    pdb_file.write_text(sample_pdb_content)
    
    return input_dir


@pytest.fixture
def temp_output_dir(tmp_path):
    """创建临时输出目录"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir
