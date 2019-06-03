# -*- coding: utf-8 -*-
"""
Created on Wed May 22 15:40:53 2019

@author: Kyle DeBry
"""

from pure_photonics_utils import *
from laser import Laser

laser = Laser('COM2', 9600)

laser.laser_off()

try:

    print(laser)
    print(laser.sercon)

    test_response = laser.itla_communicate(ITLA.REG_Nop, 0, ITLA.READ)
    print(test_response)

    if test_response == ITLA.ERROR_SERBAUD:
        print('Baud rate error')
    elif test_response == ITLA.ERROR_SERPORT:
        print('Port connection error')
    else:
        print('Connection successful! :)')

        sled_slope = laser.get_sled_slope()
        print('Found sled slope: %f' % sled_slope)

        sled_spacing = Laser.get_sled_spacing(laser, 'CalibrationFiles\\CRTNHBM047_21_14_43_4.sled')

        print('Sled spacing %f' % float(sled_spacing))

        map_vals = Laser.read_mapfile('CalibrationFiles\\CRTNHBM047_1000_21_14_39_59.map')

        freq_THz = 193
        freq_GHz = 0

        print('%d THz' % laser.itla_communicate(ITLA.REG_FreqTHz, freq_THz, ITLA.WRITE))
        print('%d * 0.1 GHz' % laser.itla_communicate(ITLA.REG_FreqGHz, freq_GHz, ITLA.WRITE))
        print('Enable: %d' % laser.itla_communicate(ITLA.REG_ResetEnable, ITLA.SET_ON, ITLA.WRITE))

        time.sleep(1)

        status = laser.itla_communicate(ITLA.REG_Nop, 0, ITLA.READ)
        print('Status: %d' % status)

        while status > 16 or status == 0:
            print('Status: %d' % status)
            status = laser.itla_communicate(ITLA.REG_Nop, 0, ITLA.READ) > 16

        optical_power = laser.itla_communicate(ITLA.REG_Oop, 0, ITLA.READ) * 0.01
        print('Optical power: %f' % optical_power)

        while optical_power < 10:
            time.sleep(0.2)
            optical_power = laser.itla_communicate(ITLA.REG_Oop, 0, ITLA.READ) * 0.01
            print('Optical power: %f' % optical_power)

        print('Status: %d' % status)

        laser.laser_on(193)
        print('Last error: %d' % laser.itla_last_error())

        print('Mode %d' % laser.itla_communicate(ITLA.REG_Mode, 1, ITLA.WRITE))
        print('Last error: %d' % laser.itla_last_error())

        time.sleep(2)

        for i in range(4):
            freq_THz = 193 + (i % 4)
            freq_GHz = 100 * i
            print('%d THz' % laser.itla_communicate(ITLA.REG_CjumpTHz, freq_THz, ITLA.WRITE))
            print('%d * 0.1 GHz' % laser.itla_communicate(ITLA.REG_CjumpGHz, freq_GHz, ITLA.WRITE))
            print('Last error: %d' % laser.itla_last_error())

            freq = freq_THz + 0.0001 * freq_GHz

            sled_temp = Laser.get_sled_temperature(sled_spacing, sled_slope, map_vals, freq)
            sled_temp_reg = round(sled_temp * 100)
            current = Laser.get_current(map_vals, freq)
            current_reg = round(current * 10)

            print('Moving sled to %d' % laser.itla_communicate(ITLA.REG_CjumpSled, sled_temp_reg, ITLA.WRITE))
            print('Moving current to %d' % laser.itla_communicate(ITLA.REG_CjumpCurrent, current_reg, ITLA.WRITE))

            print('CJump: %d' % laser.itla_communicate(ITLA.REG_Cjumpon, 1, ITLA.WRITE))
            print('CJump: %d' % laser.itla_communicate(ITLA.REG_Cjumpon, 1, ITLA.WRITE))
            print('CJump: %d' % laser.itla_communicate(ITLA.REG_Cjumpon, 1, ITLA.WRITE))
            print('CJump: %d' % laser.itla_communicate(ITLA.REG_Cjumpon, 1, ITLA.WRITE))

            error_read = laser.itla_communicate(ITLA.REG_Cjumpoffset, 0, ITLA.READ)

            freq_error = error_read / 10.0
            print('Frequency error: %f GHz' % freq_error)

            # Read out the laser's claimed frequency
            claim_THz = laser.itla_communicate(ITLA.REG_GetFreqTHz, 0, ITLA.READ)
            claim_GHz = laser.itla_communicate(ITLA.REG_GETFreqGHz, 0, ITLA.READ) / 10

            print('Claim THz: %d' % claim_THz)
            print('Claim GHz %f' % claim_GHz)

            wait_time = time.clock() + 2

            while abs(freq_error) > 0 and time.clock() < wait_time:
                time.sleep(.1)
                error_read = laser.itla_communicate(ITLA.REG_Cjumpoffset, 0, ITLA.READ)
                freq_error = error_read / 10.0
                print('Frequency error: %f GHz' % freq_error)

            print('Last error: %d' % laser.itla_last_error())

            time.sleep(2)

        laser.itla_communicate(ITLA.REG_Cjumpon, 0, ITLA.WRITE)

        time.sleep(1)

        print('Off: %d' % laser.itla_communicate(ITLA.REG_ResetEnable, ITLA.SET_OFF, ITLA.WRITE))

finally:
    print(laser.itla_disconnect())

"""
except:
    e = sys.exc_info()[0]
    print(e)

finally:
    print(laser.ITLADisconnect())
"""
