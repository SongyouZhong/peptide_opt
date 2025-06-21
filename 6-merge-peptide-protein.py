from Bio.PDB import PDBParser, PDBIO, StructureBuilder
from Bio.PDB.Chain import Chain
from Bio.PDB.Residue import Residue
from Bio.PDB.Atom import Atom
import copy
import os

def clone_and_rename_chain(original_chain, new_id):
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

os.system('mkdir pmpnn')
for n in range(1, 11):
    os.system('mkdir ./pmpnn/complex'+str(n))

    # Input/output
    peptide_pdb = 'peptide_ranked_'+str(n)+'_sorted_H.pdb'
    protein_pdb = 'receptorH.pdb'
    output_pdb = './pmpnn/complex'+str(n)+'/complex.pdb'

    # Parse structures
    parser = PDBParser(QUIET=True)
    peptide_structure = parser.get_structure("peptide", peptide_pdb)
    protein_structure = parser.get_structure("protein", protein_pdb)

    # Initialize new structure
    builder = StructureBuilder.StructureBuilder()
    builder.init_structure("combined")
    builder.init_model(0)

    # Add peptide chain as 'A'
    peptide_chain = list(peptide_structure.get_chains())[0]
    new_peptide_chain = clone_and_rename_chain(peptide_chain, "A")
    builder.structure[0].add(new_peptide_chain)

    # Add protein chains with IDs B, C, D, ...
    chain_ids = [chr(i) for i in range(ord('B'), ord('Z') + 1)]
    protein_chains = list(protein_structure.get_chains())

    for i, original_chain in enumerate(protein_chains):
        if i >= len(chain_ids):
            raise ValueError("Too many chains for simple letter IDs.")
        new_chain = clone_and_rename_chain(original_chain, chain_ids[i])
        builder.structure[0].add(new_chain)

    # Save combined structure
    io = PDBIO()
    io.set_structure(builder.structure)
    io.save(output_pdb)

    print(f"Combined structure saved to: {output_pdb}")
