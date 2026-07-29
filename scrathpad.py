from bitarray import bitarray

regPT = 0
regPW = False
tempvram = bitarray(0)
def test(data):
    if not regPW:
        tempvram = bitarray(data*16)
    else:
        ppuaddr += data + tempvram
        regPT = ppuaddr
    print(regPT)
    regPW != regPW

test(0x1001)
test(0x0110)
print(regPT)