# -*- coding: utf-8 -*-
"""
Created on Tue May 28 13:35:28 2019

@author: Kyle DeBry
"""

from laser import Laser
import logging
import time

laser = Laser('COM2', 115200, logging.DEBUG)

try:

    freq = 195

    laser_err = laser.laser_on(freq, logging.DEBUG)

    print('Laser error: %d' % laser_err)
    laser.read_error()

    time.sleep(1)

    if laser_err == Laser.NOERROR:

        laser.clean_sweep_prep(50, 20000)

        laser.laser_on(freq, logging.INFO)

        laser.clean_sweep_start()

        offset_GHz = laser.clean_sweep_offset()

        logging.info('Clean sweep offset: %d GHz' % offset_GHz)

        laser.clean_sweep_pause(20)

        wait_time = time.perf_counter() + 5

        while offset_GHz > -150 and time.perf_counter() < wait_time:
            offset_GHz = laser.clean_sweep_offset()
            logging.info('Clean sweep offset: %d GHz' % offset_GHz)
            time.sleep(0.2)

        print('Done looping')
        logging.debug('Resuming laser...')

        laser.clean_sweep_start()

        while time.perf_counter() < wait_time + 5:
            offset_GHz = laser.clean_sweep_offset()
            logging.info('Clean sweep offset: %d GHz' % offset_GHz)
            time.sleep(0.2)

        logging.info('Pausing laser')
        laser.clean_sweep_pause()

        time.sleep(3)

        logging.info('Clean sweep off: %d' % laser.itla_communicate(0xE5, 0, Laser.WRITE))
        time.sleep(3)
        laser.read_error()
        laser.wait_nop()
        time.sleep(1)
        logging.debug('Low noise mode: %d' % laser.itla_communicate(0x90, 0, Laser.WRITE))
        laser.read_error()

        time.sleep(5)

        laser.laser_off()

    else:
        logging.warning('Another error occurred: %d' % laser_err)


finally:
    laser.clean_sweep_stop()

    time.sleep(1)

    laser.laser_off()
    laser.itla_disconnect()

    time.sleep(2)