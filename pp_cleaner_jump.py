# -*- coding: utf-8 -*-
"""
Created on Wed May 22 15:40:53 2019

@author: Kyle DeBry
"""

from pure_photonics_utils import *
from laser import Laser
import logging

laser = Laser('COM12', 9600, log_level=logging.DEBUG)

try:

    freq = 193

    laser_err = laser.laser_on(freq)

    print('Laser error: %d' % laser_err)
    laser.read_error()

    time.sleep(1)

    if laser_err == ITLA.NOERROR:

        print('Mode %d' % laser.itla_communicate(ITLA.REG_Mode, 1, ITLA.WRITE))

        for i in range(4):
            freq_THz = 193 + (i % 4)
            freq_GHz = 100 * i
            print('%d THz' % laser.itla_communicate(ITLA.REG_CjumpTHz, freq_THz, ITLA.WRITE))
            print('%d * 0.1 GHz' % laser.itla_communicate(ITLA.REG_CjumpGHz, freq_GHz, ITLA.WRITE))
            laser.read_error()

            freq = freq_THz + 0.0001 * freq_GHz

            laser.clean_jump(freq)

            time.sleep(2)

        laser.itla_communicate(ITLA.REG_Cjumpon, 0, ITLA.WRITE)

        time.sleep(1)

        print('Off: %d' % laser.itla_communicate(ITLA.REG_ResetEnable, ITLA.SET_OFF, ITLA.WRITE))

finally:
    print(laser.itla_disconnect())
