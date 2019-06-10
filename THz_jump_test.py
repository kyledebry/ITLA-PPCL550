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

if laser_err == ITLA.NOERROR:

    for i in range(9):
        freq = 193 + i * 0.35
        laser.clean_jump(freq)
        time.sleep(1)

    time.sleep(1)
    laser.ITLACommunicate(ITLA.REG_Cjumpon, 0, ITLA.WRITE)

    laser.laser_off()

laser.ITLADisconnect()
