import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import matplotlib.animation as animation
from matplotlib import style

import tkinter as tk
from tkinter import ttk

from laser import Laser
import time

LARGE_FONT = ("Verdana", 14)
style.use("ggplot")

f = Figure(figsize=(5, 5), dpi=100)
a = f.add_subplot(111)


graph_x = []
graph_x_start = 0
graph_y = []


def animate(i):

    power = laser.check_power()
    t = time.perf_counter() - graph_x_start

    graph_x.append(t)
    graph_y.append(power)

    a.clear()
    a.plot(graph_x[-100:], graph_y[-100:])

    if power >= 10:
        laser.wait_nop()


def start_laser(controller):

    controller.show_frame(StartLaser)
    laser.startup_begin(195)


def stop_laser(controller):
    controller.show_frame(StopLaser)
    laser.laser_off()


class MainApplication(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        #self.tk.iconbitmap(self, default="favicon.ico")
        #self.tk.wm_title(self, "ITLA-PPCL550 Control")

        self.main_and_commands = Main(self)
        self.navigation = NavigationBar(self)

        self.main_and_commands.pack(side="right", fill="both", expand=True)
        self.navigation.pack(side="left", fill="y", expand=False)

        self.pack(fill="both", expand=True)

        self.laser = None

    def connect_laser(self):
        self.laser = Laser()
        self.main_and_commands.status.text.config(text="Laser connected.")
        self.main_and_commands.status.progress_bar.config(value=100)

    def laser_on(self):
        self.laser.startup_begin()

    def quit(self):
        if self.laser:
            self.laser.itla_disconnect()

        quit()


class Main(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.status = Status(self)
        self.main = Context(self)
        self.top_separator = ttk.Separator(self)
        self.bottom_separator = ttk.Separator(self)
        self.commands = CommandBar(self)

        self.status.pack(side="top", padx=10, pady=10, fill="x", expand=False)
        self.top_separator.pack(side="top", fill="x", padx=10, pady=5)
        self.main.pack(side="top", fill="both", expand=True)
        self.bottom_separator.pack(side="top", fill="x", padx=10, pady=5)
        self.commands.pack(side="bottom", fill="x", expand=False)


class Context(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.context = BlankContext(self)
        self.context.pack(fill="both", expand=True)


class BlankContext(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.pack(fill="both", expand=True)


class Status(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.text = ttk.Label(self, text="Connecting to laser...")
        self.progress_bar = ttk.Progressbar(self, length=200, value=0)

        self.text.pack(side="top", pady=5, padx=10, expand=True)
        self.progress_bar.pack(side="bottom", pady=5, padx=20, fill="x", expand=False)


class NavigationBar(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent)
        self.parent = parent

        self.button_home = NavigationButton(self, "Home", None)
        self.button_power = NavigationButton(self, "Power Monitor", None)
        self.button_frequency = NavigationButton(self, "Frequency Monitor", None)
        self.button_close = NavigationButton(self, "Close", self.parent.quit)

        self.button_home.pack(fill="both", expand=True)
        self.button_power.pack(fill="both", expand=True)
        self.button_frequency.pack(fill="both", expand=True)
        self.button_close.pack(fill="both", expand=True)


class NavigationButton(tk.Frame):
    def __init__(self, parent, label, action, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.button = ttk.Button(self, text=label, command=action, width=20)
        self.button.pack(pady=5, ipady=20, fill="both", expand=True)


class CommandBar(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        full_sticky = tk.N+tk.S+tk.E+tk.W

        for c in range(5):
            self.grid_columnconfigure(c, weight=1)

        self.button_on = CommandButton(self, "Laser On", None)
        self.button_on.grid(row=0, column=0, sticky=full_sticky)
        self.button_off = CommandButton(self, "Laser Off", None)
        self.button_off.grid(row=1, column=0, sticky=full_sticky)

        self.jump_entry = FrequencyEntryAndLabel(self, "Jump frequency (THz):")
        self.jump_entry.grid(row=0, column=1, padx=5)
        self.button_jump = CommandButton(self, "Frequency Jump", None)
        self.button_jump.grid(row=1, column=1, sticky=full_sticky)

        self.sweep_entry = FrequencyEntryAndLabel(self, "Sweep range (GHz)", 50, 0, 50)
        self.sweep_entry.grid(row=0, column=2, padx=5)
        self.speed_entry = FrequencyEntryAndLabel(self, "Sweep speed (GHz/sec)", 20, 0, 50)
        self.speed_entry.grid(row=0, column=3, padx=5)
        self.button_sweep = CommandButton(self, "Frequency Sweep", None)
        self.button_sweep.grid(row=1, column=2, columnspan=2, sticky=full_sticky)


class FrequencyEntryAndLabel(tk.Frame):
    def __init__(self, parent, label, freq=195, min_freq=191.5, max_freq=196.25, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.label = ttk.Label(self, text=label)
        self.label.pack(side="top", expand=True, fill="both")

        self.frequency_entry = FrequencyEntry(self, freq, min_freq, max_freq)
        self.frequency_entry.pack(side="bottom", expand=True, fill="both")


class FrequencyEntry(tk.Frame):
    def __init__(self, parent, freq=195, min_freq=191.5, max_freq=196.25, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        vcmd = (parent.register(self.validate),
                '%d', '%i', '%P', '%s', '%S', '%v', '%V', '%W')

        self.entry = ttk.Entry(self, text=str(freq), validate='focusout', validatecommand=vcmd)
        self.entry.pack(padx=10, pady=5)
        self.min_freq = min_freq
        self.max_freq = max_freq
        self.frequency = freq

        self.entry.insert(0, str(self.frequency))

    def value(self):
        return self.entry.get()

    def validate(self, action, index, value_if_allowed,
                       prior_value, text, validation_type, trigger_type, widget_name):
        if text in '0123456789.-+':
            try:
                value_float = float(value_if_allowed)

                if self.min_freq < value_float < self.max_freq:
                    self.frequency = round(value_float, 4)
                    self.entry.delete(0, tk.END)
                    self.entry.insert(0, str(self.frequency))
                    return True
                else:
                    self.bell()
                    self.entry.delete(0, tk.END)
                    self.entry.insert(0, str(self.frequency))
                    return False

            except ValueError:
                self.bell()
                self.entry.delete(0, tk.END)
                self.entry.insert(0, str(self.frequency))
                return False
        else:
            self.bell()
            self.entry.delete(0, tk.END)
            self.entry.insert(0, str(self.frequency))
            return False


class CommandButton(tk.Frame):
    def __init__(self, parent, label, action, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        full_sticky = tk.N + tk.S + tk.E + tk.W

        self.button = ttk.Button(self, text=label, command=action, width=-20)
        self.button.pack(fill="both", pady=5, padx=10, ipady=5)


class StartPage(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        label = tk.Label(self, text=('ITLA-PPCL550 Control'), font=LARGE_FONT)
        label.pack(pady=10, padx=10)

        button1 = ttk.Button(self, text="Laser On",
                             command=lambda: start_laser(controller))
        button1.pack()

        button2 = ttk.Button(self, text="Close",
                             command=quit)
        button2.pack()


class StopLaser(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        label = tk.Label(self, text="Turning off laser", font=LARGE_FONT)
        label.pack(pady=10, padx=10)

        button1 = ttk.Button(self, text="Back to Home",
                             command=lambda: controller.show_frame(StartPage))
        button1.pack()


class StartLaser(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        label = tk.Label(self, text="Laser starting up...", font=LARGE_FONT)
        label.pack(pady=10, padx=10)

        button1 = ttk.Button(self, text="Back to Home",
                             command=lambda: controller.show_frame(StartPage))
        button1.pack()

        button2 = ttk.Button(self, text="Turn off Laser",
                             command=lambda: stop_laser(controller))

        button2.pack()

        canvas = FigureCanvasTkAgg(f, self)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        toolbar = NavigationToolbar2Tk(canvas, self)
        toolbar.update()
        canvas._tkcanvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)


app = None
try:
    app = MainApplication(tk.Tk())
    app.bind_all("<1>", lambda event: event.widget.focus_set())
    app.connect_laser()
    # ani = animation.FuncAnimation(f, animate, interval=10)
    app.mainloop()

finally:
    app.laser.itla_disconnect()
