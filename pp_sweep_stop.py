# -*- coding: utf-8 -*-
"""
Created on Tue May 28 13:35:28 2019

@author: Kyle DeBry
"""

from pure_photonics_utils import *
import itla_convenience_methods as icm
import logging
import math

laser = ITLA('COM2', 115200)

try:

    freq = 195

    laser_err = icm.laser_on(laser, freq, logging.DEBUG)

    print('Laser error: %d' % laser_err)
    icm.read_error(laser)

    time.sleep(1)

    if laser_err == ITLA.ITLA_NOERROR:

        icm.clean_sweep_prep(laser, 50, 20000)

        icm.laser_on(laser, freq, logging.debug)

        icm.clean_sweep_start(laser)

        offset_GHz = icm.clean_sweep_offset(laser)

        logging.info('Clean sweep offset: %d GHz' % offset_GHz)

        icm.clean_sweep_pause(laser, 20)

        wait_time = time.clock() + 5

        while offset_GHz > -150 and time.clock() < wait_time:
            offset_GHz = icm.clean_sweep_offset(laser)
            logging.info('Clean sweep offset: %d GHz' % offset_GHz)
            time.sleep(0.2)
            print(1)

        print('Done looping')
        logging.debug('Resuming laser...')

        icm.clean_sweep_start(laser)

        while time.clock() < wait_time + 6:
            offset_GHz = icm.clean_sweep_offset(laser)
            logging.info('Clean sweep offset: %d GHz' % offset_GHz)
            time.sleep(0.2)

        logging.info('Pausing laser')
        icm.clean_sweep_pause(laser)

        time.sleep(3)

        logging.info('Clean sweep off: %d' % laser.ITLACommunicate(0xE5, 0, ITLA.WRITE))
        icm.read_error(laser)
        icm.wait_nop(laser)
        time.sleep(1)
        logging.debug('Low noise mode: %d' % laser.ITLACommunicate(0x90, 0, ITLA.WRITE))
        icm.read_error(laser)

        time.sleep(5)

        icm.laser_off(laser)

    else:
        logging.warn('Another error occurred: %d' % test_response)


finally:
    icm.clean_sweep_stop(laser)

    time.sleep(1)

    icm.laser_off(laser)
    laser.ITLADisconnect()

    time.sleep(2)
