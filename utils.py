
from http.client import HTTPException
import os


def validate_file_exists(file_path: str, file_type: str) -> str:
    """验证文件是否存在"""
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=400, 
            detail=f"{file_type} file not found: {file_path}"
        )
    return file_path

def validate_fasta_file(file_path: str) -> str:
    """验证FASTA文件格式"""
    validate_file_exists(file_path, "FASTA")
    
    try:
        with open(file_path, 'r') as f:
            content = f.read().strip()
            if not content.startswith('>'):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid FASTA format: file should start with '>'"
                )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error reading FASTA file: {str(e)}"
        )
    
    return file_path

def validate_pdb_file(file_path: str) -> str:
    """验证PDB文件格式"""
    validate_file_exists(file_path, "PDB")
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            if not any(line.startswith(('ATOM', 'HETATM')) for line in content.split('\n')):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid PDB format: no ATOM or HETATM records found"
                )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error reading PDB file: {str(e)}"
        )
    
    return file_path
