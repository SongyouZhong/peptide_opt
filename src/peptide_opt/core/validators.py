"""
文件验证工具
"""

import os
from typing import Optional


class ValidationError(Exception):
    """验证错误"""
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


def validate_file_exists(file_path: str, file_type: str) -> str:
    """
    验证文件是否存在
    
    Args:
        file_path: 文件路径
        file_type: 文件类型描述
        
    Returns:
        验证通过的文件路径
        
    Raises:
        ValidationError: 文件不存在时
    """
    if not os.path.exists(file_path):
        raise ValidationError(f"{file_type} file not found: {file_path}")
    return file_path


def validate_fasta_file(file_path: str) -> str:
    """
    验证 FASTA 文件格式
    
    Args:
        file_path: FASTA 文件路径
        
    Returns:
        验证通过的文件路径
        
    Raises:
        ValidationError: 文件格式无效时
    """
    validate_file_exists(file_path, "FASTA")
    
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
            if not content.startswith('>'):
                raise ValidationError(
                    "Invalid FASTA format: file should start with '>'"
                )
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Error reading FASTA file: {str(e)}")
    
    return file_path


def validate_pdb_file(file_path: str) -> str:
    """
    验证 PDB 文件格式
    
    Args:
        file_path: PDB 文件路径
        
    Returns:
        验证通过的文件路径
        
    Raises:
        ValidationError: 文件格式无效时
    """
    validate_file_exists(file_path, "PDB")
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            if not any(line.startswith(('ATOM', 'HETATM')) for line in content.split('\n')):
                raise ValidationError(
                    "Invalid PDB format: no ATOM or HETATM records found"
                )
    except ValidationError:
        raise
    except Exception as e:
        raise ValidationError(f"Error reading PDB file: {str(e)}")
    
    return file_path


def validate_sequence(sequence: str, min_length: int = 1, max_length: int = 1000) -> str:
    """
    验证氨基酸序列
    
    Args:
        sequence: 氨基酸序列
        min_length: 最小长度
        max_length: 最大长度
        
    Returns:
        验证通过的序列（大写）
        
    Raises:
        ValidationError: 序列无效时
    """
    valid_amino_acids = set("ACDEFGHIKLMNPQRSTVWY")
    
    sequence = sequence.upper().strip()
    
    if len(sequence) < min_length:
        raise ValidationError(f"Sequence too short: minimum {min_length} residues required")
    
    if len(sequence) > max_length:
        raise ValidationError(f"Sequence too long: maximum {max_length} residues allowed")
    
    invalid_chars = set(sequence) - valid_amino_acids
    if invalid_chars:
        raise ValidationError(
            f"Invalid amino acids in sequence: {', '.join(sorted(invalid_chars))}"
        )
    
    return sequence
