"""Test code for PM100-D power supply"""

import visa
from ThorlabsPM100 import ThorlabsPM100
import time

rm = visa.ResourceManager()
resources = rm.list_resources()
inst = rm.open_resource(resources[0])
#print(inst.query('*IDN?'))
power_meter = ThorlabsPM100(inst=inst)

while True:
    print(power_meter.read)
    time.sleep(.1)
