
array1 = [255, 128,100, 200, 0, 0]
binarray1 = [[(b >> i) & 1 == 1 for i in range(7, -1, -1)] for b in array1]
print(binarray1)