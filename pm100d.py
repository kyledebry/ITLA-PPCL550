"""Test code for PM100-D power supply"""

import visa
from ThorlabsPM100 import ThorlabsPM100
import time
from matplotlib import pyplot as plt
import numpy as np

rm = visa.ResourceManager()
resources = rm.list_resources()
inst = rm.open_resource(resources[0])
#print(inst.query('*IDN?'))
power_meter = ThorlabsPM100(inst=inst)

f = []

for _ in range(1000):
    f.append(power_meter.read)

plt.Figure()
plt.plot(f)
plt.show()
