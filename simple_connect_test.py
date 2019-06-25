
from laser import Laser
import logging, time

laser = Laser('COM12', 115200, logging.DEBUG)

print('Test: %d' % laser.itla_communicate(Laser.REG_Nop, 0, Laser.READ))

time.sleep(.2)

logging.info('%d THz' % laser.send(Laser.REG_FreqTHz, 193))
time.sleep(.2)

logging.info('%d THz' % laser.read(Laser.REG_FreqTHz))

time.sleep(.2)

print(laser.read(Laser.REG_GetFreqTHz))

laser.itla_disconnect()
