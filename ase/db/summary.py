from __future__ import print_function

from ase.db.core import float_to_time_string, now, default_key_descriptions
from ase.geometry import cell_to_cellpar
from ase.utils import formula_metal


class Summary:
    def __init__(self, row, meta={}, subscript=None, prefix=''):
        self.row = row

        self.cell = [['{:.3f}'.format(a) for a in axis] for axis in row.cell]
        par = ['{:.3f}'.format(x) for x in cell_to_cellpar(row.cell)]
        self.lengths = par[:3]
        self.angles = par[3:]

        self.stress = row.get('stress')
        if self.stress is not None:
            self.stress = ', '.join('{0:.3f}'.format(s) for s in self.stress)

        self.formula = formula_metal(row.numbers)
        if subscript:
            self.formula = subscript.sub(r'<sub>\1</sub>', self.formula)

        kd = meta.get('key_descriptions', {})
        create_layout = meta.get('layout') or default_layout
        layout = create_layout(row, kd, prefix)
        # Transpose:
        self.layout = [(title,
                        [[row[0] for row in rows],
                         [row[1] for row in rows if len(row) == 2]])
                       for title, rows in layout]

        self.dipole = row.get('dipole')
        if self.dipole is not None:
            self.dipole = ', '.join('{0:.3f}'.format(d) for d in self.dipole)

        self.data = row.get('data')
        if self.data:
            self.data = ', '.join(self.data.keys())

        self.constraints = row.get('constraints')
        if self.constraints:
            self.constraints = ', '.join(c.__class__.__name__
                                         for c in self.constraints)

    def write(self):
        row = self.row

        print(self.formula + ':')
        for headline, columns in self.layout:
            blocks = columns[0]
            if len(columns) == 2:
                blocks += columns[1]
            print((' ' + headline + ' ').center(78, '='))
            for block in blocks:
                if block['type'] == 'table':
                    print(block['title'] + ':')
                    rows = block['rows']
                    if not rows:
                        print()
                        continue
                    width = max(len(name) for name, value, unit in rows)
                    print('{:{width}}|value'.format('name', width=width))
                    for name, value, unit in rows:
                        print('{:{width}}|{} {}'.format(name, value, unit,
                                                        width=width))
                    print()
                elif block['type'] == 'figure':
                    print(block['filename'])
                    print()
                elif block['type'] == 'cell':
                    print('Unit cell in Ang:')
                    print('axis|periodic|          x|          y|          z')
                    c = 1
                    fmt = '   {0}|     {1}|{2[0]:>11}|{2[1]:>11}|{2[2]:>11}'
                    for p, axis in zip(row.pbc, self.cell):
                        print(fmt.format(c, [' no', 'yes'][p], axis))
                        c += 1
                    print('Lengths: {:>10}{:>10}{:>10}'
                          .format(*self.lengths))
                    print('Angles:  {:>10}{:>10}{:>10}\n'
                          .format(*self.angles))

        if self.stress:
            print('Stress tensor (xx, yy, zz, zy, zx, yx) in eV/Ang^3:')
            print('   ', self.stress, '\n')

        if self.dipole:
            print('Dipole moment in e*Ang: ({})\n'.format(self.dipole))

        if self.constraints:
            print('Constraints:', self.constraints, '\n')

        if self.data:
            print('Data:', self.data, '\n')


def create_table(row, keys, title, key_descriptions, digits=3):
    # types: (Row, List[str], str, Dict[str, Tuple[str, str, str]], int)
    # -> Dict[str, Any]
    table = []
    for key in keys:
        if key == 'age':
            age = float_to_time_string(now() - row.ctime, True)
            table.append(('Age', age, ''))
            continue
        value = row.get(key)
        if value is not None:
            if isinstance(value, float):
                value = '{:.{}f}'.format(value, digits)
            elif not isinstance(value, str):
                value = str(value)
            desc, unit = key_descriptions.get(key, ['', key, ''])[1:]
            table.append((desc, value, unit))
    return {'type': 'table', 'rows': table, 'title': title}


def default_layout(row, key_descriptions, prefix):
    # types: (Row, Dict[str, Tuple[str, str, str]], str)
    # types -> List[Tuple[str, List[List[Dict[str, Any]]]]]
    keys = ['id',
            'energy', 'fmax', 'smax',
            'mass',
            'age']
    table = create_table(row, keys, 'Key-value pairs', key_descriptions)
    layout = [('Basic properties', [[{'type': 'atoms'}, table],
                                    [{'type': 'cell'}]])]

    misckeys = set(default_key_descriptions)
    misckeys.update(row.key_value_pairs)
    misckeys -= set(keys)
    misc = create_table(row, sorted(misckeys), 'Items', key_descriptions)
    layout.append(('Miscellaneous', [[misc]]))
    return layout
