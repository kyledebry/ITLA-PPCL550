import datetime
import tkinter as tk
from queue import Queue
from tkinter import ttk
from threading import Thread, Lock, Event
from laser import Laser
import time
from enum import Enum, auto
import math
import visa
from ThorlabsPM100 import ThorlabsPM100
from matplotlib import pyplot as plt
import matplotlib.animation as animation
from matplotlib import style
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import scipy.interpolate


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
        self.root = tk.Tk()
        self.view = View(self.root)
        self.progress = Controller.ProgressType.CONNECTION
        self.stop_standard_update = Event()
        self.gui_lock = self.view.lock
        self.clean_jump_frequency = 195
        self.clean_sweep_frequency = 50
        self.clean_sweep_speed = 20
        self.clean_scan_start = 192
        self.clean_scan_stop = 196
        self.clean_scan_speed = 10
        self.stop_clean_scan = Event()
        self.take_scan_data = Event()
        self.scan_data = {'x': np.array([]), 'y': np.array([])}
        self.power_data = {'t': [], 'p': []}
        self.sweep_data = {'x': np.array([]), 'y': np.array([])}
        self.sweep_to = 0

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
        self.view.main_and_commands.commands.scan_start.frequency_entry.frequency.addCallback(
            self.set_scan_start_frequency)
        self.view.main_and_commands.commands.scan_start.change_frequency(self.clean_scan_start)
        self.view.main_and_commands.commands.scan_stop.frequency_entry.frequency.addCallback(
            self.set_scan_stop_frequency)
        self.view.main_and_commands.commands.scan_stop.change_frequency(self.clean_scan_stop)
        self.view.main_and_commands.commands.scan_speed_entry.frequency_entry.frequency.addCallback(
            self.set_clean_scan_speed)
        self.view.main_and_commands.commands.button_scan.add_callback(self.clean_scan)
        self.view.navigation.button_power.add_callback(self.go_to_power_monitor)
        self.view.navigation.button_mode_finder.add_callback(self.go_to_scan_monitor)
        self.view.navigation.button_sweep.add_callback(self.sweep_monitor)

        self.model.frequency.addCallback(self.frequency_changed)
        self.model.offset.addCallback(self.offset_changed)
        self.model.clean_jump_active.addCallback(self.clean_jump_active)
        self.model.power.addCallback(self.power_changed)
        self.model.on.addCallback(self.state)
        self.model.connected.addCallback(self.connected)
        self.model.clean_sweep_state.addCallback(self.clean_sweep_state)
        self.model.clean_scan_progress.addCallback(self.clean_scan_progress)
        self.model.clean_scan_active.addCallback(self.clean_scan_state)
        self.model.scan_data.addCallback(self.set_scan_data)
        self.model.scan_data_old.addCallback(self.set_scan_data_old)
        self.model.scan_time_remaining.addCallback(self.scan_time_remaining)
        self.model.scan_update_active.addCallback(lambda x: self.stop_standard_update.set() if x
                                                  else self.stop_standard_update.clear())

        self.view.bind_all("<Left>", self.key_jump)
        self.view.bind_all("<Right>", self.key_jump)
        self.view.bind_all("<Shift-Left>", self.key_shift_jump)
        self.view.bind_all("<Shift-Right>", self.key_shift_jump)

        self.model.connect_laser()
        self.model.set_startup_frequency(195)

        self.view.bind_all("<1>", lambda event: event.widget.focus_set())

        self.scan_plot_animation = animation.FuncAnimation(self.view.main_and_commands.main.mode_finder.fig,
                                                           self.animate_power_plot, interval=200)
        self.power_plot_animation = animation.FuncAnimation(self.view.main_and_commands.main.power.fig,
                                                            self.animate_scan_plot, interval=200)
        self.sweep_plot_animation = animation.FuncAnimation(self.view.main_and_commands.main.sweep.fig,
                                                            self.animate_sweep_plot, interval=200)
        self.go_to_power_monitor()

        self.root.mainloop()

    def animate_scan_plot(self, i):
        if self.progress == Controller.ProgressType.CLEAN_SCAN:
            if self.scan_data['x'].size > 1:
                x = self.scan_data['x']
                y = self.scan_data['y']
                if x.size == y.size:
                    self.view.main_and_commands.main.mode_finder.plot(x, y)

    def animate_power_plot(self, i):
        if len(self.power_data['t']) > 1 and self.progress != Controller.ProgressType.CLEAN_SWEEP_MONITOR:
            self.view.main_and_commands.main.power.plot(np.array(self.power_data['t']), np.array(self.power_data['p']),
                                                        max_x_width=30)

    def animate_sweep_plot(self, i):
        if self.sweep_data['x'].size > 1 and self.progress == Controller.ProgressType.CLEAN_SWEEP_MONITOR:
            x = self.sweep_data['x']
            y = self.sweep_data['y']
            if x.size == y.size:
                self.view.main_and_commands.main.sweep.plot(x, y)

    def power_changed(self, power):
        self.view.main_and_commands.status.set_power(round(power, 2))
        if self.progress == Controller.ProgressType.POWER:
            self.progress_bar(power / 10)

        self.power_data['t'].append(time.perf_counter())
        self.power_data['p'].append(power)

    def frequency_changed(self, frequency):
        self.view.main_and_commands.status.set_frequency(frequency)

    def offset_changed(self, offset_ghz):
        self.view.main_and_commands.status.set_offset(offset_ghz)
        if self.progress == Controller.ProgressType.OFFSET:
            progress = min(1 - math.sqrt(abs(offset_ghz / 10000)), 0)
            self.progress_bar(progress)
        elif self.progress is Controller.ProgressType.CLEAN_SWEEP:
            progress = 0.5 + offset_ghz / (self.clean_sweep_frequency + 0.0001)
            self.progress_bar(progress)

    def disconnect_laser(self):
        self.model.disconnect()

    def close(self):
        self.stop_standard_update.set()
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
        self.view.main_and_commands.commands.button_off.enable()
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
            self.view.main_and_commands.commands.button_off.enable()
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

    def go_to_power_monitor(self):
        self.view.main_and_commands.main.power.switch_to()
        self.view.navigation.button_mode_finder.enable()
        self.view.navigation.button_power.disable()

    def go_to_scan_monitor(self):
        self.view.main_and_commands.main.mode_finder.switch_to()
        self.view.navigation.button_mode_finder.disable()
        self.view.navigation.button_power.enable()

    def set_clean_jump(self, frequency):
        self.clean_jump_frequency = frequency

    def clean_jump(self):
        clean_jump_thread = Thread(target=self.model.clean_jump, args=(self.clean_jump_frequency,))
        clean_jump_thread.start()

    def key_jump(self, event):
        print(event)
        print(event.keysym)

        if self.model.on.get() and self.progress == Controller.ProgressType.NONE:
            new_freq = round(self.model.frequency.get(), 4)
            if event.keysym == "Right":
                new_freq += 0.00012
            elif event.keysym == "Left":
                new_freq -= 0.00012
            key_jump_thread = Thread(target=self.model.clean_jump, args=(new_freq,))
            key_jump_thread.start()
        elif self.model.on.get() and self.progress in (Controller.ProgressType.CLEAN_SWEEP_MONITOR,
                                                       Controller.ProgressType.CLEAN_SWEEP):
            if event.keysym == "Right":
                self.sweep_to += 1
            elif event.keysym == "Left":
                self.sweep_to -= 1
            key_sweep_to_thread = Thread(target=self.model.clean_sweep_to_offset, args=(self.sweep_to,))
            key_sweep_to_thread.start()

    def key_shift_jump(self, event):
        print(event)
        print(event.keysym)
        new_freq = round(self.model.frequency.get(), 4)
        if event.keysym == "Right":
            new_freq += 0.001
        elif event.keysym == "Left":
            new_freq -= 0.001
        key_jump_thread = Thread(target=self.model.clean_jump, args=(new_freq,))
        if self.model.on.get() and self.progress == Controller.ProgressType.NONE:
            key_jump_thread.start()

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
        if self.progress not in (Controller.ProgressType.CLEAN_SWEEP, Controller.ProgressType.CLEAN_SWEEP_MONITOR):
            self.progress = Controller.ProgressType.CLEAN_SWEEP
            self.view.change_status("Performing frequency sweep...")
            self.view.main_and_commands.commands.button_sweep.change_text("Stop Sweep")
            self.view.main_and_commands.commands.button_jump.disable()
            self.view.main_and_commands.commands.button_scan.disable()
            self.sweep_to = 0
            clean_sweep_thread = Thread(target=self.model.clean_sweep_start,
                                        args=(self.clean_sweep_frequency, self.clean_sweep_speed))
            clean_sweep_thread.start()
        else:
            self.progress = Controller.ProgressType.NONE
            self.view.change_status("Frequency sweep stopped.")
            self.view.main_and_commands.commands.button_sweep.change_text("Frequency Sweep")
            Thread(target=self.model.clean_sweep_stop).start()
            self.progress_bar(0)
            self.view.main_and_commands.commands.button_jump.enable()
            self.view.main_and_commands.commands.button_scan.enable()
            self.stop_clean_scan.set()
            self.take_scan_data.clear()

    def set_clean_sweep_frequency(self, frequency):
        self.clean_sweep_frequency = frequency

    def set_clean_sweep_speed(self, speed):
        self.clean_sweep_speed = speed

    def clean_sweep_state(self, state):
        if self.progress in (Controller.ProgressType.CLEAN_SWEEP, Controller.ProgressType.CLEAN_SWEEP_MONITOR):
            self.view.change_status(state)

    def set_scan_start_frequency(self, start):
        self.clean_scan_start = start

    def set_scan_stop_frequency(self, stop):
        self.clean_scan_stop = stop

    def set_clean_scan_speed(self, speed):
        self.clean_scan_speed = speed

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
            self.view.change_status("Starting scan...")
            self.view.main_and_commands.commands.button_scan.disable()
            self.view.main_and_commands.commands.button_jump.disable()
            self.view.main_and_commands.commands.button_sweep.disable()
            self.stop_clean_scan.clear()
            clean_scan_thread = Thread(target=self.model.clean_scan,
                                       args=(start, stop, self.clean_scan_speed,
                                             self.stop_clean_scan, self.take_scan_data))
            scan_update_thread = Thread(target=self.model.scan_update,
                                        args=(self.stop_clean_scan, self.take_scan_data))
            clean_scan_thread.start()
            scan_update_thread.start()
        else:
            self.stop_clean_scan.set()
            self.view.change_status("Stopping scan...")
            self.view.main_and_commands.commands.button_scan.disable()

    def clean_scan_state(self, state):
        if state:
            self.progress = Controller.ProgressType.CLEAN_SCAN
            self.progress_bar(0)
            self.view.change_status("Performing frequency scan...")
            self.view.main_and_commands.commands.button_scan.change_text("Stop Scan")
            self.view.main_and_commands.commands.button_jump.disable()
            self.view.main_and_commands.commands.button_sweep.disable()
            self.view.main_and_commands.commands.button_scan.enable()
            self.go_to_scan_monitor()
        else:
            self.stop_clean_scan.set()
            self.progress = Controller.ProgressType.NONE
            self.progress_bar(0)
            self.view.change_status("Frequency scan complete.")
            self.view.main_and_commands.commands.button_scan.enable()
            self.view.main_and_commands.commands.button_jump.enable()
            self.view.main_and_commands.commands.button_sweep.enable()
            self.view.main_and_commands.commands.button_scan.change_text("Frequency Scan")
            self.stop_standard_update.clear()
            laser_update_thread = Thread(target=self.model.standard_update,
                                         args=(self.gui_lock, self.stop_standard_update))
            laser_update_thread.start()

            current_date_time = datetime.datetime.now()

            dt = current_date_time.strftime("%Y-%m-%d_%H-%M-%S")

            with open("scan_transmission_{}.csv".format(dt), "w") as fp:
                for freq, transmission in zip(self.scan_data['x'], self.scan_data['y']):
                    fp.write(str(freq) + ',' + str(transmission) + '\n')

    def clean_scan_progress(self, progress):
        if self.progress == Controller.ProgressType.CLEAN_SCAN:
            self.progress_bar(progress)

    def set_scan_data(self, data):
        # print(data)
        if len(data['f']) > 5 and len(data['p_out']) > 5:
            f = scipy.interpolate.interp1d(data['t_laser'], data['f'], kind='cubic', fill_value="extrapolate")(
                np.array(data['t_pm']))
            p_in = scipy.interpolate.interp1d(data['t_laser'], data['p_in'], kind='cubic', fill_value="extrapolate")(
                np.array(data['t_pm']))
            p_out = np.array(data['p_out'])
            p_rel = p_out / p_in

            self.scan_data['x'] = f
            self.scan_data['y'] = p_rel

    def set_scan_data_old(self, data):
        if len(data['f']) > 5:
            self.scan_data['x'] = np.array(data['f'])
            self.scan_data['y'] = np.array(data['t'])

            if self.progress == Controller.ProgressType.CLEAN_SWEEP_MONITOR:
                min_freq = self.clean_jump_frequency - self.clean_sweep_frequency / 2000
                max_freq = self.clean_jump_frequency + self.clean_sweep_frequency / 2000
                i = 1
                while self.scan_data['x'][-i] < 0.8 * max_freq + 0.2 * min_freq and i < len(self.scan_data['x']):
                    i += 1
                max_i = i
                i = 1
                while self.scan_data['x'][-i] > 0.8 * min_freq + 0.2 * max_freq and i < len(self.scan_data['x']):
                    i += 1
                min_i = i
                keep_data = min(int(abs(max_i - min_i) * 2.1), len(self.scan_data['x']))
                self.sweep_data['x'] = self.scan_data['x'][-keep_data:]
                self.sweep_data['y'] = self.scan_data['y'][-keep_data:]

    def scan_time_remaining(self, time_remaining):
        if self.progress == Controller.ProgressType.CLEAN_SCAN and isinstance(time_remaining, int):
            self.view.change_status("Performing frequency scan ({} minutes remaining)...".format(time_remaining))

    def sweep_monitor(self):
        self.sweep_data = {'x': np.array([]), 'y': np.array([])}
        self.scan_data = {'x': np.array([]), 'y': np.array([])}
        self.view.main_and_commands.main.sweep.switch_to()
        self.view.navigation.button_sweep.disable()
        self.view.navigation.button_mode_finder.enable()
        self.view.navigation.button_power.enable()
        self.progress = Controller.ProgressType.CLEAN_SWEEP_MONITOR

        self.stop_clean_scan.clear()
        self.take_scan_data.set()
        if not self.model.power_meter_connected.is_set():
            pm_thread = Thread(target=self.model.connect_pm)
            pm_thread.start()
        scan_update_thread = Thread(target=self.model.scan_update,
                                    args=(self.stop_clean_scan, self.take_scan_data))
        scan_update_thread.start()

    def progress_bar(self, progress):
        self.view.change_progress(100 * progress)

    class ProgressType(Enum):
        NONE = auto()
        CONNECTION = auto()
        POWER = auto()
        OFFSET = auto()
        CLEAN_SWEEP = auto()
        CLEAN_SCAN = auto()
        CLEAN_SWEEP_MONITOR = auto()


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
        self.scan_data = Observable({'t_laser': [], 'f': [], 'p_in': [], 't_pm': [], 'p_out': []})
        self.scan_data_old = Observable({'f': [], 't': []})
        self.scan_time_remaining = Observable()
        self.scan_update_active = Observable(False)

        self.lock = Lock()
        self.data_lock = Lock()

        self.laser = None
        self.power_meter = None
        self.power_meter_connected = Event()
        self.power_meter_connected.clear()
        self.power_meter_thread = None
        self.power_meter_stop = Event()

    def set_startup_frequency(self, frequency):
        self.frequency.set(frequency)

    def connect_laser(self):
        with self.lock:
            self.laser = Laser()
            self.connected.set(True)

    def connect_pm(self):
        rm = visa.ResourceManager()
        resources = rm.list_resources()
        print(resources)
        inst = rm.open_resource(resources[0])
        inst.timeout = 5000
        print(inst.query('*IDN?'))
        self.power_meter = ThorlabsPM100(inst=inst)
        self.power_meter_connected.set()

    def laser_on(self):
        with self.lock:
            self.laser.startup_begin(self.frequency.get())

            while self.laser.check_nop() > 16:
                self.power.set(self.laser.check_power())

            self.on.set(True)

    def laser_off(self):
        # with self.lock:
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
            time.sleep(0.01)
            with self.lock:
                if not update_stop_event.is_set():
                    self.power.set(self.laser.check_power())
                    freq_thz = self.laser.read(Laser.REG_FreqTHz)
                    freq_ghz = self.laser.read(Laser.REG_FreqGHz)
                    self.frequency.set(freq_thz + freq_ghz / 10000)
                    self.offset.set(self.laser.offset())

    def scan_update(self, end_event: Event, take_data: Event):
        self.power_meter_connected.wait()
        print('PM connected')
        t_prev = None
        p_prev = None
        f_prev = None

        stop_pm_event = Event()
        power_queue = Queue()
        time_queue = Queue()

        pm_read_thread = Thread(target=self.pm_read, args=(time_queue, power_queue, stop_pm_event))
        pm_read_thread.start()

        self.scan_update_active.set(True)

        while not end_event.is_set():
            queue = Queue(maxsize=1)
            laser_read_thread = Thread(target=self.laser_read, args=(queue,))
            laser_read_thread.start()
            output_powers_list = []
            measured_time_list = []

            laser_read_thread.join()

            stop_pm_event.set()
            pm_read_thread.join()

            while not time_queue.empty():
                measured_time_list.append(time_queue.get())

            while not power_queue.empty():
                output_powers_list.append(power_queue.get())

            pm_read_thread = Thread(target=self.pm_read, args=(time_queue, power_queue, stop_pm_event))
            stop_pm_event.clear()
            pm_read_thread.start()

            output_powers = np.array(output_powers_list)
            measured_time = np.array(measured_time_list)

            p_new, offset, t_end = queue.get()
            self.power.set(p_new)
            self.offset.set(offset)
            f_new = self.frequency.get() + offset / 1000

            if t_prev and f_prev and p_prev:
                assert isinstance(f_prev, float)
                assert isinstance(p_prev, float)

                t_duration = t_end - t_prev
                interpolation = ((measured_time - t_prev) / t_duration)
                frequencies = list(interpolation * f_new + (1 - interpolation) * f_prev)
                input_powers = interpolation * p_new + (1 - interpolation) * p_prev
                input_powers_watts = np.power(10, input_powers / 10) / 1000
                relative_powers = list(output_powers / input_powers_watts)

                if abs(offset) < 20 and abs(p_new - 10) < 0.03 and abs(f_prev - f_new) < 0.1 and take_data.is_set():
                    with self.data_lock:
                        data = self.scan_data_old.get()
                        data['f'] += frequencies
                        data['t'] += relative_powers
                        self.scan_data_old.set(data)

            t_prev = t_end
            f_prev = f_new
            p_prev = p_new
        self.scan_update_active.set(False)

    def laser_read(self, queue: Queue):
        with self.lock:
            input_power = self.laser.check_power()
            offset = self.laser.offset()
            t = time.perf_counter()
        results = input_power, offset, t

        queue.put(results)

    def pm_read(self, time_queue: Queue, power_queue: Queue, stop: Event):
        while not stop.is_set():
            power_queue.put(self.power_meter.read)
            time_queue.put(time.perf_counter())

    def pm_update(self, end_event: Event, take_data: Event):
        self.power_meter_connected.wait()
        while not end_event.is_set():
            if take_data.is_set():
                power_out = self.power_meter.read
                with self.data_lock:
                    data = self.scan_data.get()
                    if len(data['t_laser']) > 1 and abs(data['t_laser'][-1] - time.perf_counter()) < 2E-1:
                        data['t_pm'].append(time.perf_counter())
                        data['p_out'].append(power_out)
                        self.scan_data.set(data)

    def clean_jump(self, frequency):
        self.clean_jump_active.set(True)
        self.clean_sweep_stop()
        with self.lock:
            self.laser.wait_nop()
        power_reference = self.power.get()
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

        time_wait = time.perf_counter() + 1

        while self.power.get() < 0.8 * power_reference and time.perf_counter() < time_wait:
            time.sleep(.1)

        self.clean_sweep_start(0, 1)

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

    def clean_sweep_to_offset(self, offset):
        self.clean_sweep_state.set("Sweeping to offset of {} GHz".format(offset))
        with self.lock:
            self.laser.clean_sweep_to_offset(offset)

        while abs(self.offset.get() - offset) > 0.1:
            time.sleep(0.1)
        self.clean_sweep_state.set("Pausing sweep at offset of {} GHz".format(offset))

    def clean_scan(self, start_frequency: float, stop_frequency: float, speed: float, stop: Event, take_data: Event):
        assert stop_frequency > start_frequency
        if not self.power_meter_connected.is_set():
            self.connect_pm()
        jump_frequency = start_frequency
        self.clean_scan_active.set(True)
        self.clean_scan_progress.set(0)
        self.scan_data.set({'t_laser': [], 'f': [], 'p_in': [], 't_pm': [], 'p_out': []})
        self.scan_data_old.set({'f': [], 't': []})
        take_data.clear()
        # self.power_meter_thread = Thread(target=self.pm_update, args=(stop, take_data))
        # self.power_meter_thread.start()

        scan_start_time = time.perf_counter()
        scan_count = 0

        while jump_frequency < stop_frequency + 0.03 and not stop.is_set():
            power_reference = self.power.get()

            with self.lock:
                self.laser.clean_jump(jump_frequency)
                freq_thz = self.laser.read(Laser.REG_FreqTHz)
                freq_ghz = self.laser.read(Laser.REG_FreqGHz)
                frequency = freq_thz + freq_ghz / 10000
                self.frequency.set(frequency)

            with self.lock:
                self.laser.wait_nop()

            time_wait = time.perf_counter() + 1

            while self.power.get() < 0.8 * power_reference and time.perf_counter() < time_wait:
                time.sleep(.1)

            time.sleep(0.5)

            power_reference = self.power.get()

            self.clean_sweep_start(50, speed)

            time.sleep(.1)

            take_data.set()

            while self.offset.get() < 10 and not stop.is_set():
                time.sleep(.1)

            while self.offset.get() > -10 and not stop.is_set():
                time.sleep(.1)

            while self.offset.get() < -1 and not stop.is_set():
                time.sleep(0.1)

            take_data.clear()

            time.sleep(0.5)

            with self.lock:
                self.laser.clean_sweep_stop()

            with self.lock:
                self.laser.wait_nop()

            time_wait = time.perf_counter() + 5

            while self.power.get() < 0.95 * power_reference and time.perf_counter() < time_wait:
                time.sleep(.1)

            jump_frequency += 0.04
            progress = (jump_frequency - start_frequency) / (stop_frequency - start_frequency)
            self.clean_scan_progress.set((jump_frequency - start_frequency) / (stop_frequency - start_frequency))
            time_elapsed = time.perf_counter() - scan_start_time
            scan_count += 1
            average_time_elapsed = time_elapsed / scan_count
            self.scan_time_remaining.set(round(average_time_elapsed / progress / 60))

        time.sleep(1)
        # self.power_meter_thread.join()
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

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.mode_finder = GraphContext(self)
        self.mode_finder.title("Mode Finder")
        self.mode_finder.label("Frequency (THz)", "Optical Transmission")
        self.power = GraphContext(self)
        self.power.title("Output Power")
        self.power.label("Time (s)", "Output Power (dBm)")
        self.sweep = GraphContext(self)
        self.sweep.title("Transmission Monitor")
        self.sweep.label("Frequency (THz)", "Optical Transmission")

        self.mode_finder.grid(row=0, column=0, sticky="NSWE")
        self.power.grid(row=0, column=0, sticky="NSWE")
        self.sweep.grid(row=0, column=0, sticky="NSWE")

        self.power.switch_to()


