# -*- coding: utf-8 -*-
"""
Created on Tue May 28 13:35:28 2019

@author: Kyle DeBry
"""

from laser import Laser
import logging
import time

laser = Laser()

freq = 195

laser_err = laser.laser_on(freq)
print('Laser error: %d' % laser_err)
laser.read_error()

time.sleep(1)

if laser_err == Laser.NOERROR:

    laser.clean_sweep_prep(5, 5000)

    laser.clean_sweep_start()

    laser.clean_sweep_pause(-5)

    offset_GHz = laser.offset()

    wait_time = time.perf_counter() + 10

    while time.perf_counter() < wait_time:
        offset_GHz = laser.offset()
        print('Clean sweep offset: %d GHz' % offset_GHz)
        print("NOP: %d" % laser.check_nop())
        time.sleep(0.2)

    laser.clean_sweep_start()
    laser.clean_sweep_pause(-4)

    offset_GHz = laser.offset()

    while time.perf_counter() < wait_time + 5:
        offset_GHz = laser.offset()
        print('Clean sweep offset: %d GHz' % offset_GHz)
        time.sleep(0.2)

    logging.info('Clean sweep off: %d' % laser.itla_communicate(0xE5, 0, Laser.WRITE))
    time.sleep(3)
    laser.read_error()
    laser.wait_nop()
    time.sleep(1)
    logging.debug('Low noise mode: %d' % laser.itla_communicate(0x90, 0, Laser.WRITE))
    laser.read_error()

    laser.laser_off()
    laser.itla_disconnect()
else:
    logging.warning('Another error occurred: %d' % laser_err)
# except Exception as e:
#     logging.error(e)
#
# finally:
#     laser.clean_sweep_stop()
#
#     time.sleep(1)
#
#     laser.laser_off()
#     laser.ITLADisconnect()
#
#     time.sleep(2)
