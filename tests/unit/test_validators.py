"""
验证器单元测试
"""

import pytest
from peptide_opt.core.validators import (
    ValidationError,
    validate_fasta_file,
    validate_pdb_file,
    validate_sequence,
)


class TestValidateSequence:
    """测试序列验证"""
    
    def test_valid_sequence(self):
        """测试有效序列"""
        seq = validate_sequence("ACDEFGHIKLMNPQRSTVWY")
        assert seq == "ACDEFGHIKLMNPQRSTVWY"
    
    def test_lowercase_sequence(self):
        """测试小写序列转换"""
        seq = validate_sequence("acdef")
        assert seq == "ACDEF"
    
    def test_sequence_too_short(self):
        """测试序列过短"""
        with pytest.raises(ValidationError):
            validate_sequence("", min_length=1)
    
    def test_sequence_too_long(self):
        """测试序列过长"""
        with pytest.raises(ValidationError):
            validate_sequence("A" * 100, max_length=50)
    
    def test_invalid_amino_acids(self):
        """测试无效氨基酸"""
        with pytest.raises(ValidationError):
            validate_sequence("ACDEFXYZ")


class TestValidateFastaFile:
    """测试 FASTA 文件验证"""
    
    def test_valid_fasta(self, tmp_path):
        """测试有效 FASTA 文件"""
        fasta_file = tmp_path / "test.fasta"
        fasta_file.write_text(">test\nACDEF\n")
        
        result = validate_fasta_file(str(fasta_file))
        assert result == str(fasta_file)
    
    def test_invalid_fasta_no_header(self, tmp_path):
        """测试无效 FASTA 文件（无头部）"""
        fasta_file = tmp_path / "test.fasta"
        fasta_file.write_text("ACDEF\n")
        
        with pytest.raises(ValidationError):
            validate_fasta_file(str(fasta_file))
    
    def test_file_not_found(self):
        """测试文件不存在"""
        with pytest.raises(ValidationError):
            validate_fasta_file("/nonexistent/path/file.fasta")


class TestValidatePdbFile:
    """测试 PDB 文件验证"""
    
    def test_valid_pdb(self, tmp_path):
        """测试有效 PDB 文件"""
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text("ATOM      1  N   ALA A   1       0.000   0.000   0.000\n")
        
        result = validate_pdb_file(str(pdb_file))
        assert result == str(pdb_file)
    
    def test_invalid_pdb_no_atoms(self, tmp_path):
        """测试无效 PDB 文件（无原子记录）"""
        pdb_file = tmp_path / "test.pdb"
        pdb_file.write_text("HEADER TEST\n")
        
        with pytest.raises(ValidationError):
            validate_pdb_file(str(pdb_file))
