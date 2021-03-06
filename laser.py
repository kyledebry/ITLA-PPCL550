# -*- coding: utf-8 -*-
"""
Created on Thu May 23 09:23:55 2019

@author: Kyle DeBry
"""

from pure_photonics_utils import ITLA
import numpy as np
import math
import time
import logging


class Laser(ITLA):
    """
    Additional methods for the ITLA class to make standard commands easier.
    """
    SLED_CENTER_TEMP = 30  # Want sled temperatures to be close to 30 C
    SLED_FILE_NAME = 'CalibrationFiles\\CRTNHBM047_21_14_43_4.sled'
    MAP_FILE_NAME = 'CalibrationFiles\\CRTNHBM047_1000_21_14_39_59.map'
    DEFAULT_PORT = 'COM12'
    DEFAULT_BAUD = 115200

    def __init__(self, port=None, baud=None, log_level=logging.WARNING):
        if not port:
            port = Laser.DEFAULT_PORT
        if not baud:
            baud = Laser.DEFAULT_BAUD

        logging.basicConfig(format='%(levelname)s: %(message)s', level=log_level)

        ITLA.__init__(self, port, baud)

        print(self.sercon)

        self.jump_values = None
        self.set_jump_vals()

    def read_error(self):
        """Get information about any errors raised by the laser"""

        laser_error = self.ITLALastError()
        if laser_error == Laser.EXERROR:
            nop_error = self.itla_communicate(Laser.REG_Nop, 0, Laser.READ)
            logging.error('Execution error (1). NOP reads %d' % nop_error)
        elif laser_error == Laser.CPERROR:
            nop_error = self.itla_communicate(Laser.REG_Nop, 0, Laser.READ)
            logging.error('Command pending error (1). NOP reads %d' % nop_error)

    def check_nop(self):
        """Reads the NOP register to get the laser's status"""
        status = self.itla_communicate(Laser.REG_Nop, 0, Laser.READ)
        logging.debug('Status: %d' % status)
        return status

    def check_power(self):
        """Returns the current optical power"""
        optical_power = self.itla_signed_communicate(Laser.REG_Oop, 0, Laser.READ) * 0.01

        if optical_power < 0:
            optical_power = 0

        return optical_power

    def wait_nop(self):
        """Wait until the NOP register reads an acceptable value"""
        assert isinstance(self, Laser)

        # Wait for the laser's status to be OK
        status = self.check_nop()
        while status > 16 or status == 0:
            status = self.check_nop()
            time.sleep(0.25)
        logging.info('NOP status: %d' % status)
        self.read_error()

    def startup_begin(self, freq):
        """Begins the process of turning on the laser by setting a frequency and powering on"""

        # Make sure the laser is responding to commands
        test_response = self.itla_communicate(Laser.REG_Nop, 0, Laser.READ)
        self.read_error()

        # Check for two common errors
        if test_response == Laser.ERROR_SERBAUD:
            logging.warning('Baud rate error')
            return test_response
        elif test_response == Laser.ERROR_SERPORT:
            logging.warning('Port connection error')
            return test_response
        elif test_response - 0x10 == Laser.NOERROR or test_response == Laser.NOERROR:
            test_response = Laser.NOERROR
            print('Connection successful! :)')

            # Split frequency into THz and GHz parts
            freq_thz = math.trunc(freq)
            freq_ghz = round((freq - freq_thz) * 10000)

            # Set the laser's frequency in THz
            logging.info('%d THz' % self.itla_communicate(Laser.REG_FreqTHz, freq_thz, Laser.WRITE))
            # Set the GHz part of the laser's frequency
            logging.info('%d * 0.1 GHz' % self.itla_communicate(Laser.REG_FreqGHz, freq_ghz, Laser.WRITE))
            # Set laser to channel 1 to make sure it comes on at currect frequency
            logging.debug('Channel: %d' % self.itla_communicate(Laser.REG_Channel, 1, Laser.WRITE))
            time.sleep(1)
            # Turn on the laser
            enable_status = self.itla_communicate(Laser.REG_ResetEnable, Laser.SET_ON, Laser.WRITE)
            logging.info('Enable: %d' % enable_status)
            if enable_status != 1:
                logging.debug('Laser response to enable: %d' % self.ITLALastError())

            return 0

    def startup_finish(self):
        """Finishes startup sequence by turning on clean mode"""
        logging.info('Clean mode on: %d' % self.send(Laser.REG_Mode, 1))

    def laser_on(self, freq):
        """Turns on the laser to the desired frequency, and returns the error code or 0"""
        assert isinstance(self, Laser)

        startup_response = self.startup_begin(freq)

        if startup_response == 0:

            self.wait_nop()

            # Wait for the laser to be outputting the correct power (10 dBm in this case) or 5 seconds
            wait_time = time.clock() + 5
            optical_power = self.check_power()
            logging.info('Optical power: %5.2f' % optical_power)

            while abs(optical_power - 10) > 1 and time.clock() < wait_time:
                time.sleep(0.2)
                optical_power = self.check_power()
                logging.info('Optical power: %5.2f' % optical_power)
            self.read_error()
            time.sleep(1)

            self.startup_finish()

        else:
            logging.warning('Another error occurred: %d' % startup_response)
            self.read_error()

        # Return error code
        return startup_response

    def laser_off(self):
        """Turns off the laser"""
        assert isinstance(self, Laser)

        print('Clean mode off: %d' % self.send(Laser.REG_Mode, 0))

        # Turn off the laser
        logging.info('Laser off: %d' % self.itla_communicate(Laser.REG_ResetEnable, Laser.SET_OFF, Laser.WRITE))

    def send(self, register, data, signed_response=False):
        """Sends a two-byte max integer to the device and returns the response
        """

        if data is True:
            data = 1
        elif data is False:
            data = 0

        if signed_response:
            response = self.itla_signed_communicate(register, data, ITLA.WRITE)
        else:
            response = self.itla_communicate(register, data, ITLA.WRITE)

        return response

    def read(self, register: int, signed_response=False) -> int:
        """Reads the value in the designated register"""

        if signed_response:
            response = self.itla_signed_communicate(register, 0, ITLA.READ)
        else:
            response = self.itla_communicate(register, 0, ITLA.READ)

        return response

    def get_sled_slope(self):
        """Returns the slope of the sled temperature from the laser in degrees C per GHz"""
        assert isinstance(self, Laser)

        # Value from laser is in units of 0.0001 C / GHz
        # Value should be negative
        sled_slope = 0.0001 * self.itla_communicate(Laser.REG_SledSlope, 0, Laser.READ)

        return sled_slope

    def get_sled_spacing(self, sledfile_name: str):
        """Calculates the spacing between acceptable sled modes in degrees C"""
        assert isinstance(self, Laser)
        assert isinstance(sledfile_name, str)

        temps = []  # List of sled temperatures from the logfile
        clusters = []  # Corresponding list of which cluster the temp belongs to

        # Read .sled calibration file sled temperatures
        with open(sledfile_name) as logfile:
            lines = logfile.readlines()

            for line in lines:
                temps.append(float(line.split(' ')[5]) * 0.01)

        # If two temps are 1 C apart or less, consider them part of the same cluster
        cluster_num = 0
        for i in range(len(temps)):  # Not Pythonic, I know

            if i > 0:
                if abs(temps[i] - temps[i - 1]) > 1:
                    cluster_num = cluster_num + 1

            clusters.append(cluster_num)

        avg_temps = []

        # Average the temperatures of each cluster
        for c in range(clusters[-1] + 1):
            cluster = []
            for j in range(len(temps)):
                if clusters[j] == c:
                    cluster.append(temps[j])
            avg_temps.append(np.mean(cluster))

        sum_diffs = 0

        # Find the average difference between cluster temperatures
        for i in range(len(avg_temps)):
            if i > 0:
                sum_diffs = sum_diffs + abs(avg_temps[i] - avg_temps[i - 1])

        sled_spacing = sum_diffs / (len(avg_temps) - 1)

        return sled_spacing

    @staticmethod
    def read_mapfile(mapfile_name):
        """Read the map calibration file and return lists of each value.

        Returns a list of lists. The order is: [freq[], sled[], f2temp[], f2temp[],
                                                f1power[], f2power[], current[]]
        Each list has the same number of points, and the ith value in each list
        corresponds to the ith frequency in the freq[] list.
        """
        assert isinstance(mapfile_name, str)

        # Open file
        with open(mapfile_name) as mapfile:
            lines = mapfile.readlines()

            freq = []
            sled = []
            f1temp = []
            f2temp = []
            f1power = []
            f2power = []
            current = []

            # Loop through each line
            for line in lines:
                line = line.split(' ')
                if len(line) > 17:
                    # Break lines into desired values, convert to floats
                    freq_point = float(line[2])
                    sled_point = float(line[5])
                    f1temp_point = float(line[8])
                    f2temp_point = float(line[11])
                    f1power_point = float(line[14])
                    f2power_point = float(line[17])
                    current_point = float(line[20]) * 0.1  # To milliamps

                    # Add these points to the arrays of each value
                    freq.append(freq_point)
                    sled.append(sled_point)
                    f1temp.append(f1temp_point)
                    f2temp.append(f2temp_point)
                    f1power.append(f1power_point)
                    f2power.append(f2power_point)
                    current.append(current_point)

        return [freq, sled, f1temp, f2temp, f1power, f2power, current]

    def set_jump_vals(self, sled_file_name=SLED_FILE_NAME, map_file_name=MAP_FILE_NAME):
        sled_slope = self.get_sled_slope()
        sled_spacing = self.get_sled_spacing(sled_file_name)
        map_vals = Laser.read_mapfile(map_file_name)

        self.jump_values = [sled_slope, sled_spacing, map_vals]

    @staticmethod
    def get_sled_temperature(sled_spacing, sled_slope, map_vals, freq):
        """Calculates the sled temperature for a jump based on .sled and .map file values and the desired frequency."""

        # Get frequency and sled temp map values
        freq_arr = map_vals[0]
        sled_arr = map_vals[1]

        # Find the two closest frequencies in freq_arr (frequency gridpoints)
        i_upper = 0
        while freq_arr[i_upper] < freq:
            i_upper = i_upper + 1

        i_lower = i_upper - 1

        # Pick the closer of the two frequency gridpoints
        upper_dist = abs(freq - freq_arr[i_upper])
        lower_dist = abs(freq - freq_arr[i_lower])

        gridpoint = i_lower

        if upper_dist < lower_dist:
            gridpoint = i_upper

        temp_gridpoint = sled_arr[gridpoint]
        freq_gridpoint = freq_arr[gridpoint]

        # Calculate the difference between the desired frequency, and the closest gridpoint, in GHz
        freq_diff = (freq - freq_gridpoint) * 1000
        logging.debug(
            'freq: {0} THz, freq_grid: {1} THz, freq_diff: {2} GHz, temp_grid: {3} C'.format(freq, freq_gridpoint,
                                                                                             freq_diff, temp_gridpoint))

        # Using the sled's temperature-frequency slope, calculate the temp difference from the closest gridpoint
        temp_diff = sled_slope * freq_diff
        logging.debug('temp diff: {0} C'.format(temp_diff))

        # Gridpoint + temperature difference will arrive at the correct frequency
        sled_base_temp = temp_gridpoint + temp_diff
        logging.debug('base temp: %f' % sled_base_temp)

        # We want the sled's temperature to be close to 30 C to make jumping faster
        # Changing the sled's temp by sled_spacing will not change the frequency
        # So we calculate the number of sled_spacing's to get the sled closest to 30 C
        # and still have the desired frequency
        sled_center_diff = Laser.SLED_CENTER_TEMP - sled_base_temp
        logging.debug('center diff: %f' % sled_center_diff)

        sled_mode_adjust = round(sled_center_diff / sled_spacing)
        logging.debug('sled mode adjust %d' % sled_mode_adjust)

        # Add the sled_spacing's to the temp calculated above to get the final temp
        sled_set_temp = sled_base_temp + sled_mode_adjust * sled_spacing

        return sled_set_temp

    @staticmethod
    def get_current(map_vals, freq):
        """Calculates the current in mA for the given frequency using the .map file values"""

        # Get the frequency and current map values
        freq_arr = map_vals[0]
        current_arr = map_vals[6]

        # Find the two closest frequencies in freq_arr (frequency gridpoints)
        i_upper = 0
        while freq_arr[i_upper] < freq:
            i_upper = i_upper + 1

        i_lower = i_upper - 1

        freq_upper = freq_arr[i_upper]
        freq_lower = freq_arr[i_lower]

        # The "grid spacing" of the map file is the frequency distance between points
        freq_grid_diff = freq_upper - freq_lower

        current_upper = current_arr[i_upper]
        current_lower = current_arr[i_lower]

        # Linear interpolation between the two currents
        upper_frac = abs((freq - freq_upper) / freq_grid_diff)
        lower_frac = 1 - upper_frac

        current_interpolation = upper_frac * current_upper + lower_frac * current_lower

        return current_interpolation

    def clean_jump_start(self, freq):
        """Starts clean jump. User must wait for stable frequency."""
        if freq > 196.25 or freq < 191.5:
            return

        sled_slope = self.jump_values[0]
        sled_spacing = self.jump_values[1]
        map_vals = self.jump_values[2]

        # Split the frequency into THz and GHz parts
        freq_thz = math.trunc(freq)
        freq_ghz = round((freq - freq_thz) * 10000)

        # Turn on clean mode
        logging.debug('Clean mode: %d' % self.itla_communicate(Laser.REG_Mode, 1, Laser.WRITE))

        # Set the next frequency in THz (register is specific for clean jump)
        logging.debug(self.itla_communicate(Laser.REG_CjumpTHz, freq_thz, Laser.WRITE))

        # Set the GHz part of the next frequency (register is specific for clean jump)
        logging.debug(self.itla_communicate(Laser.REG_CjumpGHz, freq_ghz, Laser.WRITE))

        # Calculate the sled temperature in units of 0.01 C and round to nearest int
        sled_temp = Laser.get_sled_temperature(sled_spacing, sled_slope, map_vals, freq)
        sled_temp_reg = round(sled_temp * 100)

        # Calculate current in units of 0.1 mA and round to nearest int
        current = Laser.get_current(map_vals, freq)
        current_reg = round(current * 10)

        # Write the current and sled temp to appropriate clean jump registers
        logging.debug(self.itla_communicate(Laser.REG_CjumpSled, sled_temp_reg, Laser.WRITE))
        logging.debug(self.itla_communicate(Laser.REG_CjumpCurrent, current_reg, Laser.WRITE))

        time.sleep(0.5)

        logging.info('Moving to frequency %f' % freq)

        # Tell laser to move frequency, temperature, and current to memory
        logging.debug('Jump: memory (%d)' % self.itla_communicate(Laser.REG_Cjumpon, 1, Laser.WRITE))
        # Tell laser to calculate filter 1 temperature
        logging.debug('Jump: filter 1 (%d)' % self.itla_communicate(Laser.REG_Cjumpon, 1, Laser.WRITE))
        # Tell laser to calculate filter 2 temperature
        logging.debug('Jump: filter 2 (%d)' % self.itla_communicate(Laser.REG_Cjumpon, 1, Laser.WRITE))
        # Execute the jump
        logging.debug('Jump! (%d)' % self.itla_communicate(Laser.REG_Cjumpon, 1, Laser.WRITE))

    def clean_jump_finish(self):
        """Turns off clean jump mode."""
        self.itla_communicate(ITLA.REG_Cjumpon, 0, ITLA.WRITE)

    def clean_jump(self, freq):
        """Performs a clean jump to the given frequency based on the calibration data provided."""

        self.clean_jump_start(freq)

        # Read the frequency error and wait until it is below a threshold or 2 seconds passes
        wait_time = time.clock() + 2

        error_read = self.itla_signed_communicate(Laser.REG_Cjumpoffset, 0, Laser.READ)
        freq_error = error_read / 10.0
        logging.debug('Frequency error: %5.1f GHz' % freq_error)

        while abs(freq_error) > 0.1 and time.clock() < wait_time:
            time.sleep(.1)
            error_read = self.itla_signed_communicate(Laser.REG_Cjumpoffset, 0, Laser.READ)
            freq_error = error_read / 10.0
            logging.debug('Frequency error: %5.1f GHz' % freq_error)
        logging.info('Frequency error: %5.1f GHz' % freq_error)

        self.wait_nop()

        # Read out the laser's claimed frequency
        claim_thz = self.itla_communicate(Laser.REG_GetFreqTHz, 0, Laser.READ)
        claim_ghz = self.itla_signed_communicate(Laser.REG_GETFreqGHz, 0, Laser.READ) / 10

        logging.debug('Claim THz: %d' % claim_thz)
        logging.debug('Claim GHz %f' % claim_ghz)

        claim_freq = claim_thz + claim_ghz / 1000.0

        print(('Laser\'s claimed frequency: %f' % claim_freq))

        self.clean_jump_finish()

    def clean_sweep_prep(self, sweep_ghz, sweep_speed):
        """Sets up clean sweep for the laser at the given range and speed"""
        assert isinstance(self, Laser)

        # Set scan range (in GHz)
        logging.debug('Sweep amp: %d GHz' % self.itla_communicate(Laser.REG_Csweepamp, sweep_ghz, Laser.WRITE))

        # Set scan speed (in MHz/sec)
        logging.debug('Sweep speed: %d MHz/s' % self.itla_communicate(Laser.REG_Csweepspeed, sweep_speed, Laser.WRITE))

    def clean_sweep_start(self):
        """Begins clean sweep with previously set parameters"""
        assert isinstance(self, Laser)

        # Turn on clean mode
        logging.debug('Clean mode: %d' % self.itla_communicate(Laser.REG_Mode, 1, Laser.WRITE))

        # Wait 0.5 seconds (recommendation)
        time.sleep(0.5)

        # Turn on clean sweep
        logging.info('Clean sweep on: %d' % self.itla_communicate(Laser.REG_Csweepon, 1, Laser.WRITE))

    def offset(self):
        assert isinstance(self, Laser)

        offset_ghz = self.read(Laser.REG_Csweepoffset, signed_response=True) / 10.0

        return offset_ghz

    def clean_sweep_pause(self, offset=None):
        assert isinstance(self, Laser)

        if offset is None:
            offset_1 = self.offset()

            print(('Current offset: %f GHz' % offset_1))

            offset_2 = self.offset()

            while offset_2 == offset_1:
                offset_2 = self.offset()
                print(('Offset 2: %f' % offset_2))
            moving_positive = offset_2 > offset_1

            offset_stop = offset_2 + 2 * (offset_2 - offset_1)

            if offset_stop < -25:
                offset_stop = -24
            elif offset_stop > 25:
                offset_stop = 24

            if moving_positive:
                offset_stop_int = math.ceil(offset_stop)
            else:
                offset_stop_int = math.floor(offset_stop)

            offset = offset_stop_int
        else:
            offset = round(offset)

        print(('Attempting to stop at %d GHz' % offset))

        if offset < 0:
            offset = 2 ** 16 + offset

        stop = self.itla_signed_communicate(Laser.REG_Csweepstop, offset, Laser.WRITE)
        print(('Stopping at %d GHz' % stop))

    def clean_sweep_to_offset(self, offset):
        self.clean_sweep_start()
        self.clean_sweep_pause(offset)

    def clean_sweep_stop(self):
        """Stops execution of clean sweep and exits low-noise mode"""
        assert isinstance(self, Laser)

        logging.info('Clean sweep stop: %d' % self.itla_communicate(Laser.REG_Csweepon, 0, Laser.WRITE))

        self.wait_nop()
