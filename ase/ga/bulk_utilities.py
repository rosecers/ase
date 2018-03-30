import numpy as np
from scipy.spatial.distance import cdist
from itertools import product, combinations_with_replacement
from ase.geometry.cell import cell_to_cellpar


def get_cell_angles_lengths(cell):
    ''' 
    Returns cell vectors lengths (a,b,c) as well as different
    angles (alpha, beta, gamma, phi, chi, psi) (in radians). 
    '''
    cellpar = cell_to_cellpar(cell)
    cellpar[3:] *= np.pi / 180  # convert angles to radians
    parnames = ['a', 'b', 'c', 'alpha', 'beta', 'gamma']
    values = {n: p for n, p in zip(parnames, cellpar)}

    volume = abs(np.linalg.det(cell))
    for i, param in enumerate(['phi', 'chi', 'psi']):
        ab = np.linalg.norm(
            np.cross(cell[(i + 1) % 3, :], cell[(i + 2) % 3, :]))
        c = np.linalg.norm(cell[i, :])
        values[param] = np.arcsin(np.abs(volume / (ab * c)))

    return values


class CellBounds:
    ''' 
    Class for defining as well as checking limits 
    on cell vector lengths and various angles
    '''

    def __init__(self, bounds={}):
        self.bounds = {'alpha': [0, np.pi], 'beta': [0, np.pi], 'gamma': [0, np.pi],
                       'a': [0, 1e6], 'b': [0, 1e6], 'c': [0, 1e6],
                       'phi': [0, np.pi], 'chi': [0, np.pi], 'psi': [0, np.pi]}
        for param, bound in bounds.iteritems():
            self.bounds[param] = bound

    def is_within_bounds(self, cell):
        values = get_cell_angles_lengths(cell)
        verdict = True
        for param, bound in self.bounds.iteritems():
            if not (bound[0] <= values[param] <= bound[1]):
                verdict = False
        return verdict


def get_rotation_matrix(u, t):
    '''
    Returns the transformation matrix for rotation over an angle t
    along an axis with direction u.
    '''
    ux, uy, uz = u
    cost, sint = np.cos(t), np.sin(t)
    rotmat = np.array([[(ux**2) * (1 - cost) + cost,
                        ux * uy * (1 - cost) - uz * sint,
                        ux * uz * (1 - cost) + uy * sint],
                       [ux * uy * (1 - cost) + uz * sint,
                        (uy**2) * (1 - cost) + cost,
                        uy * uz * (1 - cost) - ux * sint],
                       [ux * uz * (1 - cost) - uy * sint,
                        uy * uz * (1 - cost) + ux * sint,
                        (uz**2) * (1 - cost) + cost]])
    return rotmat


def gather_atoms_by_tag(atoms):
    ''' Translates same-tag atoms so that they lie 'together',
    with distance vectors as in the minimum image convention.'''
    tags = atoms.get_tags()
    pos = atoms.get_positions()
    for tag in list(set(tags)):
        indices = np.where(tags == tag)[0]
        if len(indices) == 1:
            continue
        vectors = atoms.get_distances(indices[0], indices[1:],
                                      mic=True, vector=True)
        pos[indices[1:]] = pos[indices[0]] + vectors
    atoms.set_positions(pos)


