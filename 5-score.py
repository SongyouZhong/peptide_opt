import subprocess
import os

file_out = open('score_rank_1_10.dat', 'w')
for i in range(1, 11):

    ifile = f'peptide_ranked_{i}_sorted_H.pdb'
    os.system('prepare_ligand -l '+ifile+' -o '+ifile+'qt')
    
    pdbqt = f'peptide_ranked_{i}_sorted_H.pdbqt'
    cmd = [
        "vina",
        "--ligand", pdbqt,
        "--receptor", "receptorH.pdbqt",
        "--score_only",
        "--exhaustiveness", "1",
        "--num_modes", "1"
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True
    )

    matches = [l for l in result.stdout.splitlines() if "Affinity:" in l]

    for match in matches:
        tmp = match.strip().split()
        score = tmp[1]
        file_out.write('%3d %15s\n' % (i, score))
    
