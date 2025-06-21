from Bio.SeqUtils.ProtParam import ProteinAnalysis
import pandas as pd
import os

info_dict = {'Original sequence affinity score':[], 
             'Original sequence global score':[], 
             'Optimal sequence':[], 
             'Global score':[], 
             'Molecular weight':[], 
             'Isoelectric point':[], 
             'Aromaticity':[], 
             'Instability index':[], 
             'Hydrophobicity':[],
             'Hydrophilicity':[],
             'Secondary structure fraction (Helix, Turn, Sheet)':[]}

# Hopp-Woods hydrophilicity scale
hopp_woods = {
    'A': -0.5, 'R': 3.0, 'N': 0.2, 'D': 3.0,
    'C': -1.0, 'Q': 0.2, 'E': 3.0, 'G': 0.0,
    'H': -0.5, 'I': -1.8, 'L': -1.8, 'K': 3.0,
    'M': -1.3, 'F': -2.5, 'P': 0.0, 'S': 0.3,
    'T': -0.4, 'W': -3.4, 'Y': -2.3, 'V': -1.5
}

def calculate_hydrophilicity(sequence: str, scale: dict = hopp_woods):
    values = [scale.get(aa, 0.0) for aa in sequence]
    return sum(values) / len(values) if values else 0.0

def optimal_sequence(fasta_path):
    file_in = open(fasta_path, 'r')
    seq_dict = {}
    n = 0
    for line in file_in.readlines():
        tmp = line.strip().split(',')
        if tmp[0] == '>complex':
            ttt = tmp[2][1:].strip().split('=')
            org_gscore = float(ttt[1])
        if n>1:
            if tmp[0][:2] == '>T':
                ttt = tmp[3][1:].strip().split('=')
                gscore = float(ttt[1])
            else:
                seq_dict[tmp[0]] = gscore
        n += 1

    sort_dict = {k: v for k, v in sorted(seq_dict.items(), key=lambda item: item[1])}
    opt_seq, opt_gscore = list(sort_dict.items())[-1]
    return org_gscore, opt_seq, opt_gscore

def info(seq):
    analysis = ProteinAnalysis(seq)
    mw  = analysis.molecular_weight()
    ip  = analysis.isoelectric_point()
    aro = analysis.aromaticity()
    ins = analysis.instability_index()
    gra = analysis.gravy()
    hyd = calculate_hydrophilicity(seq)
    sec = analysis.secondary_structure_fraction()
    return mw, ip, aro, ins, gra, hyd, sec


# original sequence
file_in = open('./input/peptide.fasta', 'r')
for line in file_in.readlines()[1:]:
    tmp = line.strip().split()
    seq = tmp[0]

mw, ip, aro, ins, gra, hyd, sec = info(seq)
info_dict = {'Original sequence affinity score':['-'],
             'Original sequence global score':['-'],
             'Optimal sequence':[seq],
             'Global score':['-'],
             'Molecular weight':[mw],
             'Isoelectric point':[ip],
             'Aromaticity':[aro],
             'Instability index':[ins],
             'Hydrophobicity':[gra],
             'Hydrophilicity':[hyd],
             'Secondary structure fraction (Helix, Turn, Sheet)':[sec]}

# read affinity score
file_in = open('score_rank_1_10.dat', 'r')
for line in file_in.readlines():
    tmp = line.strip().split()
    ascore = float(tmp[1])
    info_dict['Original sequence affinity score'].append(ascore)

# optimal sequence
for i in range(1, 11):
    fasta_path = './pmpnn/complex' + str(i) +'/seqs/complex.fa'
    org_gscore, opt_seq, opt_gscore = optimal_sequence(fasta_path)
    mw, ip, aro, ins, gra, hyd, sec = info(opt_seq)
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

    os.system('cp ./pmpnn/complex'+str(i)+'/complex.pdb ./output/complex'+str(i)+'.pdb')


index_labels = ['Input peptide property', 
                'Docking result rank 1',
                'Docking result rank 2',
                'Docking result rank 3',
                'Docking result rank 4',
                'Docking result rank 5',
                'Docking result rank 6',
                'Docking result rank 7',
                'Docking result rank 8',
                'Docking result rank 9',
                'Docking result rank 10']

df = pd.DataFrame(info_dict, index=index_labels)
df.to_csv('./output/result.csv', index='Index')

