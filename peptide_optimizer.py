#!/usr/bin/env python3
"""
Peptide Optimization Pipeline
整合的肽段优化程序，包含结构预测、分子对接、序列优化和性质分析
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from Bio.PDB import PDBParser, PDBIO, Select, StructureBuilder
from Bio.PDB.Chain import Chain
from Bio.PDB.Residue import Residue
from Bio.PDB.Atom import Atom
from Bio.SeqUtils.ProtParam import ProteinAnalysis
import pandas as pd
from pymol import cmd
import copy


class PeptideOptimizer:
    """肽段优化主类"""
    
    def __init__(self, input_dir="./input", output_dir="./output", 
                 proteinmpnn_dir="./ProteinMPNN/", cores=12, cleanup=True,
                 n_poses=10, num_seq_per_target=10, proteinmpnn_seed=37,
                 progress_callback=None):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.proteinmpnn_dir = Path(proteinmpnn_dir)
        self.cores = cores
        self.cleanup = cleanup  # 是否清理中间文件
        self.progress_callback = progress_callback  # 进度回调函数
        
        # 新增参数
        self.n_poses = n_poses  # adcp命令中的-N参数
        self.num_seq_per_target = num_seq_per_target  # ProteinMPNN每个目标生成的序列数
        self.proteinmpnn_seed = proteinmpnn_seed  # ProteinMPNN随机数种子
        
        # 中间文件目录
        self.middle_dir = Path("./middlefiles")
        self.pmpnn_dir = self.middle_dir / "pmpnn"
        
        # Hopp-Woods hydrophilicity scale
        self.hopp_woods = {
            'A': -0.5, 'R': 3.0, 'N': 0.2, 'D': 3.0,
            'C': -1.0, 'Q': 0.2, 'E': 3.0, 'G': 0.0,
            'H': -0.5, 'I': -1.8, 'L': -1.8, 'K': 3.0,
            'M': -1.3, 'F': -2.5, 'P': 0.0, 'S': 0.3,
            'T': -0.4, 'W': -3.4, 'Y': -2.3, 'V': -1.5
        }
        
        # 创建必要的目录
        self.output_dir.mkdir(exist_ok=True)
        self.middle_dir.mkdir(exist_ok=True)
        
    def log(self, message):
        """日志输出"""
        print(f"[PeptideOptimizer] {message}")
        
    def update_progress(self, progress, message):
        """更新进度"""
        if self.progress_callback:
            self.progress_callback(progress, message)
        self.log(f"Progress {progress:.1f}%: {message}")
        
    def run_command(self, command, description=""):
        """执行系统命令"""
        if description:
            self.log(f"{description}")
        self.log(f"Running: {command}")
        
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            self.log(f"Error in command: {command}")
            self.log(f"Error output: {result.stderr}")
            raise RuntimeError(f"Command failed: {command}")
        return result
        
    def step1_model_peptide(self):
        """步骤1: 使用OmegaFold预测肽段结构"""
        self.log("Step 1: Modeling peptide structure with OmegaFold")
        
        peptide_fasta = self.input_dir / "peptide.fasta"
        if not peptide_fasta.exists():
            raise FileNotFoundError(f"Peptide FASTA file not found: {peptide_fasta}")
            
        # 输出到中间文件目录
        command = f"omegafold --model 2 {peptide_fasta} {self.middle_dir}"
        self.run_command(command, "Predicting peptide structure")
        
    def step2_add_hydrogens(self):
        """步骤2: 添加氢原子"""
        self.log("Step 2: Adding hydrogens to receptor and peptide")
        
        # 处理受体蛋白
        class NoHetatmSelect(Select):
            def accept_residue(self, residue):
                return residue.id[0] == ' '

        input_pdb = self.input_dir / "5ffg.pdb"
        output_pdb = self.middle_dir / "receptor.pdb"

        parser = PDBParser(QUIET=True)
        structure = parser.get_structure("structure", str(input_pdb))

        io = PDBIO()
        io.set_structure(structure)
        io.save(str(output_pdb), select=NoHetatmSelect())

        # 使用PyMOL添加氢原子
        cmd.load(str(output_pdb))
        cmd.remove("elem H")
        cmd.h_add("all")
        cmd.save(str(self.middle_dir / "receptorH.pdb"))
        cmd.reinitialize()

        cmd.load(str(self.middle_dir / "peptide.pdb"))
        cmd.remove("elem H")
        cmd.h_add("all")
        cmd.save(str(self.middle_dir / "peptideH.pdb"))
        cmd.reinitialize()
        
    def step3_docking(self):
        """步骤3: 分子对接"""
        self.log("Step 3: Molecular docking")
        
        # 读取肽段序列
        peptide_fasta = self.input_dir / "peptide.fasta"
        with open(peptide_fasta, 'r') as f:
            lines = f.readlines()
            peptide_seq = lines[1].strip()
        
        # 切换到中间文件目录进行操作
        original_cwd = os.getcwd()
        os.chdir(self.middle_dir)
        
        try:
            # 准备受体和配体
            self.update_progress(56, "Preparing receptor structure")
            commands = [
                "prepare_receptor -r receptorH.pdb -o receptorH.pdbqt",
            ]
            
            for command in commands:
                self.run_command(command)
                
            self.update_progress(57, "Preparing ligand structure")
            commands = [
                "prepare_ligand -l peptideH.pdb -o peptideH.pdbqt",
            ]
            
            for command in commands:
                self.run_command(command)
                
            self.update_progress(58, "Generating docking grid")
            commands = [
                "agfr -r receptorH.pdbqt -l peptideH.pdbqt -asv 1.1 -o complex",
            ]
            
            for command in commands:
                self.run_command(command)
                
            self.update_progress(60, f"Running molecular docking ({self.n_poses} poses)")
            commands = [
                f"adcp -t complex.trg -s {peptide_seq} -N {self.n_poses} -c {self.cores} -o ./peptide"
            ]
            
            for command in commands:
                self.run_command(command)
        finally:
            # 恢复原始工作目录
            os.chdir(original_cwd)
            
    def step4_sort_atoms(self):
        """步骤4: 原子排序和添加氢原子"""
        self.log("Step 4: Sorting atoms and adding hydrogens")
        
        for i in range(1, self.n_poses + 1):
            parser = PDBParser(QUIET=True)
            input_file = self.middle_dir / f'peptide_ranked_{i}.pdb'
            structure = parser.get_structure("A", str(input_file))

            io = PDBIO()
            io.set_structure(structure)
            sorted_file = self.middle_dir / f'peptide_ranked_{i}_sorted.pdb'
            io.save(str(sorted_file))

            cmd.load(str(sorted_file))
            cmd.remove("elem H")
            cmd.h_add("all")
            sorted_h_file = self.middle_dir / f'peptide_ranked_{i}_sorted_H.pdb'
            cmd.save(str(sorted_h_file))
            cmd.reinitialize()
            
    def step5_score_binding(self):
        """步骤5: 计算结合亲和力评分"""
        self.log("Step 5: Calculating binding affinity scores")
        
        # 保存当前工作目录
        original_cwd = os.getcwd()
        
        score_file = self.middle_dir / f'score_rank_1_{self.n_poses}.dat'
        with open(score_file, 'w') as file_out:
            for i in range(1, self.n_poses + 1):
                input_filename = f'peptide_ranked_{i}_sorted_H.pdb'
                output_filename = f'peptide_ranked_{i}_sorted_H.pdbqt'
                input_file = self.middle_dir / input_filename
                output_file = self.middle_dir / output_filename
                
                # 检查输入文件是否存在
                if not input_file.exists():
                    self.log(f"Warning: Input file does not exist: {input_file}")
                    continue
                
                # 切换到中间文件目录执行prepare_ligand
                os.chdir(self.middle_dir)
                
                try:
                    # 准备配体，使用相对路径
                    prepare_cmd = f'prepare_ligand -l {input_filename} -o {output_filename}'
                    self.run_command(prepare_cmd)
                finally:
                    # 恢复原始工作目录
                    os.chdir(original_cwd)
                
                # 使用vina评分
                receptor_pdbqt = self.middle_dir / "receptorH.pdbqt"
                cmd = [
                    "vina",
                    "--ligand", str(output_file.resolve()),
                    "--receptor", str(receptor_pdbqt.resolve()),
                    "--score_only",
                    "--autobox",
                    "--exhaustiveness", "1",
                    "--num_modes", "1"
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                matches = [l for l in result.stdout.splitlines() if "Affinity:" in l]

                for match in matches:
                    tmp = match.strip().split()
                    score = tmp[1]
                    file_out.write('%3d %15s\n' % (i, score))
                    
    def clone_and_rename_chain(self, original_chain, new_id):
        """克隆并重命名链"""
        new_chain = Chain(new_id)
        for residue in original_chain:
            new_residue = Residue(residue.id, residue.resname, residue.segid)
            for atom in residue:
                new_atom = Atom(
                    atom.name,
                    atom.coord,
                    atom.bfactor,
                    atom.occupancy,
                    atom.altloc,
                    atom.fullname.strip().ljust(4),
                    atom.serial_number,
                    element=atom.element,
                )
                new_residue.add(new_atom)
            new_chain.add(new_residue)
        return new_chain
        
    def step6_merge_structures(self):
        """步骤6: 合并肽段和蛋白质结构"""
        self.log("Step 6: Merging peptide and protein structures")
        
        self.pmpnn_dir.mkdir(exist_ok=True)
        
        for n in range(1, self.n_poses + 1):
            complex_dir = self.pmpnn_dir / f"complex{n}"
            complex_dir.mkdir(exist_ok=True)

            # 输入/输出文件
            peptide_pdb = self.middle_dir / f'peptide_ranked_{n}_sorted_H.pdb'
            protein_pdb = self.middle_dir / 'receptorH.pdb'
            output_pdb = complex_dir / 'complex.pdb'

            # 解析结构
            parser = PDBParser(QUIET=True)
            peptide_structure = parser.get_structure("peptide", str(peptide_pdb))
            protein_structure = parser.get_structure("protein", str(protein_pdb))

            # 初始化新结构
            builder = StructureBuilder.StructureBuilder()
            builder.init_structure("combined")
            builder.init_model(0)

            # 添加肽段链作为'A'
            peptide_chain = list(peptide_structure.get_chains())[0]
            new_peptide_chain = self.clone_and_rename_chain(peptide_chain, "A")
            builder.structure[0].add(new_peptide_chain)

            # 添加蛋白质链，ID为B, C, D...
            chain_ids = [chr(i) for i in range(ord('B'), ord('Z') + 1)]
            protein_chains = list(protein_structure.get_chains())

            for i, original_chain in enumerate(protein_chains):
                if i >= len(chain_ids):
                    raise ValueError("Too many chains for simple letter IDs.")
                new_chain = self.clone_and_rename_chain(original_chain, chain_ids[i])
                builder.structure[0].add(new_chain)

            # 保存合并的结构
            io = PDBIO()
            io.set_structure(builder.structure)
            io.save(str(output_pdb))

            self.log(f"Combined structure saved to: {output_pdb}")
            
    def step7_proteinmpnn_optimization(self):
        """步骤7: 使用ProteinMPNN进行序列优化"""
        self.log("Step 7: Optimizing sequences with ProteinMPNN")
        
        openmpnn_helper = self.proteinmpnn_dir / "helper_scripts"
        chains_to_design = "A"
        
        for i in range(1, self.n_poses + 1):
            progress = 85 + (8 * (i-1) / self.n_poses)  # 85% to 93%
            self.update_progress(progress, f"Processing complex {i}/{self.n_poses} with ProteinMPNN")
            
            output_dir = self.pmpnn_dir / f"complex{i}"
            path_for_parsed_chains = output_dir / "parsed_pdbs.jsonl"
            path_for_assigned_chains = output_dir / "assigned_pdbs.jsonl"
            
            # 解析多链结构
            command = f"python3 {openmpnn_helper}/parse_multiple_chains.py --input_path={output_dir} --output_path={path_for_parsed_chains}"
            self.run_command(command)
            
            # 分配固定链
            command = f"python3 {openmpnn_helper}/assign_fixed_chains.py --input_path={path_for_parsed_chains} --output_path={path_for_assigned_chains} --chain_list {chains_to_design}"
            self.run_command(command)
            
            # 运行ProteinMPNN
            command = f"python3 {self.proteinmpnn_dir}/protein_mpnn_run.py --jsonl_path {path_for_parsed_chains} --out_folder {output_dir} --chain_id_jsonl {path_for_assigned_chains} --num_seq_per_target {self.num_seq_per_target} --sampling_temp 0.1 --seed {self.proteinmpnn_seed} --batch_size 1"
            self.run_command(command)
            
            self.log(f"complex{i} optimization completed")
            
    def calculate_hydrophilicity(self, sequence, scale=None):
        """计算疏水性"""
        if scale is None:
            scale = self.hopp_woods
        values = [scale.get(aa, 0.0) for aa in sequence]
        return sum(values) / len(values) if values else 0.0

    def optimal_sequence(self, fasta_path):
        """从FASTA文件中找到最优序列"""
        with open(fasta_path, 'r') as file_in:
            seq_dict = {}
            n = 0
            for line in file_in.readlines():
                tmp = line.strip().split(',')
                if tmp[0] == '>complex':
                    ttt = tmp[2][1:].strip().split('=')
                    org_gscore = float(ttt[1])
                if n > 1:
                    if tmp[0][:2] == '>T':
                        ttt = tmp[3][1:].strip().split('=')
                        gscore = float(ttt[1])
                    else:
                        seq_dict[tmp[0]] = gscore
                n += 1

        sort_dict = {k: v for k, v in sorted(seq_dict.items(), key=lambda item: item[1])}
        opt_seq, opt_gscore = list(sort_dict.items())[-1]
        return org_gscore, opt_seq, opt_gscore

    def analyze_sequence_properties(self, seq):
        """分析序列性质"""
        analysis = ProteinAnalysis(seq)
        mw = analysis.molecular_weight()
        ip = analysis.isoelectric_point()
        aro = analysis.aromaticity()
        ins = analysis.instability_index()
        gra = analysis.gravy()
        hyd = self.calculate_hydrophilicity(seq)
        sec = analysis.secondary_structure_fraction()
        return mw, ip, aro, ins, gra, hyd, sec
        
    def step8_final_analysis(self):
        """步骤8: 最终分析和报告生成"""
        self.log("Step 8: Final analysis and report generation")
        
        # 读取原始序列
        peptide_fasta = self.input_dir / "peptide.fasta"
        with open(peptide_fasta, 'r') as f:
            lines = f.readlines()
            original_seq = lines[1].strip()

        # 分析原始序列性质
        mw, ip, aro, ins, gra, hyd, sec = self.analyze_sequence_properties(original_seq)
        
        info_dict = {
            'Original sequence affinity score': ['-'],
            'Original sequence global score': ['-'],
            'Optimal sequence': [original_seq],
            'Global score': ['-'],
            'Molecular weight': [mw],
            'Isoelectric point': [ip],
            'Aromaticity': [aro],
            'Instability index': [ins],
            'Hydrophobicity': [gra],
            'Hydrophilicity': [hyd],
            'Secondary structure fraction (Helix, Turn, Sheet)': [sec]
        }

        # 读取亲和力评分
        score_file = self.middle_dir / f'score_rank_1_{self.n_poses}.dat'
        with open(score_file, 'r') as file_in:
            for line in file_in.readlines():
                tmp = line.strip().split()
                ascore = float(tmp[1])
                info_dict['Original sequence affinity score'].append(ascore)

        # 分析优化序列
        for i in range(1, self.n_poses + 1):
            fasta_path = self.pmpnn_dir / f'complex{i}' / 'seqs' / 'complex.fa'
            org_gscore, opt_seq, opt_gscore = self.optimal_sequence(str(fasta_path))
            mw, ip, aro, ins, gra, hyd, sec = self.analyze_sequence_properties(opt_seq)
            
            info_dict['Original sequence global score'].append(org_gscore)
            info_dict['Optimal sequence'].append(opt_seq)
            info_dict['Global score'].append(opt_gscore)
            info_dict['Molecular weight'].append(mw)
            info_dict['Isoelectric point'].append(ip)
            info_dict['Aromaticity'].append(aro)
            info_dict['Instability index'].append(ins)
            info_dict['Hydrophobicity'].append(gra)
            info_dict['Hydrophilicity'].append(hyd)
            info_dict['Secondary structure fraction (Helix, Turn, Sheet)'].append(sec)

            # 复制复合物文件到输出目录
            src = self.pmpnn_dir / f'complex{i}' / 'complex.pdb'
            dst = self.output_dir / f'complex{i}.pdb'
            shutil.copy2(src, dst)

        # 生成DataFrame和CSV报告
        index_labels = ['Input peptide property']
        for i in range(1, self.n_poses + 1):
            index_labels.append(f'Docking result rank {i}')

        df = pd.DataFrame(info_dict, index=index_labels)
        output_csv = self.output_dir / 'result.csv'
        df.to_csv(output_csv, index_label='Index')
        
        self.log(f"Final analysis completed. Results saved to {output_csv}")
        
    def cleanup_intermediate_files(self):
        """清理中间文件"""
        if not self.cleanup:
            self.log("Cleanup disabled, keeping intermediate files")
            return
            
        self.log("Cleaning up intermediate files...")
        try:
            if self.middle_dir.exists():
                shutil.rmtree(self.middle_dir)
                self.log(f"Removed intermediate files directory: {self.middle_dir}")
        except Exception as e:
            self.log(f"Warning: Failed to clean up intermediate files: {e}")
        
    def run_full_pipeline(self):
        """运行完整的肽段优化流程"""
        self.log("Starting peptide optimization pipeline")
        
        try:
            self.update_progress(35, "Step 1: Modeling peptide structure")
            self.step1_model_peptide()
            
            self.update_progress(45, "Step 2: Adding hydrogens to structures")
            self.step2_add_hydrogens()
            
            self.update_progress(55, "Step 3: Performing molecular docking")
            self.step3_docking()
            
            self.update_progress(65, "Step 4: Sorting atoms in structures")
            self.step4_sort_atoms()
            
            self.update_progress(70, "Step 5: Scoring binding affinity")
            self.step5_score_binding()
            
            self.update_progress(75, "Step 6: Merging peptide structures")
            self.step6_merge_structures()
            
            self.update_progress(85, "Step 7: ProteinMPNN sequence optimization")
            self.step7_proteinmpnn_optimization()
            
            self.update_progress(95, "Step 8: Final analysis and reporting")
            self.step8_final_analysis()
            
            # 清理中间文件
            self.update_progress(98, "Cleaning up intermediate files")
            self.cleanup_intermediate_files()
            
            self.update_progress(100, "Peptide optimization completed successfully!")
            self.log("Peptide optimization pipeline completed successfully!")
            
        except Exception as e:
            self.log(f"Pipeline failed with error: {str(e)}")
            if self.cleanup:
                self.log("Keeping intermediate files for debugging...")
            raise


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Peptide Optimization Pipeline')
    parser.add_argument('--input_dir', default='./input', help='Input directory')
    parser.add_argument('--output_dir', default='./output', help='Output directory')
    parser.add_argument('--proteinmpnn_dir', default='./ProteinMPNN/', help='ProteinMPNN directory')
    parser.add_argument('--cores', type=int, default=12, help='Number of CPU cores for docking')
    parser.add_argument('--step', type=int, help='Run only specific step (1-8)')
    parser.add_argument('--no-cleanup', action='store_true', help='Keep intermediate files (useful for debugging)')
    parser.add_argument('--n_poses', type=int, default=10, help='Number of docking poses to generate (adcp -N parameter)')
    parser.add_argument('--num_seq_per_target', type=int, default=10, help='Number of sequences per target for ProteinMPNN')
    parser.add_argument('--proteinmpnn_seed', type=int, default=37, help='Random seed for ProteinMPNN')
    
    args = parser.parse_args()
    
    optimizer = PeptideOptimizer(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        proteinmpnn_dir=args.proteinmpnn_dir,
        cores=args.cores,
        cleanup=not args.no_cleanup,  # 默认清理，除非指定--no-cleanup
        n_poses=args.n_poses,
        num_seq_per_target=args.num_seq_per_target,
        proteinmpnn_seed=args.proteinmpnn_seed
    )
    
    if args.step:
        # 运行特定步骤
        step_methods = {
            1: optimizer.step1_model_peptide,
            2: optimizer.step2_add_hydrogens,
            3: optimizer.step3_docking,
            4: optimizer.step4_sort_atoms,
            5: optimizer.step5_score_binding,
            6: optimizer.step6_merge_structures,
            7: optimizer.step7_proteinmpnn_optimization,
            8: optimizer.step8_final_analysis
        }
        
        if args.step in step_methods:
            step_methods[args.step]()
        else:
            print(f"Invalid step number: {args.step}. Must be 1-8.")
            sys.exit(1)
    else:
        # 运行完整流程
        optimizer.run_full_pipeline()


if __name__ == "__main__":
    main()
