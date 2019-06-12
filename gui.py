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

        self.container = tk.Frame(self)
        self.container.pack(side="top", fill="both", expand=True)
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)

        self.main_and_commands = MainAndCommands(self)
        self.navigation = NavigationBar(self)

        self.main_and_commands.pack(side="right", fill="x")
        self.navigation.pack(side="left", expand=False)

        self.pack()

        self.laser = None

    def connect_laser(self):
        self.laser = Laser()
        self.main_and_commands.main.status.text.config(text="Laser connected.")

    def laser_on(self):
        self.laser.startup_begin()

    def quit(self):
        if self.laser:
            self.laser.itla_disconnect()

        quit()


class MainAndCommands(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.main = Main(self)
        self.commands = CommandBar(self)

        self.main.pack(side="top")
        self.commands.pack(side="bottom")


class Main(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.status = Status(self)
        self.context = Context(self)

        self.status.pack(side="top", padx=10, pady=10)
        self.context.pack(side="bottom", padx=10, pady=10)


class Context(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.context = BlankContext(self)
        self.context.pack(padx=300, pady=300)


class BlankContext(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent


class Status(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.text = ttk.Label(self, text="Connecting to laser...")
        self.progress_bar = ttk.Progressbar(self, length=200, value=0)

        self.text.pack(side="top", pady=5)
        self.progress_bar.pack(side="bottom", pady=5)


class NavigationBar(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent)
        self.parent = parent

        self.button_home = NavigationButton(self, "Home", None)
        self.button_power = NavigationButton(self, "Power Monitor", None)
        self.button_close = NavigationButton(self, "Close", self.parent.quit)

        self.button_home.pack(fill="y")
        self.button_power.pack(fill="y")
        self.button_close.pack(fill="y")


class NavigationButton(tk.Frame):
    def __init__(self, parent, label, action, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.button = ttk.Button(self, text=label, command=action, width=20)
        self.button.pack(fill="y", pady=5)


class CommandBar(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.button_on = CommandButton(self, "Laser On", None)
        self.button_off = CommandButton(self, "Laser Off", None)

        self.button_on.pack(fill="x")


class CommandButton(tk.Frame):
    def __init__(self, parent, label, action, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.button = ttk.Button(self, text=label, command=action, width=-30)
        self.button.pack(fill="x", pady=10, padx=5)


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
    app.connect_laser()
    # ani = animation.FuncAnimation(f, animate, interval=10)
    app.mainloop()

finally:
    app.laser.itla_disconnect()
