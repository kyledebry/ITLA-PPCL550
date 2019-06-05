# -*- coding: utf-8 -*-
"""
Created on Wed May 22 15:40:53 2019

@author: Kyle DeBry
"""

from pure_photonics_utils import *
import laser as icm
import sys
import logging

laser = ITLA('COM2', 9600)

try:

    freq = 193

    laser_err = icm.laser_on(laser, freq, logging.DEBUG)

    print('Laser error: %d' % laser_err)
    icm.read_error(laser)

    time.sleep(1)

    if laser_err == ITLA.ITLA_NOERROR:

        sled_slope = icm.get_sled_slope(laser)
        sled_spacing = icm.get_sled_spacing(laser, 'CalibrationFiles\\CRTNHBM047_21_14_43_4.sled')
        map_vals = icm.read_mapfile('CalibrationFiles\\CRTNHBM047_1000_21_14_39_59.map')

        print('Mode %d' % laser.ITLACommunicate(ITLA.REG_Mode, 1, ITLA.WRITE))

        for i in range(4):
            freq_THz = 193 + (i % 4)
            freq_GHz = 100 * i
            print('%d THz' % laser.ITLACommunicate(ITLA.REG_CjumpTHz, freq_THz, ITLA.WRITE))
            print('%d * 0.1 GHz' % laser.ITLACommunicate(ITLA.REG_CjumpGHz, freq_GHz, ITLA.WRITE))
            icm.read_error(laser)


            freq = freq_THz + 0.0001 * freq_GHz

            icm.clean_jump(laser, freq, sled_spacing, sled_slope, map_vals)

            time.sleep(2)

        laser.ITLACommunicate(ITLA.REG_Cjumpon, 0, ITLA.WRITE)

        time.sleep(1)

        print('Off: %d' % laser.ITLACommunicate(ITLA.REG_ResetEnable, ITLA.SET_OFF, ITLA.WRITE))

finally:
    print(laser.ITLADisconnect())