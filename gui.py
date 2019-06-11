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

def start_laser(controller):

    controller.show_frame(StartLaser)
    laser.startup_begin(195)


def stop_laser(controller):
    controller.show_frame(StopLaser)
    laser.laser_off()

class LaserGUI(tk.Tk):

    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)

        tk.Tk.iconbitmap(self, default="favicon.ico")
        tk.Tk.wm_title(self, "ITLA-PPCL550 Control")

        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}

        for F in (StartPage, StartLaser, StopLaser):
            frame = F(container, self)

            self.frames[F] = frame

            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(StartPage)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()


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


laser = None
try:
    laser = Laser()
    app = LaserGUI()
    ani = animation.FuncAnimation(f, animate, interval=10)
    app.mainloop()

finally:
    laser.itla_disconnect()
