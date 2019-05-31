# -*- coding: utf-8 -*-
"""
Created on Fri May 24 17:42:08 2019

@author: Kyle DeBry
"""

from pure_photonics_utils import *
import itla_convenience_methods as icm

laser = ITLA('COM2', 9600)

try:

    freq = 193

    laser_err = icm.laser_on(laser, freq)

    print(laser_err)

    if laser_err == ITLA.ITLA_NOERROR:

        sled_slope = icm.get_sled_slope(laser)
        sled_spacing = icm.get_sled_spacing(laser, 'CalibrationFiles\\CRTNHBM047_21_14_43_4.sled')
        map_vals = icm.read_mapfile('CalibrationFiles\\CRTNHBM047_1000_21_14_39_59.map')

        for i in range(9):
            freq = 193 + i * 0.35
            icm.clean_jump(laser, freq, sled_spacing, sled_slope, map_vals)
            time.sleep(1)

        time.sleep(1)
        laser.ITLACommunicate(ITLA.REG_Cjumpon, 0, ITLA.WRITE)

        icm.laser_off(laser)

except:
    e = sys.exc_info()[0]
    print(e)

finally:
    laser.ITLADisconnect()
    curses.nocbreak()
    screen.keypad(0)
    curses.echo()
    curses.endwin()
