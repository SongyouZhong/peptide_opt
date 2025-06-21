Required softwares/packages and installation guide
1. install omegafold (https://github.com/HeliXonProtein/OmegaFold)
pip install OmegaFold
or
pip install git+https://github.com/HeliXonProtein/OmegaFold

2. install autodock crankpep (https://ccsb.scripps.edu/adcp/downloads/)
download tarball
tar zxvf ADFRsuite_Linux-x86_64_1.0.tar.gz
cd ADFRsuite_x86_64Linux_1.0
### change install.sh line 85 to export PATH="$PATH:$INSTALL_DIR/bin"
./install.sh -d ~/ADFRsuite-1.0 -c 0
export PATH=/home/sunja/ADFRsuite-1.0/bin:$PATH

2. install autodock vina use vina to calculate binding scores
pip install vina
or
sudo apt-get install autodock-vina

3. install pymol to add H and do mutation
conda install -c conda-forge -c schrodinger pymol-bundle

4. install biopython
python3 -m pip install biopython

5. install ProteinMPNN
git clone https://github.com/dauparas/ProteinMPNN
not need to install

Workflow
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
