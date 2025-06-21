from Bio.PDB import PDBParser, PDBIO
from pymol import cmd

for i in range(1, 11):
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("A", 'peptide_ranked_'+str(i)+'.pdb')

    io = PDBIO()
    io.set_structure(structure)
    io.save('peptide_ranked_'+str(i)+'_sorted.pdb')

    cmd.load('peptide_ranked_'+str(i)+'_sorted.pdb')
    cmd.remove("elem H")
    cmd.h_add("all")
    cmd.save('peptide_ranked_'+str(i)+'_sorted_H.pdb')

    cmd.reinitialize()