def atoms_too_close(atoms, bl, use_tags=False):
    ''' 
    Alternative method of finding out whether atoms are 
    too close to each other. Whereas the function in ase.ga.utilities
    can take up to the order of 1 second to decide, this one
    consistently does it in a few milliseconds. 
    Furthermore, for cells with one very short lattice vector
    (e.g. 1-2 Angstrom), this method seems to correctly evaluate,
    whereas the ase.ga.utilities function appears to be faulty.

    use_tags: whether to use the Atoms tags to disable distance
              checking within a block with the same tag.

              Note: if certain atoms are constrained, this method
              may return unexpected results in case the contraints
              prevent same-tag atoms to be gathered together in
              the minimum-image-convention. In such cases, one
              should (1) release the relevant constraints, 
              (2) apply the gather_atoms_by_tag function, and
              (3) re-apply the constraints, before using the 
              atoms_too_close function.  
    '''
    a = atoms.copy()
    if use_tags:
        gather_atoms_by_tag(a)

    pbc = a.get_pbc()
    cell = a.get_cell()
    num = a.get_atomic_numbers()
    pos = a.get_positions()
    tags = a.get_tags()
    unique_types = sorted(list(set(num)))

    neighbours = []
    for i in range(3):
        if pbc[i]:
            neighbours.append([-1, 0, 1])
        else:
            neighbours.append([0])

    for nx, ny, nz in product(*neighbours):
        displacement = np.dot(cell.T, np.array([nx, ny, nz]).T)
        pos_new = pos + displacement
        distances = cdist(pos, pos_new)

        if nx == 0 and ny == 0 and nz == 0:
            if use_tags and len(a) > 1:
                x = np.array([tags]).T
                distances += 1e2 * (cdist(x, x) == 0)
            else:
                distances += 1e2 * np.identity(len(a))

        for type1, type2 in combinations_with_replacement(unique_types, 2):
            x1 = np.where(num == type1)
            x2 = np.where(num == type2)
            if np.min(distances[x1].T[x2]) < bl[(type1, type2)]:
                return True

    return False


def convert_for_lammps(atoms):
    """
    Convert a parallel piped (forming right hand basis)
    to lower triangular, low-tilt box that LAMMPS will accept. 

    This code draws from a previous LAMMPS interface:
    https://svn.fysik.dtu.dk/projects/ase-extra/trunk/
    ase-extra/trunk/ase/calculators/lammpslib.py
    """
    ase_cell = atoms.get_cell()
    cell = np.matrix.transpose(ase_cell)
    # rotate bases into triangular matrix
    tri_mat = np.zeros((3, 3))
    A = cell[:, 0]
    B = cell[:, 1]
    C = cell[:, 2]
    tri_mat[0, 0] = np.linalg.norm(A)
    Ahat = A / np.linalg.norm(A)
    AxBhat = np.cross(A, B) / np.linalg.norm(np.cross(A, B))
    tri_mat[0, 1] = np.dot(B, Ahat)
    tri_mat[1, 1] = np.linalg.norm(np.cross(Ahat, B))
    tri_mat[0, 2] = np.dot(C, Ahat)
    tri_mat[1, 2] = np.dot(C, np.cross(AxBhat, Ahat))
    tri_mat[2, 2] = np.linalg.norm(np.dot(C, AxBhat))

    # create and save the transformation for coordinates
    #volume = np.linalg.det(ase_cell)
    #trans = np.array([np.cross(B, C), np.cross(C, A), np.cross(A, B)])
    #trans = trans / volume
    #coord_transform = tri_mat*trans

    atoms.set_cell(tri_mat.T, scale_atoms=True)
    atoms.wrap(pbc=True)

    # "flip" the cell if it is too skewed
    newcell = atoms.get_cell()
    while True:
        xx, yy = newcell[0, 0], newcell[1, 1]
        xy, xz, yz = newcell[1, 0], newcell[2, 0], newcell[2, 1]
        cond1 = 2 * abs(xy) > xx
        cond2 = 2 * abs(xz) > xx
        cond3 = 2 * abs(yz) > yy
        if not cond1 and not cond2 and not cond3:
            break
        if cond1:
            newcell[1, 0] += xx * np.round((0.5 * xx - xy) / xx - 0.5)
        if cond2:
            newcell[2, 0] += xx * np.round((0.5 * xx - xz) / xx - 0.5)
        if cond3:
            newcell[2, 1] += yy * np.round((0.5 * yy - yz) / yy - 0.5)
            newcell[2, 0] += xy * np.round((0.5 * yy - yz) / yy - 0.5)

    atoms.set_cell(newcell, scale_atoms=False)
    atoms.wrap(pbc=True)