class BlankContext(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.pack(fill="both", expand=True)


class GraphContext(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent, *args, **kwargs)
        self.parent = parent

        self.fig = plt.Figure(figsize=(5, 4), dpi=100)
        self.sub_plot = self.fig.add_subplot(111)
        self.line, = self.sub_plot.plot([], [], 'o', markersize=1)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
        self.ax = self.canvas.figure.axes[0]
        self.ax.set_xlim(0, 1)
        self.ax.set_ylim(0, 1)

    def switch_to(self):
        self.tkraise()

    def title(self, title):
        self.ax.set_title(title)

    def label(self, x_label, y_label):
        self.ax.set_xlabel(x_label)
        self.ax.set_ylabel(y_label)

    def plot(self, x, y, max_x_width=None):
        if isinstance(x, np.ndarray):
            if x.size > 1:
                self.line.set_data(x, y)
                ax = self.canvas.figure.axes[0]
                if max_x_width:
                    x_min = max(x.max() - max_x_width, x.min())
                else:
                    x_min = x.min()

                x_width = x.max() - x_min

                ax.set_xlim(x_min - x_width / 20, x.max() + x_width / 20)
                ax.set_ylim(0.8 * y.min(), max(1.2 * y.max(), 1E-7))
            else:
                self.line.set_data([], [])
                ax = self.canvas.figure.axes[0]
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)


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
            self.grid_columnconfigure(c + 1, weight=0, pad=20, minsize=200)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(4, weight=1)

        self.pad_left = ttk.Label(self, text=" ", style="GREY.TLabel")
        self.power = ttk.Label(self, text="Power: 0 dBm", style="GREY.TLabel", anchor="center")
        self.frequency = ttk.Label(self, text="Center Frequency:", style="GREY.TLabel", anchor="center")
        self.offset = ttk.Label(self, text="Frequency Offset: 0 GHz", style="GREY.TLabel", anchor="center")
        self.pad_right = ttk.Label(self, text=" ", style="GREY.TLabel", anchor="center")

        self.pad_left.grid(row=0, column=0, ipadx=5, ipady=5, padx=5, sticky=full_sticky)
        self.power.grid(row=0, column=1, ipadx=5, ipady=5, padx=5, sticky=full_sticky)
        self.frequency.grid(row=0, column=2, ipadx=5, ipady=5, padx=5, sticky=full_sticky)
        self.offset.grid(row=0, column=3, ipadx=5, ipady=5, padx=5, sticky=full_sticky)
        self.pad_right.grid(row=0, column=4, ipadx=5, ipady=5, padx=5, sticky=full_sticky)


