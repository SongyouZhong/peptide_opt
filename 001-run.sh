# All input files are in the "input" folder
# All output files are in the "output" folder
# Input: (1) PDB file for target; (2) peptide sequence
# Output: (1) 10 pdb files for top 10 docking complex; (2) a csv file for basic information

#step 1. use omegafold to model the peptide structure through sequence information
sh 1-model_peptide.sh

# step 2. add hydrogen to both receptor and peptide for docking
python3 2-add_h.py

# step 3. docking receptor and peptide and extract the top 10 peptides
sh 3-dock.sh

# step 4. sort the atoms in the top 10 peptides
python3 4-sort_atom.py

# step 5. run vina for the top 10 peptide-protein complexes
python3 5-score.py

# step 6. combine the peptide protein structures for peptide optimization
python3 6-merge-peptide-protein.py

# step 7. run ProteinMPNN for optimizing peptide sequence
sh 7-pmpnn.sh

# step 8. output the docking results, optimal sequence and basic peptide properties as csv
python3 8-final.py
