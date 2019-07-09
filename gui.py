import tkinter as tk
from tkinter import ttk
from threading import Thread, Lock, Event
from laser import Laser
import time
from enum import Enum, auto
import math
import visa
from ThorlabsPM100 import ThorlabsPM100
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np

class Observable:
    def __init__(self, initial_value=None):
        self.data = initial_value
        self.callbacks = {}

    def addCallback(self, func):
        self.callbacks[func] = 1

    def delCallback(self, func):
        del self.callbacks[func]

    def _docallbacks(self):
        for func in self.callbacks:
            func(self.data)

    def set(self, data):
        self.data = data
        self._docallbacks()

    def get(self):
        return self.data

    def unset(self):
        self.data = None


class Controller:
    def __init__(self):
        self.model = Model()
        self.view = View(tk.Tk())
        self.progress = Controller.ProgressType.CONNECTION
        self.stop_standard_update = Event()
        self.gui_lock = self.view.lock
        self.clean_jump_frequency = 195
        self.clean_sweep_frequency = 50
        self.clean_sweep_speed = 20
        self.clean_scan_start = 192
        self.clean_scan_stop = 196
        self.stop_clean_scan = Event()
        self.take_scan_data = Event()

        self.view.navigation.button_close.add_callback(self.close)
        self.view.main_and_commands.commands.button_on.add_callback(self.laser_on)
        self.view.main_and_commands.commands.button_off.add_callback(self.laser_off)
        self.view.main_and_commands.commands.jump_entry.frequency_entry.frequency.addCallback(self.set_clean_jump)
        self.view.main_and_commands.commands.button_jump.add_callback(self.clean_jump)
        self.view.main_and_commands.commands.button_sweep.add_callback(self.clean_sweep)
        self.view.main_and_commands.commands.sweep_entry.frequency_entry.frequency.addCallback(
            self.set_clean_sweep_frequency)
        self.view.main_and_commands.commands.speed_entry.frequency_entry.frequency.addCallback(
            self.set_clean_sweep_speed)
        self.view.main_and_commands.commands.scan_start.frequency_entry.frequency.addCallback(self.set_scan_start_frequency)
        self.view.main_and_commands.commands.scan_start.change_frequency(self.clean_scan_start)
        self.view.main_and_commands.commands.scan_stop.frequency_entry.frequency.addCallback(self.set_scan_stop_frequency)
        self.view.main_and_commands.commands.scan_stop.change_frequency(self.clean_scan_stop)
        self.view.main_and_commands.commands.button_scan.add_callback(self.clean_scan)

        self.model.frequency.addCallback(self.frequency_changed)
        self.model.offset.addCallback(self.offset_changed)
        self.model.clean_jump_active.addCallback(self.clean_jump_active)
        self.model.power.addCallback(self.power_changed)
        self.model.on.addCallback(self.state)
        self.model.connected.addCallback(self.connected)
        self.model.clean_sweep_state.addCallback(self.clean_sweep_state)
        self.model.clean_scan_progress.addCallback(self.clean_scan_progress)
        self.model.clean_scan_active.addCallback(self.clean_scan_state)

        self.model.connect_laser()
        self.model.set_startup_frequency(195)

        self.view.bind_all("<1>", lambda event: event.widget.focus_set())
        self.view.mainloop()

    def power_changed(self, power):
        self.view.main_and_commands.status.set_power(round(power, 2))
        if self.progress == Controller.ProgressType.POWER:
            self.progress_bar(power / 10)

    def frequency_changed(self, frequency):
        self.view.main_and_commands.status.set_frequency(frequency)

    def offset_changed(self, offset_ghz):
        self.view.main_and_commands.status.set_offset(offset_ghz)
        if self.progress == Controller.ProgressType.OFFSET:
            progress = min(1 - math.sqrt(abs(offset_ghz / 10000)), 0)
            self.progress_bar(progress)
        elif self.progress is Controller.ProgressType.CLEAN_SWEEP:
            progress = 0.5 + offset_ghz / self.clean_sweep_frequency
            self.progress_bar(progress)

    def disconnect_laser(self):
        self.model.disconnect()

    def close(self):
        self.disconnect_laser()
        quit()

    def laser_on(self):
        self.view.main_and_commands.commands.button_on.disable()
        self.view.change_status('Powering laser on...')
        self.progress = Controller.ProgressType.POWER
        self.progress_bar(0)
        self.stop_standard_update.clear()
        laser_on_thread = Thread(target=self.model.laser_on)
        laser_on_thread.start()

    def laser_off(self):
        self.stop_standard_update.set()
        self.view.main_and_commands.commands.button_off.disable()
        self.view.change_status('Laser is off.')
        self.model.laser_off()

    def state(self, on):
        if on:
            self.view.main_and_commands.commands.button_on.disable()
            self.view.main_and_commands.commands.button_off.enable()
            self.view.main_and_commands.commands.button_jump.enable()
            self.view.main_and_commands.commands.button_sweep.enable()
            self.view.main_and_commands.commands.button_scan.enable()
            self.progress = Controller.ProgressType.NONE
            self.progress_bar(1)
            self.view.change_status('Laser is on.')

            laser_update_thread = Thread(target=self.model.standard_update,
                                         args=(self.gui_lock, self.stop_standard_update))
            laser_update_thread.start()
        else:
            self.view.main_and_commands.commands.button_on.enable()
            self.view.main_and_commands.commands.button_off.disable()
            self.view.main_and_commands.commands.button_scan.disable()
            self.view.main_and_commands.commands.button_sweep.disable()
            self.view.main_and_commands.commands.button_jump.disable()
            self.progress_bar(0)
            self.view.change_status("Laser is off.")

    def connected(self, connected):
        if connected:
            self.view.change_status('Connected to laser.')
            if self.progress == Controller.ProgressType.CONNECTION:
                self.progress_bar(1)
        else:
            self.view.change_status('Laser not connected')

    def set_clean_jump(self, frequency):
        self.clean_jump_frequency = frequency

    def clean_jump(self):
        clean_jump_thread = Thread(target=self.model.clean_jump, args=(self.clean_jump_frequency,))
        clean_jump_thread.start()

    def clean_jump_active(self, active):
        if active:
            self.progress = Controller.ProgressType.OFFSET
            self.view.main_and_commands.commands.button_jump.disable()
            self.view.main_and_commands.commands.button_scan.disable()
            self.view.change_status('Performing frequency jump...')
        else:
            self.progress = Controller.ProgressType.NONE
            self.progress_bar(1)
            self.view.main_and_commands.commands.button_jump.enable()
            self.view.main_and_commands.commands.button_scan.enable()
            self.view.change_status('Frequency jump complete.')

    def clean_sweep(self):
        if self.progress is not Controller.ProgressType.CLEAN_SWEEP:
            self.progress = Controller.ProgressType.CLEAN_SWEEP
            self.view.change_status("Performing frequency sweep...")
            self.view.main_and_commands.commands.button_sweep.change_text("Stop Sweep")
            self.view.main_and_commands.commands.button_jump.disable()
            self.view.main_and_commands.commands.button_scan.disable()
            clean_sweep_thread = Thread(target=self.model.clean_sweep_start,
                                        args=(self.clean_sweep_frequency, self.clean_sweep_speed))
            clean_sweep_thread.start()
        else:
            self.progress = Controller.ProgressType.NONE
            self.view.change_status("Frequency sweep stopped.")
            self.view.main_and_commands.commands.button_sweep.change_text("Frequency Sweep")
            self.model.clean_sweep_stop()
            self.progress_bar(0)
            self.view.main_and_commands.commands.button_jump.enable()
            self.view.main_and_commands.commands.button_scan.enable()

    def set_clean_sweep_frequency(self, frequency):
        self.clean_sweep_frequency = frequency

    def set_clean_sweep_speed(self, speed):
        self.clean_sweep_speed = speed

    def clean_sweep_state(self, state):
        if self.progress is Controller.ProgressType.CLEAN_SWEEP:
            self.view.change_status(state)

    def set_scan_start_frequency(self, start):
        self.clean_scan_start = start

    def set_scan_stop_frequency(self, stop):
        self.clean_scan_stop = stop

    def clean_scan(self):
        if self.progress is not Controller.ProgressType.CLEAN_SCAN:
            if self.clean_scan_start == self.clean_scan_stop:
                start = self.clean_scan_start
                stop = start + 0.05
            elif self.clean_scan_start > self.clean_scan_stop:
                start = self.clean_scan_stop
                stop = self.clean_scan_start
            else:
                start = self.clean_scan_start
                stop = self.clean_scan_stop
            self.progress = Controller.ProgressType.CLEAN_SCAN
            self.stop_clean_scan.clear()
            self.stop_standard_update.set()
            clean_scan_thread = Thread(target=self.model.clean_scan,
                                       args=(start, stop, self.stop_clean_scan, self.take_scan_data))
            scan_update_thread = Thread(target=self.model.scan_update,
                                        args=(self.gui_lock, self.stop_clean_scan, self.take_scan_data))
            clean_scan_thread.start()
            scan_update_thread.start()
        else:
            self.stop_clean_scan.set()
            self.view.change_status("Stopping clean scan...")
            self.view.main_and_commands.commands.button_scan.disable()

    def clean_scan_state(self, state):
        if state:
            self.progress = Controller.ProgressType.CLEAN_SCAN
            self.progress_bar(0)
            self.view.change_status("Performing frequency scan...")
            self.view.main_and_commands.commands.button_scan.change_text("Stop Scan")
            self.view.main_and_commands.commands.button_jump.disable()
            self.view.main_and_commands.commands.button_sweep.disable()
        else:
            self.stop_clean_scan.set()
            self.progress = Controller.ProgressType.NONE
            self.progress_bar(0)
            self.view.change_status("Frequency scan complete.")
            self.view.main_and_commands.commands.button_scan.enable()
            self.view.main_and_commands.commands.button_jump.enable()
            self.view.main_and_commands.commands.button_sweep.enable()
            self.view.main_and_commands.commands.button_scan.change_text("Frequency Scan")

    def clean_scan_progress(self, progress):
        if self.progress == Controller.ProgressType.CLEAN_SCAN:
            self.progress_bar(progress)

    def progress_bar(self, progress):
        self.view.change_progress(100 * progress)

    class ProgressType(Enum):
        NONE = auto()
        CONNECTION = auto()
        POWER = auto()
        OFFSET = auto()
        CLEAN_SWEEP = auto()
        CLEAN_SCAN = auto()


