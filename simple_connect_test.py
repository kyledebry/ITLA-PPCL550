
from laser import Laser
import logging, time

laser = Laser('COM2', 115200, logging.DEBUG)

print(laser.itla_communicate(Laser.REG_GetFreqTHz, 0, Laser.READ))

print('Test: %d' % laser.itla_communicate(Laser.REG_Nop, 0, Laser.READ))

time.sleep(.2)

logging.info('%d GHz' % laser.itla_communicate(Laser.REG_FreqGHz, 500, Laser.WRITE))
laser.read_error()
time.sleep(.2)

logging.info('%d GHz' % laser.itla_communicate(Laser.REG_FreqGHz, 0, Laser.READ))
laser.read_error()

time.sleep(.2)

print(laser.itla_communicate(Laser.REG_GetFreqTHz, 0, Laser.READ))

laser.itla_disconnect()
