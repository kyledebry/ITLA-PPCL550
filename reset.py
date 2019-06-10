# -*- coding: utf-8 -*-
"""
Created on Wed May 29 13:26:37 2019

@author: rm3531
"""

from laser import Laser

laser = Laser('COM2', 9600)
print(laser.sercon)
laser.laser_off()
laser.itla_disconnect()
