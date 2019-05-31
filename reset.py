# -*- coding: utf-8 -*-
"""
Created on Wed May 29 13:26:37 2019

@author: rm3531
"""

import itla_convenience_methods as icm
from pure_photonics_utils import *

laser = ITLA('COM2', 9600)
print(laser.sercon)
icm.laser_off(laser)
laser.ITLADisconnect()