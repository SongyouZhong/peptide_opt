from Bio.PDB import PDBParser, PDBIO, Select

class NoHetatmSelect(Select):
    def accept_residue(self, residue):
        return residue.id[0] == ' '

input_pdb = "./input/5ffg.pdb"
output_pdb = "receptor.pdb"

parser = PDBParser(QUIET=True)
structure = parser.get_structure("structure", input_pdb)

io = PDBIO()
io.set_structure(structure)
io.save(output_pdb, select=NoHetatmSelect())

from pymol import cmd

cmd.load("receptor.pdb")
cmd.remove("elem H")
cmd.h_add("all")
cmd.save("receptorH.pdb")

cmd.reinitialize()

cmd.load("peptide.pdb")
cmd.remove("elem H")
cmd.h_add("all")
cmd.save("peptideH.pdb")