class NavigationBar(tk.Frame):
    def __init__(self, parent, *args, **kwargs):
        tk.Frame.__init__(self, parent)
        self.parent = parent

        self.button_power = NavigationButton(self, "Power Monitor", None)
        self.button_sweep = NavigationButton(self, "Transmission Monitor", None)
        self.button_mode_finder = NavigationButton(self, "Comb Mode Finder", None)
        self.button_close = NavigationButton(self, "Close", None)

        self.button_power.pack(fill="both", expand=True)
        self.button_sweep.pack(fill="both", expand=True)
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
        self.button_off.enable()

        self.jump_entry = FrequencyEntryAndLabel(self, "Jump frequency (THz):", 195, 191.5, 196.25)
        self.jump_entry.grid(row=0, column=1, padx=5)
        self.button_jump = CommandButton(self, "Frequency Jump", None)
        self.button_jump.grid(row=1, column=1, sticky=full_sticky)
        self.button_jump.disable()

        self.sweep_entry = FrequencyEntryAndLabel(self, "Sweep range (GHz):", 50, 0, 50)
        self.sweep_entry.grid(row=0, column=2, padx=5)
        self.speed_entry = FrequencyEntryAndLabel(self, "Sweep speed (GHz/sec):", 20, 0.1, 50)
        self.speed_entry.grid(row=0, column=3, padx=5)
        self.button_sweep = CommandButton(self, "Frequency Sweep", None)
        self.button_sweep.grid(row=1, column=2, columnspan=2, sticky=full_sticky)
        self.button_sweep.disable()

        self.scan_start = FrequencyEntryAndLabel(self, "Scan start frequency (THz):", 192)
        self.scan_start.grid(row=0, column=4, padx=5)
        self.scan_stop = FrequencyEntryAndLabel(self, "Scan stop frequency (THz):", 196)
        self.scan_stop.grid(row=0, column=5, padx=5)
        self.scan_speed_entry = FrequencyEntryAndLabel(self, "Scan speed (GHz/sec):", 10, 1, 25)
        self.scan_speed_entry.grid(row=0, column=6, padx=5)
        self.button_scan = CommandButton(self, "Frequency Scan", None)
        self.button_scan.grid(row=1, column=4, columnspan=3, sticky=full_sticky)
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

        self.entry.delete(0, 'end')
        self.entry.insert(0, str(float(self.frequency.get())))

    def value(self):
        return self.entry.get()

    def validate(self, action, index, value_if_allowed,
                 prior_value, text, validation_type, trigger_type, widget_name):
        if text in '0123456789.-+':
            try:
                value_float = float(value_if_allowed)

                if self.min_freq <= value_float <= self.max_freq:
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
