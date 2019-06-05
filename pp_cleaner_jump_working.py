# -*- coding: utf-8 -*-
"""
Created on Wed May 22 15:40:53 2019

@author: Kyle DeBry
"""

from pure_photonics_utils import *
import laser as icm
import sys

laser = ITLA('COM2', 9600)

icm.laser_off(laser)

try:

    print(laser)
    print(laser.sercon)

    test_response = laser.ITLACommunicate(ITLA.REG_Nop, 0, ITLA.READ)
    print(test_response)

    if test_response == ITLA.ITLA_ERROR_SERBAUD:
        print('Baud rate error')
    elif test_response == ITLA.ITLA_ERROR_SERPORT:
        print('Port connection error')
    else:
        print('Connection successful! :)')

        sled_slope = icm.get_sled_slope(laser)
        print('Found sled slope: %f' % sled_slope)

        sled_spacing = icm.get_sled_spacing(laser, 'CalibrationFiles\\CRTNHBM047_21_14_43_4.sled')

        print('Sled spacing %f' % float(sled_spacing))

        map_vals = icm.read_mapfile('CalibrationFiles\\CRTNHBM047_1000_21_14_39_59.map')

        freq_THz = 193
        freq_GHz = 0

        print('%d THz' % laser.ITLACommunicate(ITLA.REG_FreqTHz, freq_THz, ITLA.WRITE))
        print('%d * 0.1 GHz' % laser.ITLACommunicate(ITLA.REG_FreqGHz, freq_GHz, ITLA.WRITE))
        print('Enable: %d' % laser.ITLACommunicate(ITLA.REG_ResetEnable, ITLA.SET_ON, ITLA.WRITE))

        time.sleep(1)

        status = laser.ITLACommunicate(ITLA.REG_Nop, 0, ITLA.READ)
        print('Status: %d' % status)

        while(status > 16 or status == 0):
            print('Status: %d' % status)
            status = laser.ITLACommunicate(ITLA.REG_Nop, 0, ITLA.READ) > 16

        optical_power = laser.ITLACommunicate(ITLA.REG_Oop, 0, ITLA.READ) * 0.01
        print('Optical power: %f' % optical_power)

        while optical_power < 10:
            time.sleep(0.2)
            optical_power = laser.ITLACommunicate(ITLA.REG_Oop, 0, ITLA.READ) * 0.01
            print('Optical power: %f' % optical_power)


        print('Status: %d' % status)


        icm.laser_on(laser, 193)
        print('Last error: %d' % laser.ITLALastError())


        print('Mode %d' % laser.ITLACommunicate(ITLA.REG_Mode, 1, ITLA.WRITE))
        print('Last error: %d' % laser.ITLALastError())

        time.sleep(2)


        for i in range(4):
            freq_THz = 193 + (i % 4)
            freq_GHz = 100 * i
            print('%d THz' % laser.ITLACommunicate(ITLA.REG_CjumpTHz, freq_THz, ITLA.WRITE))
            print('%d * 0.1 GHz' % laser.ITLACommunicate(ITLA.REG_CjumpGHz, freq_GHz, ITLA.WRITE))
            print('Last error: %d' % laser.ITLALastError())


            freq = freq_THz + 0.0001 * freq_GHz

            sled_temp = icm.get_sled_temperature(sled_spacing, sled_slope, map_vals, freq)
            sled_temp_reg = round(sled_temp * 100)
            current = icm.get_current(map_vals, freq)
            current_reg = round(current * 10)

            print('Moving sled to %d' % laser.ITLACommunicate(ITLA.REG_CjumpSled, sled_temp_reg, ITLA.WRITE))
            print('Moving current to %d' % laser.ITLACommunicate(ITLA.REG_CjumpCurrent, current_reg, ITLA.WRITE))

            print('CJump: %d' % laser.ITLACommunicate(ITLA.REG_Cjumpon, 1, ITLA.WRITE))
            print('CJump: %d' % laser.ITLACommunicate(ITLA.REG_Cjumpon, 1, ITLA.WRITE))
            print('CJump: %d' % laser.ITLACommunicate(ITLA.REG_Cjumpon, 1, ITLA.WRITE))
            print('CJump: %d' % laser.ITLACommunicate(ITLA.REG_Cjumpon, 1, ITLA.WRITE))

            error_read = laser.ITLACommunicate(ITLA.REG_Cjumpoffset, 0, ITLA.READ)

            freq_error = (error_read)/10.0
            print('Frequency error: %f GHz' % freq_error)

            # Read out the laser's claimed frequency
            claim_THz = laser.ITLACommunicate(ITLA.REG_GetFreqTHz, 0, ITLA.READ)
            claim_GHz = laser.ITLACommunicate(ITLA.REG_GETFreqGHz, 0, ITLA.READ) / 10

            print('Claim THz: %d' % claim_THz)
            print('Claim GHz %f' % claim_GHz)


            wait_time = time.clock() + 2

            while abs(freq_error) > 0 and time.clock() < wait_time:
                time.sleep(.1)
                error_read = laser.ITLACommunicate(ITLA.REG_Cjumpoffset, 0, ITLA.READ)
                freq_error = (error_read)/10.0
                print('Frequency error: %f GHz' % freq_error)

            print('Last error: %d' % laser.ITLALastError())

            time.sleep(2)

        laser.ITLACommunicate(ITLA.REG_Cjumpon, 0, ITLA.WRITE)

        time.sleep(1)

        print('Off: %d' % laser.ITLACommunicate(ITLA.REG_ResetEnable, ITLA.SET_OFF, ITLA.WRITE))

finally:
    print(laser.ITLADisconnect())

"""
except:
    e = sys.exc_info()[0]
    print(e)

finally:
    print(laser.ITLADisconnect())
"""