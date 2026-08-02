from timeit import timeit
import numpy as np
from bitarray import *
from bitarray.util import int2ba, ba2int

regPV = 100
inc32 = False
regPV += 32 if inc32 else 1
print(regPV)
inc32 = True
regPV += 32 if inc32 else 1
print(regPV)