#!/usr/bin/env python
import gtk
import gobject

from ase.gui.languages import translate as _
from ase.gui.widgets import pack


class Movie(gtk.Window):
    def __init__(self, gui):
        gtk.Window.__init__(self)
        self.set_position(gtk.WIN_POS_NONE)
        self.connect('destroy', self.close)
        #self.connect('delete_event', self.exit2)
        self.set_title('Movie')
        vbox = gtk.VBox()
        pack(vbox, gtk.Label(_('Image number:')))
        self.frame_number = gtk.Adjustment(gui.frame, 0,
                                           gui.images.nimages - 1,
                                           1.0, 5.0)
        self.frame_number.connect('value-changed', self.new_frame)

        hscale = pack(vbox, gtk.HScale(self.frame_number))
        hscale.set_update_policy(gtk.UPDATE_CONTINUOUS)
        hscale.set_digits(0)

        buttons = [gtk.Button(stock=gtk.STOCK_GOTO_FIRST),
                   gtk.Button(stock=gtk.STOCK_GO_BACK),
                   gtk.Button(stock=gtk.STOCK_GO_FORWARD),
                   gtk.Button(stock=gtk.STOCK_GOTO_LAST)]

        buttons[0].connect('clicked', self.click, -1, True)
        buttons[1].connect('clicked', self.click, -1)
        buttons[2].connect('clicked', self.click, 1)
        buttons[3].connect('clicked', self.click, 1, True)

        pack(vbox, buttons)

        play, stop = pack(vbox, [gtk.Button(_('Play')),
                                 gtk.Button('Stop')])
        play.connect('clicked', self.play)
        stop.connect('clicked', self.stop)

        self.rock = pack(vbox, gtk.CheckButton('Rock'))
        tdefault = min(max(gui.images.nimages/10.0, 0.1), 300)
        self.time = gtk.Adjustment(tdefault, 0.1, 300, 0.1)
        hscale = pack(vbox, gtk.HScale(self.time))
        hscale.set_update_policy(gtk.UPDATE_DISCONTINUOUS)
        hscale.set_digits(1)
            
        self.time.connect('value-changed', self.new_time)

        self.add(vbox)

        if gtk.pygtk_version < (2, 12):
            self.set_tip = gtk.Tooltips().set_tip
            self.set_tip(hscale, _('Adjust number of frames per second.'))
        else:
            hscale.set_tooltip_text(_('Adjust number of frames per second.'))
        vbox.show()
        self.show()
        self.gui = gui
        #gui.m=self
        self.direction = 1
        self.id = None
        gui.register_vulnerable(self)

    def notify_atoms_changed(self):
        "Called by gui object when the atoms have changed."
        self.destroy()
        
    def close(self, event):
        self.stop()

    def click(self, button, step, firstlast=False):
        if firstlast and step < 0:
            i = 0
        elif firstlast:
            i = self.gui.images.nimages - 1
        else:
            i = max(0, min(self.gui.images.nimages - 1, self.gui.frame + step))
        self.gui.set_frame(i)
        self.frame_number.value = i
        if firstlast:
            self.direction = cmp(-step, 0)
        else:
            self.direction = cmp(step, 0)
            
    def new_frame(self, widget):
        self.gui.set_frame(int(self.frame_number.value))

    def play(self, widget=None):
        if self.id is not None:
            gobject.source_remove(self.id)
        t = int(1000.0 / float(self.time.value))
        self.id = gobject.timeout_add(t, self.step)

    def stop(self, widget=None):
        if self.id is not None:
            gobject.source_remove(self.id)
            self.id = None

    def step(self):
        i = self.gui.frame
        nimages = self.gui.images.nimages
        
        if self.rock.get_active():
            if i == 0:
                self.direction = 1
            elif i == nimages - 1:
                self.direction = -1
            i += self.direction
        else:
            i = (i + self.direction + nimages) % nimages
            
        self.gui.set_frame(i)
        self.frame_number.value = i
        return True

    def new_time(self, widget):
        if self.id is not None:
            self.play()

if __name__ == '__main__':
    import os
    os.system('python gui.py')
