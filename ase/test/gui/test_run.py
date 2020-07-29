import os

import pytest
import numpy as np

from ase import Atoms
from ase.calculators.singlepoint import SinglePointCalculator
from ase.build import molecule, bulk
import ase.gui.ui as ui
from ase.gui.i18n import _
from ase.gui.gui import GUI
from ase.gui.save import save_dialog


class Error:
    """Fake window for testing puposes."""
    has_been_called = False

    def __call__(self, title, text=None):
        self.text = text or title
        self.has_been_called = True

    def called(self, text=None):
        """Check that an oops-window was opened with correct title."""
        if not self.has_been_called:
            return False

        self.has_been_called = False  # ready for next call

        return text is None or text == self.text


@pytest.fixture
def display():
    pytest.importorskip('tkinter')
    if not os.environ.get('DISPLAY'):
        raise pytest.skip('no display')


@pytest.fixture
def gui(guifactory):
    return guifactory(None)


@pytest.fixture
def no_blocking_errors_monkeypatch():
    orig_ui_error = ui.error
    ui.error = Error()
    yield
    ui.error = orig_ui_error


@pytest.fixture
def guifactory(display, no_blocking_errors_monkeypatch):
    guis = []

    def factory(images):
        gui = GUI(images)
        guis.append(gui)
        return gui
    yield factory

    for gui in guis:
        gui.exit()


@pytest.fixture
def atoms(gui):
    atoms = bulk('Ti') * (2, 2, 2)
    gui.new_atoms(atoms)
    return atoms


@pytest.fixture
def animation(guifactory):
    images = [bulk(sym) for sym in ['Cu', 'Ag', 'Au']]
    gui = guifactory(images)
    return gui


def test_nanotube(gui):
    nt = gui.nanotube_window()
    nt.apply()
    nt.element[1].value = '?'
    nt.apply()
    assert ui.error.called(
        _('You have not (yet) specified a consistent set of parameters.'))

    nt.element[1].value = 'C'
    nt.ok()
    assert len(gui.images[0]) == 20


def test_nanoparticle(gui):
    n = gui.nanoparticle_window()
    n.element.symbol = 'Cu'
    n.apply()
    n.set_structure_data()
    assert len(gui.images[0]) == 675
    n.method.value = 'wulff'
    n.update_gui_method()
    n.apply()


def test_color(gui):
    a = Atoms('C10', magmoms=np.linspace(1, -1, 10))
    a.positions[:] = np.linspace(0, 9, 10)[:, None]
    a.calc = SinglePointCalculator(a, forces=a.positions)
    che = np.linspace(100, 110, 10)
    mask = [0] * 10
    mask[5] = 1
    a.set_array('corehole_energies', np.ma.array(che, mask=mask))
    gui.new_atoms(a)
    c = gui.colors_window()
    c.toggle('force')
    c.toggle('magmom')
    activebuttons = [button.active for button in c.radio.buttons]
    assert activebuttons == [1, 0, 1, 0, 0, 1, 1, 1], activebuttons
    c.toggle('corehole_energies')
    c.change_mnmx(101, 120)


def test_settings(gui):
    gui.new_atoms(molecule('H2O'))
    s = gui.settings()
    s.scale.value = 1.9
    s.scale_radii()


def test_rotate(gui):
    gui.window['toggle-show-bonds'] = True
    gui.new_atoms(molecule('H2O'))
    gui.rotate_window()


def test_open_and_save(gui):
    mol = molecule('H2O')
    for i in range(3):
        mol.write('h2o.json')
    gui.open(filename='h2o.json')
    save_dialog(gui, 'h2o.cif@-1')


def test_fracocc(gui):
    from ase.test.fio.test_cif import content
    with open('./fracocc.cif', 'w') as f:
        f.write(content)
    gui.open(filename='fracocc.cif')



@pytest.fixture
def with_bulk_ti(gui):
    atoms = bulk('Ti') * (2, 2, 2)
    gui.new_atoms(atoms)


@pytest.fixture
def modify(gui, with_bulk_ti):
    gui.images.selected[:4] = True
    return gui.modify_atoms()


def test_select_atoms(gui, with_bulk_ti):
    gui.select_all()
    assert all(gui.images.selected)
    gui.invert_selection()
    assert not any(gui.images.selected)


def test_modify_element(gui, modify):
    class MockElement:
        Z = 79
    modify.set_element(MockElement())
    assert all(gui.atoms.symbols[:4] == 'Au')
    assert all(gui.atoms.symbols[4:] == 'Ti')