class Model:
    def __init__(self):
        self.frequency = Observable()
        self.power = Observable(0)
        self.offset = Observable(0)
        self.on = Observable(False)
        self.connected = Observable(False)
        self.clean_jump_active = Observable(False)
        self.clean_scan_active = Observable(False)
        self.clean_scan_progress = Observable()
        self.clean_sweep_state = Observable()

        self.lock = Lock()

        self.laser = None
        self.power_meter = None

    def set_startup_frequency(self, frequency):
        self.frequency.set(frequency)

    def connect_laser(self):
        with self.lock:
            self.laser = Laser()
            self.connected.set(True)

    def connect_pm(self):
        rm = visa.ResourceManager()
        resources = rm.list_resources()
        inst = rm.open_resource(resources[0])
        print(inst.query('*IDN?'))
        self.power_meter = ThorlabsPM100(inst=inst)

    def laser_on(self):
        with self.lock:
            self.laser.startup_begin(self.frequency.get())

            while self.power.get() < 9.99:
                self.power.set(self.laser.check_power())

            while self.laser.check_nop() > 16:
                time.sleep(0.001)

            self.laser.startup_finish()
            self.power.set(self.laser.check_power())
            self.on.set(True)

    def laser_off(self):
        with self.lock:
            self.laser.laser_off()
            self.power.set(0)
            self.on.set(False)

    def disconnect(self):
        with self.lock:
            if self.laser:
                self.laser.itla_disconnect()
            self.connected.set(False)

    def standard_update(self, gui_lock: Lock, update_stop_event: Event):
        while not update_stop_event.is_set():
            with self.lock and gui_lock:
                self.power.set(self.laser.check_power())
                freq_thz = self.laser.read(Laser.REG_FreqTHz)
                freq_ghz = self.laser.read(Laser.REG_FreqGHz)
                self.frequency.set(freq_thz + freq_ghz / 10000)
                self.offset.set(self.laser.offset())

    def scan_update(self, gui_lock: Lock, end_event: Event, take_data: Event):
        self.connect_pm()
        while not end_event.is_set():
            if take_data.wait(timeout=1):
                with self.lock and gui_lock:
                    input_power = self.laser.check_power()
                    self.power.set(input_power)
                    freq_thz = self.laser.read(Laser.REG_FreqTHz)
                    freq_ghz = self.laser.read(Laser.REG_FreqGHz)
                    frequency = freq_thz + freq_ghz / 10000
                    offset = self.laser.offset()
                    self.frequency.set(frequency)
                    self.offset.set(offset)
                    output_power = self.power_meter.read

    def clean_jump(self, frequency):
        self.clean_jump_active.set(True)
        with self.lock:
            self.laser.clean_jump_start(frequency)

        # Read the frequency error and wait until it is below a threshold or 2 seconds passes
        wait_time = time.perf_counter() + 2

        with self.lock:
            error_read = self.laser.read(Laser.REG_Cjumpoffset)
        freq_error = error_read / 10.0
        self.offset.set(freq_error)

        while abs(freq_error) > 0.1 and time.perf_counter() < wait_time:
            with self.lock:
                error_read = self.laser.read(Laser.REG_Cjumpoffset)
            freq_error = error_read / 10.0
            self.offset.set(freq_error)

        with self.lock:
            self.laser.wait_nop()

        # Read out the laser's claimed frequency
        with self.lock:
            claim_thz = self.laser.read(Laser.REG_GetFreqTHz)
            claim_ghz = self.laser.read(Laser.REG_GETFreqGHz) / 10
        claim_freq = claim_thz + claim_ghz / 1000.0

        self.frequency.set(claim_freq)

        print('Laser\'s claimed frequency: %f' % claim_freq)

        with self.lock:
            self.laser.clean_jump_finish()

        self.clean_jump_active.set(False)

    def clean_sweep_start(self, frequency, speed):
        self.clean_sweep_state.set("Preparing for clean sweep...")
        with self.lock:
            self.laser.clean_sweep_prep(frequency, int(speed * 1000))

        time.sleep(1)

        self.clean_sweep_state.set("Running clean sweep.")
        with self.lock:
            self.laser.clean_sweep_start()

    def clean_sweep_stop(self):
        with self.lock:
            self.laser.clean_sweep_stop()
        self.clean_sweep_state.set(None)

    def clean_scan(self, start_frequency: float, stop_frequency: float, stop: Event, take_data: Event):
        assert stop_frequency > start_frequency
        jump_frequency = start_frequency
        self.clean_scan_active.set(True)
        self.clean_scan_progress.set(0)
        take_data.clear()

        while jump_frequency < stop_frequency + 0.05 and not stop.is_set():
            power_reference = self.power.get()

            with self.lock:
                self.laser.clean_jump(jump_frequency)

            with self.lock:
                self.laser.wait_nop()

            time_wait = time.perf_counter() + 1

            while self.power.get() < 0.8 * power_reference and time.perf_counter() < time_wait:
                time.sleep(.1)

            time.sleep(0.5)

            power_reference = self.power.get()

            self.clean_sweep_start(50, 20)
            take_data.set()

            while self.offset.get() > -10 and not stop.is_set():
                time.sleep(.1)

            while self.offset.get() < 1 and not stop.is_set():
                time.sleep(0.1)

            take_data.clear()
            with self.lock:
                self.laser.clean_sweep_stop()

            with self.lock:
                self.laser.wait_nop()

            time_wait = time.perf_counter() + 5

            while self.power.get() < 0.95 * power_reference and time.perf_counter() < time_wait:
                time.sleep(.1)

            jump_frequency += 0.05
            self.clean_scan_progress.set((jump_frequency - start_frequency) / (stop_frequency - start_frequency))

        time.sleep(1)
        self.clean_scan_active.set(False)


