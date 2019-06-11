# -*- coding: utf-8 -*-
"""
Created on Wed May 29 13:26:37 2019

@author: rm3531
"""
import logging

from laser import Laser

laser = None

try:
    laser = Laser('COM2', 115200, log_level=logging.DEBUG)
    laser.laser_off()
finally:
    laser.itla_disconnect()
