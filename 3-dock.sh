prepare_receptor -r receptorH.pdb -o receptorH.pdbqt
prepare_ligand   -l peptideH.pdb  -o peptideH.pdbqt
agfr -r receptorH.pdbqt -l peptideH.pdbqt -asv 1.1 -o complex
adcp -t complex.trg -s GNGVPNLRGDLQVLGQRVGRT -N 10 -c 12 -o ./peptide # slow, 12 cores for 20 min
