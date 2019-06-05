# -*- coding: utf-8 -*-
"""
Created on Fri May 24 17:42:08 2019

@author: Kyle DeBry
"""

from pure_photonics_utils import ITLA
from laser import Laser
import time

laser = Laser('COM2', 115200)

freq = 193

laser_err = laser.laser_on(freq)

print(laser_err)

if laser_err == ITLA.NOERROR:

    sled_slope = laser.get_sled_slope()
    sled_spacing = laser.get_sled_spacing('CalibrationFiles\\CRTNHBM047_21_14_43_4.sled')
    map_vals = Laser.read_mapfile('CalibrationFiles\\CRTNHBM047_1000_21_14_39_59.map')

    for i in range(9):
        freq = 193 + i * 0.35
        laser.clean_jump(freq)
        time.sleep(1)

    time.sleep(1)
    laser.ITLACommunicate(ITLA.REG_Cjumpon, 0, ITLA.WRITE)

    laser.laser_off()

laser.ITLADisconnect()