class View(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent
        self.lock = Lock()

        # self.tk.iconbitmap(self, default="favicon.ico")
        # self.tk.wm_title(self, "ITLA-PPCL550 Control")

        self.main_and_commands = Main(self)
        self.navigation = NavigationBar(self)

        self.main_and_commands.pack(side="right", fill="both", expand=True)
        self.navigation.pack(side="left", fill="y", expand=False)

        self.pack(fill="both", expand=True)

    def connect_laser(self):
        self.main_and_commands.status.status.config(text="Laser connected.")
        self.main_and_commands.status.progress_bar.config(value=100)

    def change_power(self, power):
        self.main_and_commands.status.set_power(power)

    def change_frequency(self, frequency):
        self.main_and_commands.status.set_frequency(frequency)

    def change_status(self, status):
        self.main_and_commands.status.set_status(status)

    def change_progress(self, progress):
        self.main_and_commands.status.set_progress(progress)


class Main(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.status = Status(self)
        self.main = Context(self)
        self.top_separator = ttk.Separator(self)
        self.bottom_separator = ttk.Separator(self)
        self.commands = CommandBar(self)

        self.status.pack(padx=10, pady=10, fill="x", expand=False)
        self.top_separator.pack(fill="x", padx=10, pady=5)
        self.main.pack(fill="both", expand=True)
        self.bottom_separator.pack(fill="x", padx=10, pady=5)
        self.commands.pack(fill="x", expand=False)


class Context(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.blank = BlankContext(self)
        self.mode_finder = GraphContext(self)
        self.power = GraphContext(self)

        # self.mode_finder.pack(fill="both", expand=True)
        self.power.pack(fill="both", expand=True)


class BlankContext(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.pack(fill="both", expand=True)


class GraphContext(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.sub_plot = self.fig.add_subplot(111)
        self.line, = self.sub_plot.plot([], [])
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)

    def plot(self, x, y):
        if len(x) > 0:
            self.line.set_data(x, y)
            ax = self.canvas.figure.axes[0]
            ax.set_xlim(x.min(), x.max())
            ax.set_ylim(y.min(), y.max())
            self.canvas.draw()

class Status(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        style = ttk.Style()
        style.configure("GREY.TLabel", foreground="black", background="#ccc")

        self.status = ttk.Label(self, text="Connecting to laser...")
        self.progress_bar = ttk.Progressbar(self, length=200, value=0)
        self.info = InfoGrid(self)

        self.status.pack(pady=5, padx=10, expand=True)
        self.progress_bar.pack(pady=5, padx=20, fill="x", expand=False)
        self.info.pack(pady=5, padx=20, fill="x", expand=True)

    def set_power(self, power):
        self.info.power.config(text="Power: {} dBm".format(power))

    def set_frequency(self, frequency):
        self.info.frequency.config(text="Center Frequency: {} THz".format(frequency))

    def set_offset(self, offset):
        self.info.offset.config(text="Frequency Offset: {} GHz".format(offset))

    def set_status(self, status):
        self.status.config(text=status)

    def set_progress(self, progress):
        self.progress_bar.config(value=progress)


class InfoGrid(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent)
        self.parent = parent

        full_sticky = tk.N + tk.S + tk.E + tk.W

        for c in range(3):
            self.grid_columnconfigure(c, weight=1)

        self.power = ttk.Label(self, text="Power: 0 dBm", style="GREY.TLabel")
        self.frequency = ttk.Label(self, text="Center Frequency:", style="GREY.TLabel")
        self.offset = ttk.Label(self, text="Frequency Offset: 0 GHz", style="GREY.TLabel")

        self.power.grid(row=0, column=0, ipadx=5, ipady=5, padx=5, sticky=full_sticky)
        self.frequency.grid(row=0, column=1, ipadx=5, ipady=5, padx=5, sticky=full_sticky)
        self.offset.grid(row=0, column=2, ipadx=5, ipady=5, padx=5, sticky=full_sticky)


class NavigationBar(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent)
        self.parent = parent

        self.button_home = NavigationButton(self, "Home", None)
        self.button_power = NavigationButton(self, "Power Monitor", None)
        self.button_frequency = NavigationButton(self, "Frequency Monitor", None)
        self.button_mode_finder = NavigationButton(self, "Comb Mode Finder", None)
        self.button_close = NavigationButton(self, "Close", None)

        self.button_home.pack(fill="both", expand=True)
        self.button_power.pack(fill="both", expand=True)
        self.button_frequency.pack(fill="both", expand=True)
        self.button_mode_finder.pack(fill="both", expand=True)
        self.button_close.pack(fill="both", expand=True)


class NavigationButton(tk.Frame):
    def __init__(self, parent, label, action, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.button = ttk.Button(self, text=label, command=action, width=20)
        self.button.pack(pady=5, ipady=20, fill="both", expand=True)

    def add_callback(self, callback):
        self.button.config(command=callback)

    def disable(self):
        self.button.state(['disabled'])

    def enable(self):
        self.button.state(['!disabled'])


class CommandBar(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        full_sticky = tk.N + tk.S + tk.E + tk.W

        for c in range(7):
            self.grid_columnconfigure(c, weight=1)

        self.button_on = CommandButton(self, "Laser On", None)
        self.button_on.grid(row=0, column=0, sticky=full_sticky)
        self.button_off = CommandButton(self, "Laser Off", None)
        self.button_off.grid(row=1, column=0, sticky=full_sticky)
        self.button_off.disable()

        self.jump_entry = FrequencyEntryAndLabel(self, "Jump frequency (THz):")
        self.jump_entry.grid(row=0, column=1, padx=5)
        self.button_jump = CommandButton(self, "Frequency Jump", None)
        self.button_jump.grid(row=1, column=1, sticky=full_sticky)
        self.button_jump.disable()

        self.sweep_entry = FrequencyEntryAndLabel(self, "Sweep range (GHz)", 50, 0, 50)
        self.sweep_entry.grid(row=0, column=2, padx=5)
        self.speed_entry = FrequencyEntryAndLabel(self, "Sweep speed (GHz/sec)", 20, 0, 50)
        self.speed_entry.grid(row=0, column=3, padx=5)
        self.button_sweep = CommandButton(self, "Frequency Sweep", None)
        self.button_sweep.grid(row=1, column=2, columnspan=2, sticky=full_sticky)
        self.button_sweep.disable()

        self.scan_start = FrequencyEntryAndLabel(self, "Scan start frequency (THz):")
        self.scan_start.grid(row=0, column=4, padx=5)
        self.scan_stop = FrequencyEntryAndLabel(self, "Scan stop frequency (THz):")
        self.scan_stop.grid(row=0, column=5, padx=5)
        self.button_scan = CommandButton(self, "Frequency Scan", None)
        self.button_scan.grid(row=1, column=4, columnspan=2, sticky=full_sticky)
        self.button_scan.disable()


class FrequencyEntryAndLabel(tk.Frame):
    def __init__(self, parent, label, freq=195, min_freq=191.5, max_freq=196.25, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.label = ttk.Label(self, text=label)
        self.label.pack(side="top", expand=True, fill="both")

        self.frequency_entry = FrequencyEntry(self, freq, min_freq, max_freq)
        self.frequency_entry.pack(side="bottom", expand=True, fill="both")

    def change_frequency(self, frequency):
        self.frequency_entry.frequency.set(frequency)
        self.frequency_entry.entry.config(text=str(frequency))


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
        self.frequency = Observable(freq)

        self.entry.insert(0, str(self.frequency.get()))

    def value(self):
        return self.entry.get()

    def validate(self, action, index, value_if_allowed,
                 prior_value, text, validation_type, trigger_type, widget_name):
        if text in '0123456789.-+':
            try:
                value_float = float(value_if_allowed)

                if self.min_freq < value_float < self.max_freq:
                    self.frequency.set(round(value_float, 4))
                    self.entry.delete(0, tk.END)
                    self.entry.insert(0, str(self.frequency.get()))
                    return True
                else:
                    self.bell()
                    self.entry.delete(0, tk.END)
                    self.entry.insert(0, str(self.frequency.get()))
                    return False

            except ValueError:
                self.bell()
                self.entry.delete(0, tk.END)
                self.entry.insert(0, str(self.frequency.get()))
                return False
        else:
            self.bell()
            self.entry.delete(0, tk.END)
            self.entry.insert(0, str(self.frequency.get()))
            return False


class CommandButton(tk.Frame):
    def __init__(self, parent, label, action, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        full_sticky = tk.N + tk.S + tk.E + tk.W

        self.button = ttk.Button(self, text=label, command=action, width=-20)
        self.button.pack(fill="both", pady=5, padx=10, ipady=5)

    def disable(self):
        self.button.state(['disabled'])

    def enable(self):
        self.button.state(['!disabled'])

    def add_callback(self, callback):
        self.button.config(command=callback)

    def change_text(self, text):
        self.button.config(text=text)


app = None
try:
    app = Controller()

finally:
    if app:
        app.disconnect_laser()