def test_modify_tag(gui, modify):
    modify.tag.value = 17
    modify.set_tag()
    tags = gui.atoms.get_tags()
    assert all(tags[:4] == 17)
    assert all(tags[4:] == 0)


def test_modify_magmom(gui, modify):
    modify.magmom.value = 3
    modify.set_magmom()
    magmoms = gui.atoms.get_initial_magnetic_moments()
    assert magmoms[:4] == pytest.approx(3)
    assert all(magmoms[4:] == 0)


def test_repeat(gui):
    fe = bulk('Fe')
    gui.new_atoms(fe)
    repeat = gui.repeat_window()

    multiplier = [2, 3, 4]
    expected_atoms = fe * multiplier
    natoms= np.prod(multiplier)
    for i, value in enumerate(multiplier):
        repeat.repeat[i].value = value

    repeat.change()
    assert len(gui.atoms) == natoms
    assert gui.atoms.positions == pytest.approx(expected_atoms.positions)
    assert gui.atoms.cell == pytest.approx(fe.cell[:])  # Still old cell

    repeat.set_unit_cell()
    assert gui.atoms.cell[:] == pytest.approx(expected_atoms.cell[:])

def test_surface(gui):
    assert len(gui.atoms) == 0
    surf = gui.surface_window()
    surf.element.symbol = 'Au'
    surf.apply()
    assert len(gui.atoms) > 0
    assert gui.atoms.cell.rank == 2


def test_movie(animation):
    movie = animation.movie_window
    assert movie is not None

    movie.play()
    movie.stop()
    movie.close()

def test_add_atoms(gui):
    dia = gui.add_atoms()
    dia.combobox.value = 'CH3CH2OH'
    dia.add()
    assert str(gui.atoms.symbols) == str(molecule('CH3CH2OH').symbols)

def test_cell_editor(gui):
    au = bulk('Au')
    gui.new_atoms(au.copy())

    dia = gui.cell_editor()

    ti = bulk('Ti')

    dia.update(ti.cell, ti.pbc)
    dia.apply_vectors()
    # Tolerance reflects the rounding (currently 7 digits)
    tol = 3e-7
    assert np.abs(gui.atoms.cell - ti.cell).max() < tol

    dia.update(ti.cell * 2, ti.pbc)
    dia.apply_magnitudes()
    assert np.abs(gui.atoms.cell - 2 * ti.cell).max() < tol

    dia.update(np.eye(3), ti.pbc)
    dia.apply_angles()
    assert abs(gui.atoms.cell.angles() - 90).max() < tol

    newpbc = [0, 1, 0]
    dia.update(np.eye(3), newpbc)
    dia.apply_pbc()
    assert (gui.atoms.pbc == newpbc).all()


def test_constrain(gui, atoms):
    gui.select_all()
    dia = gui.constraints_window()

    assert len(atoms.constraints) == 0
    dia.selected()  # constrain selected
    assert len(atoms.constraints) == 1

    assert sorted(atoms.constraints[0].index) == list(range(len(atoms)))


def test_quickinfo(gui, atoms):
    from ase.gui.quickinfo import info
    from ase.gui.i18n import _

    # (Note: String can be in any language)
    refstring = _('Single image loaded.')
    infostring = info(gui)
    assert refstring in infostring

    dia = gui.quick_info_window()
    # This is a bit weird and invasive ...
    txt = dia.things[0].text
    assert refstring in txt

def window():

    def hello(event=None):
        print('hello', event)

    menu = [('Hi', [ui.MenuItem('_Hello', hello, 'Ctrl+H')]),
            ('Hell_o', [ui.MenuItem('ABC', hello, choices='ABC')])]
    win = ui.MainWindow('Test', menu=menu)

    win.add(ui.Label('Hello'))
    win.add(ui.Button('Hello', hello))

    r = ui.Rows([ui.Label(x * 7) for x in 'abcd'])
    win.add(r)
    r.add('11111\n2222\n333\n44\n5')

    def abc(x):
        print(x, r.rows)

    cb = ui.ComboBox(['Aa', 'Bb', 'Cc'], callback=abc)
    win.add(cb)

    rb = ui.RadioButtons(['A', 'B', 'C'], 'ABC', abc)
    win.add(rb)

    b = ui.CheckButton('Hello')

    def hi():
        print(b.value, rb.value, cb.value)
        del r[2]
        r.add('-------------')

    win.add([b, ui.Button('Hi', hi)])

    return win


def runcallbacks(win):
    win.things[1].callback()
    win.things[1].callback()
    win.close()


def test_callbacks(display):
    win = window()
    win.win.after_idle(runcallbacks)
