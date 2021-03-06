# -*- coding: utf-8 -*-
"""
Created on Wed May 22 15:40:53 2019

@author: Kyle DeBry
"""

from pure_photonics_utils import *
from laser import Laser
import curses
import logging
import sys

laser = Laser('COM2', 9600, logging.DEBUG)

try:

    freq = 193

    laser_err = laser.laser_on(freq)

    print('Laser error: %d' % laser_err)

    time.sleep(1)

    if laser_err == ITLA.NOERROR:

        sled_slope = laser.get_sled_slope()
        sled_spacing = laser.get_sled_spacing('CalibrationFiles\\CRTNHBM047_21_14_43_4.sled')
        map_vals = Laser.read_mapfile('CalibrationFiles\\CRTNHBM047_1000_21_14_39_59.map')

        screen = curses.initscr()
        curses.noecho()
        curses.cbreak()
        screen.keypad(True)

        run = True

        while run:
            ch = screen.getch()

            if ch == ord('q'):
                run = False
                print('Shutting off...')
            elif ch == ord('r'):
                print('Restarting...')
                laser.laser_off()
                time.sleep(1)
                laser.laser_on(freq)
                time.sleep(1)
            else:
                old_freq = freq

                if ch == curses.KEY_RIGHT:
                    freq = freq + 0.001
                elif ch == curses.KEY_LEFT:
                    freq = freq - 0.001
                elif ch == curses.KEY_SRIGHT:
                    freq = freq + 0.01
                elif ch == curses.KEY_SLEFT:
                    freq = freq - 0.01
                elif ch == curses.KEY_UP:
                    freq = freq + 0.1
                elif ch == curses.KEY_DOWN:
                    freq = freq - 0.1
                elif ch == ord('d'):
                    freq = freq + 1
                elif ch == ord('a'):
                    freq = freq - 1

                if freq > 196.25 or freq < 191.5:
                    freq = old_freq
                    print('Frequency out of range!')
                else:
                    icm.clean_jump(laser, freq, sled_spacing, sled_slope, map_vals)
                    time.sleep(1)

        time.sleep(1)
        laser.itla_communicate(ITLA.REG_Cjumpon, 0, ITLA.WRITE)

        icm.laser_off(laser)

except:
    e = sys.exc_info()[0]
    print(e)
    time.sleep(5)

finally:
    laser.itla_disconnect()
    print('Press any key to exit')
    screen.getch()
    curses.nocbreak()
    screen.keypad(0)
    curses.echo()
    curses.endwin()
