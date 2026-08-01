from customTypes import *
import math
import csv
from pathlib import Path
import pygame as pg
import time
import sys
from bitarray import bitarray
from bitarray.util import int2ba, ba2int
import numpy as np

class Emulation:
    def __init__(self, filepath, screen, pgmctr=0, delay = 0):
        # initialize path to rom, relevant registers and flags
        self.screen = screen
        self.rompath = filepath
        self.delay = delay
        self.regA = 0x00
        self.regX = 0x00
        self.regY = 0x00
        self.regPW = False
        self.regPT = 0x00
        self.regPV = 0x00
        self.opcode = 0
        self.cycles = 0
        self.halt = False
        # Treating the flags as components of a byte might increase performance when it comes to pushing and pulling flags
        # I also think it would tank performance in a lot of other places where a simple boolean check is replaced with modulus math
        # There might be some good compromise, but I don't think there are major gains to be had here?
        # TODO: Future me here, bitarrays are awesome and a boolean check can be flagarray[x] so yeah definitely worht looking into
        self.flag_Carry = False
        self.flag_Zero = False
        self.flag_InterruptDisable = False
        self.flag_Decimal = False
        self.flag_Overflow = False
        self.flag_Negative = False
        self.stackptr = 0xFD
        self.logger = []
        self.iter = 0
        self.oplookup = {}
        # initialize CPU Adressable space ( I believe ram will need to be randomized on startup in the future)
        self.addSpace = np.zeros(0x10000, dtype=np.uint8)
        # Initialize rom and insert
        tempread = []
        with open(self.rompath, "rb") as data:
            self.header = (chunk for chunk in data.read(0x10))
            tempread += (chunk for chunk in data.read())
            self.addSpace   [0x800:len(tempread)+0x800] = np.array(tempread, dtype=np.uint8)
        # Initalize PPU Addressable space then write CHR ROM to it
        self.vaddSpace = np.zeros(0x3FFF, dtype=np.uint8)
        self.vaddSpace[0:0x1FFF] = self.addSpace[0x8800:0xA7FF]
        print(list(map(lambda x: hex(x), self.vaddSpace[0:0x40])))
        # Move the Program Counter to correct space (Little Endian), or custom address if debug is active
        if pgmctr:
            self.pgmctr = pgmctr
        else:
            self.pgmctr = self.addSpace[0xFFFC] + np.uint16(self.addSpace[0xFFFD]) * 256
            self.makesprites()

    def makesprites(self):
        #TODO Convert to pg biteplanes instead of nested lists
        chardata = self.vaddSpace[:0x2000]
        spritesheet = []
        # Ingest spritedate as 2 bitplanes, combine the bitmaps with bp2 having a value of 2 to give palette range between 0-3
        for spritepointer in range(0, len(chardata), 16):
            spritedata = chardata[spritepointer:spritepointer+16]
            bp1 = list(map(lambda x: int2ba(x,8), spritedata[0:8]))
            bp2 = list(map(lambda x: int2ba(x,8), spritedata[8:16]))
            sprite = [list(map(lambda x: int2ba(x[0] + x[1]*2), zip(bp1[y], bp2[y]))) for y in range(8)]
            spritesheet.append(sprite)
        self.sprites = spritesheet

    def draw(self):
        # TODO Import palette data to pass onto pixel constructor
        palette = [(0, 0, 0),(85, 85, 85), (170, 170, 170),(255, 255, 255)]
        for table in range(0, 2):
            for row in range(0,16):
                for col in range(0,16):
                    for y in range (0,8):
                        for x in range (0,8):
                            spritedata = self.sprites[table*256+col*16+row]
                            calcx = table*128 + row*8 + x
                            calcy = col*8 + y
                            self.screen.set_at((calcx, calcy), palette[ba2int(spritedata[y][x])])
        pg.display.flip()

    def run_emu(self, log): # Primary event loop
        logger = csv.writer(log)
        logger.writerow(["Program Counter", "Op", "Reg A", "Reg X", "Reg Y", "Fstring"])
        self.flag_InterruptDisable = True
        while not self.halt:
            if self.delay:
                time.sleep(self.delay)
            self.draw()
            self.opcode = self.addSpace[self.pgmctr]
            logger.writerow([hex(self.pgmctr), hex(self.opcode), self.opcode, hex(self.regA), hex(self.regX), hex(self.regY), self.build_Fstring(), self.addSpace[0:0x0C]])
            #TODO: Implement op lookup table for more readable logging
            self.pgmctr += 0x1
            self.op()
            while self.cycles:
                self.draw()
                self.cycles -= 1
        return False

    def build_Fstring(self):
        base = ""
        if self.flag_Negative:
            base = base + "N"
        else:
            base = base + "n"
        if self.flag_Overflow:
            base = base + "V"
        else:
            base = base + "v"
        base = base + "TB"
        if self.flag_Decimal:
            base = base + "D"
        else:
            base = base + "d"
        if self.flag_InterruptDisable:
            base = base + "I"
        else:
            base = base + "i"
        if self.flag_Zero:
            base = base + "Z"
        else:
            base = base + "z"
        if self.flag_Carry:
            base = base + "C"
        else:
            base = base + "c"
        return base

    def push(self, value): # Push value to stack, decrease stack pointer
        self.write(0x100 + self.stackptr, value)
        self.stackptr -= 1

    def pull(self): # Pull value from stack, increase stack pointer
        if self.stackptr == 0xFF:
            self.stackptr = 0x00
        else:
            self.stackptr += 1
        return self.read(0x100 + self.stackptr)

    def read(self, address=-1, mirror=True): # Read from address, if no address is specified, the address will be taken from the program coutner
        if address == -1:
            address = self.pgmctr
        while 0x1FFF > address >= 0x800 and mirror:
            address -= 0x800
        return self.addSpace[address]

    def write(self, address, data): # Write data to address in memory
        if address < 0x2000:
            self.addSpace[address & 0x7FF] = int(data)
        elif address < 0x4000:
            address &= 2007
            match address:
                case 0x2000:
                    pass
                case 0x2001:
                    pass
                case 0x2002:
                    pass
                case 0x2003:
                    pass
                case 0x2004:
                    pass
                case 0x2005:
                    pass
                case 0x2006:
                    if not self.regPW:
                        # First write to 2006 is big endian adress
                        ppuaddr = data*16
                    else:
                        ppuaddr += data
                        regPT = ppuaddr
                        regPV = ppuaddr
                    self.regPW = not self.regPW
                case 0x2007:
                    if regPV < 0x2000:
                        # Write to Pattern Table if
                        if not self.header[5]:
                            pass
                            # I AM HERE, need to refactor the way I handle CHRData and sprite generation
                        pass
                    elif regPV < 0x3F00:
                        # Write to Nametables
                        pass
                    else:
                        # Write to Palette RAM
                        pass

        else:
            raise MemoryError(f"Attemplted to reference out of scope address {address}")
            self.halt = True
        
        

    def set_flags(self, value, negative=True, zero=True): # Set relevant flags based on passed value.
        self.flag_Negative = value > 127 and negative
        self.flag_Zero = value == 0 and zero

    def get_abs(self): # Get Absolute Address
        tlow = self.read()
        self.pgmctr += 1
        return tlow + self.read() * 256

    def get_abs_indx(self, addr, index):
        self.cycles += addr % 256 + index > 255
        return addr + index
    # TODO, utilize this function in indirect inclusive / exclusive?

    def get_incl_indr(self, offset=-1):
        if offset == -1:
            offset = self.regX
        addr = self.read(self.pgmctr) + offset
        return addr

    def get_excl_indr(self, offset=-1):
        if offset == -1:
            offset = self.regY
        # Why return 2 different values? $91 does NOT cost an additional cycle for crossing page boundaries unlike every other Exclusive Indirect Addressing,
        # so we will let the op choose whether it adss one extra cycle or not
        addr = self.read(self.read())
        return addr + offset, addr + offset > 256

    def adc(self, a, b): # Add with carry
        tempval = a + b + self.flag_Carry
        self.flag_Carry = tempval > 255
        while tempval > 255:
            tempval -= 256
        self.regA = tempval
        tempsigned = signed8(a) + signed8(b) + self.flag_Carry
        self.flag_Overflow = -128 > tempsigned or tempsigned > 127
        self.set_flags(tempval)
        return tempval

    def sbc(self, a, b): # Subtract with Carry
        tempval = a - b - (not self.flag_Carry)
        self.flag_Carry = tempval > 0
        while tempval < 0:
            tempval += 256
        self.set_flags(tempval)
        t1 = a > 127
        t2 = b > 127
        t3 = tempval > 127
        # Get the signed flag of each number, set overflow if
        # A positive - negative = negative or if a negative - positive = positive
        # Simplified as sign of a != sign of b and sign of b == sign of c
        self.flag_Overflow = t1 != t2 and t2 == t3
        return tempval
        # overflow if bit 7 0,1,1 or 1,0,0

    def asl(self, val): # Arithmetic shift left
        self.flag_Carry = val > 127
        val = (val % 128)*2
        self.set_flags(val)
        return val

    def lsr(self, val): # Logical Shift Right
        self.flag_Carry = val % 2 == 1
        val -= self.flag_Carry
        val /= 2
        self.set_flags(val)
        return val

    def rol(self, val): # Roll Left
        willcarry = val > 127
        val = (val % 128)*2 + self.flag_Carry
        self.set_flags(val)
        self.flag_Carry = willcarry
        return val

    def ror(self, val): # Roll Right
        willcarry = val % 2 == 1
        val -= willcarry
        val /= 2
        val += (self.flag_Carry*128)
        self.set_flags(val)
        self.flag_Carry = willcarry
        return val
        # There may be a more efficient way to set the 8th bit then mult by 0 / 1

    def inc(self, val):
        val += 1
        if val == 256:
            val = 0
        self.set_flags(val)
        return val

    def cmp(self, a, b):
        self.flag_Zero = a == b
        self.flag_Negative = (a - b) > 127
        self.flag_Carry = a >= b

    def bit(self, byte):
        self.flag_Zero = (byte & self.regA) == 0
        self.flag_Negative = byte > 127
        self.flag_Overflow = byte > 63

    def dec(self, a):
        a -= 1
        a += 256 * (a < 0)
        return a

    def op(self):
        # I'M GONNA RENAME INDIRECT INDEXED ADDRESSING TO EXCLUSIVE ADDRESSING AND INDEXED INDIRECT ADDRESSING TO INCLUSIVE ADDRESSING
        # Okay so ($04, X) will be called Inclusive indirect and ($04), Y will be called Exclusive please email all of your complaints to gaben@valvesoftware.com

        # At the beginning of each op, the program counter will point to the address immediately following the opcode
        # For operations with a length of one, a return should be used to skip this automatic increment at the end of the op function
        # These automatic increments are done in an attempt to shorten the  amount of space each op takes up, I realize this may not be best practice
        # And if it proves to be too confusing I can revisit this later

        match self.opcode:
            case 0x00:
                #region Break
                self.pgmctr += 1
                self.push(math.floor(self.pgmctr / 256)); self.push(self.pgmctr % 256)
                #TODO: B I T A R R A Y T H I S G A R B A G E
                flags = self.flag_Carry
                flags += self.flag_Zero * 2
                flags += self.flag_InterruptDisable * 4
                flags += self.flag_Decimal * 8
                flags += 0x30
                flags += self.flag_Overflow * 64
                flags += self.flag_Negative * 128
                self.push(flags)
                tlow = self.read(0xFFFE)
                thigh = self.read(0xFFFF)
                self.pgmctr = tlow + np.uint16(thigh) * 256
                self.cycles += 7
                return
                #endregion
            case 0x01:
                #region OR w/ Accumulator, Indirect X (Inclusive Indirect)
                addr = self.get_incl_indr()
                self.regA |= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 6
                #endregion
            case 0x02:
                    #region Halt
                self.halt = True
                #endregion
            case 0x05:
                #region OR w/ Accumulator Zero Page
                addr = self.read()
                self.regA |= self.read(addr)
                self.set_flags(self.regA); self.cycles += 3
                #endregion
            case 0x06:
                #region Arithmetic Shift Left Zero Page
                addr = self.read()
                self.write(addr, self.asl(self.read(addr)))
                self.cycles = 5
                #endregion
            case 0x08:
                #region Push Flags
                flagbyte = 48
                if self.flag_Carry:
                    flagbyte += 1
                if self.flag_Zero:
                    flagbyte += 2
                if self.flag_InterruptDisable:
                    flagbyte += 4
                if self.flag_Decimal:
                    flagbyte += 8
                if self.flag_Overflow:
                    flagbyte += 64
                if self.flag_Negative:
                    flagbyte += 128
                self.push(flagbyte); self.cycles += 3; return
                #endregion
            case 0x09:
                #region OR w/ Accumulator Immediate
                self.regA |= self.read()
                self.set_flags(self.regA); self.cycles += 2
                #endregion
            case 0x0D:
                #region OR w/ Accumulator Absolute
                self.regA |= self.read(self.get_abs())
                self.set_flags(self.regA); self.cycles += 4
                #endregion
            case 0x0A:
                #region Arithmetic Shift Left Accumulator
                self.regA = self.asl(self.regA)
                self.cycles = 2; return
                #endregion
            case 0x0E:
                #region Arithmetic Shift Left Absolute
                addr = self.get_abs()
                self.write(addr, self.asl(self.read(addr))); self.cycles += 6
                #endregion
            case 0x10:
                #region Branch on Plus
                if not self.flag_Negative:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
                #endregion
            # TODO: Refactor Branching to use get_abs_indx()
            case 0x11:
                #region OR w/ Accumulator Indirect, Y Indexed (Exclusive Indirect)
                addr, addcycle = self.get_excl_indr()
                self.regA |= self.read(addr)
                self.cycles += addcycle + 5
                self.set_flags(self.regA)
                #endregion
            case 0x15:
                #region OR w/ Accumulator Zero Page, X Indexed
                addr = (self.read() + self.regX) % 256
                self.regA |= self.read(addr)
                self.set_flags(self.regA); self.cycles += 4
                #endregion
            case 0x16:
                #region Arithmetic Shift Left Zero Page, X Indexed
                addr = (self.read() + self.regX) % 256
                self.write(addr, self.asl(self.read(addr))); self.cycles += 6
                #endregion
            case 0x18:
                #region Clear Carry
                self.flag_Carry = False; self.cycles += 2
                return
                #endregion
            case 0x19:
                #region OR w/ Accumulator Absolute, Y Index
                addr = self.get_abs_indx(self.get_abs(), self.regY)
                self.regA |= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                #endregion
            case 0x1D:
                #region OR w/ Accumulator Absolute, X Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regX)
                self.regA |= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                #endregion
            case 0x1E:
                #region Arithmetic Shift Left Absolute, X Indexed
                addr = self.get_abs() + self.regX
                self.write(addr, self.asl(self.read(addr))); self.cycles += 7
                #endregion
            case 0x20:
                #region Jump to Subroutine
                tlow = self.read(); self.pgmctr += 1
                thigh = self.read()
                self.push(math.floor(self.pgmctr/256)); self.push(self.pgmctr % 256)
                self.pgmctr = (tlow+thigh*256); self.cycles += 6
                return # prevent auto increment to pgmctr since we just set it
                #endregion
            case 0x21:
                #region AND w/ Accumulator Indirect, X Indexed (Inclusive Indirect)
                addr = self.get_incl_indr()
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 6
                #endregion
            case 0x24:
                #region test Bit Zero Page
                addr = self.read()
                self.bit(self.read(addr))
                self.cycles += 3
                #endregion
            case 0x25:
                #region AND w/ Accumulator Zero Page
                addr = self.read()
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 3
                #endregion
            case 0x26:
                #region Rotate Left Zero Page
                addr = self.read()
                self.write(addr, self.rol(self.read(addr))); self.cycles += 5
                #endregion
            case 0x28:
                #region Pull Flags
                flags = bin(self.pull())[2:]
                while len(flags) < 8:
                    flags = "0" + flags
                self.flag_Carry = flags[7] == "1"
                self.flag_Zero = flags[6] == "1"
                self.flag_InterruptDisable = flags[5] == "1"
                # self.flag_Decimal = flags[4] Not necessary due to NES disabling BCD
                self.flag_Overflow = flags[1] == "1"
                self.flag_Negative = flags[0] == "1"
                self.cycles += 3; return
                #endregion
                # TODO: Probably more efficient to do this as subtraction in a while loop?
                # TODO: Might be better to represent flag state as a byte rather than converting when necessary?
                # TODO: Reviewing code, yet another case of I should use bitarrays here
            case 0x29:
                #region AND w/ Accumulator Immediate
                self.regA &= self.read()
                self.set_flags(self.regA)
                self.cycles += 2
                #endregion
            case 0x2A:
                #region Rotate Left Accumulator
                self.regA = self.rol(self.regA)
                self.cycles += 2; return
                #endregion
            case 0x2C:
                #region test Bit Absolute
                addr = self.get_abs()
                self.bit(self.read(addr))
                self.cycles += 4
                #endregion
            case 0x2D:
                #region AND w/ Accumulator Absolute
                addr = self.get_abs()
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                #endregion
            case 0x2E:
                #region Rotate Left Absolute
                addr = self.get_abs()
                self.write(addr, self.rol(self.read(addr)))
                self.cycles += 6
                #endregion
            case 0x30:
                #region Branch on Minus
                if self.flag_Negative:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
                #endregion
            case 0x31:
                #region AND w/ Accumulator Indirect, Y Indexed (Exclusive Indirect)
                addr, addcycle = self.get_excl_indr()
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 5 + addcycle
                #endregion
            case 0x35:
                #region AND w/ Accumulator Zero Page, X Indexed
                addr = (self.read() + self.regX) % 256
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                #endregion
            case 0x36:
                #region Rotate Left Zero Page, X Indexed
                addr = (self.read() + self.regX) % 256
                self.write(addr, self.rol(self.read(addr))); self.cycles += 6
                #endregion
            case 0x38:
                #region Set Carry
                self.flag_Carry = True; self.cycles += 2
                return
                #endregion
            case 0x39:
                #region AND w/ Accumulator Absolute Y Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regY)
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                #endregion
            case 0x3D:
                #region AND w/ Accumulator Absolute X Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regX)
                self.regA &= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                #endregion
            case 0x3E:
                #region Rotate Left Absolute, X Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regX) # Add cycle if page boundary crossed
                self.write(addr, self.rol(self.read(addr)))
                self.cycles += 7
                #endregion
            case 0x40:
                #region Return from Interrupt
                flags = self.pull()
                tlow = self.pull(); thigh = self.pull()
                self.pgmctr = tlow + thigh * 256
                self.flag_Negative = flags > 127
                flags -= self.flag_Negative * 128
                self.flag_Overflow = flags > 63
                flags -= self.flag_Overflow * 64 - 0x30
                self.flag_Decimal = flags > 7
                flags -= self.flag_Decimal * 8
                self.flag_InterruptDisable = flags > 3
                flags -= self.flag_InterruptDisable
                self.flag_Zero = flags > 1
                self.flag_Carry = flags % 2 == 1
                self.cycles += 7
                return
                #endregion
            case 0x41:
                #region EOR w/ Accumulator Indirect, X Indexed (Inclusive Indirect)
                addr = self.get_incl_indr()
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 6
                #endregion
            case 0x45:
                #region EOR w/ Accumulator Zero Page
                addr = self.read()
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 3
                #endregion
            case 0x46:
                #region Logical Shift Right Zero Page
                addr = self.read()
                self.write(addr, self.lsr(self.read(addr)))
                self.cycles += 5
                #endregion
            case 0x48:
                #region Push Accumulator
                self.push(self.regA); self.cycles += 3
                return
                #endregion
            case 0x49:
                #region EOR w/ Accumulator Immediate
                self.regA ^= self.read()
                self.set_flags(self.regA)
                self.cycles += 2
                #endregion
            case 0x4A:
                #region Logical Shift Right Accumulator
                self.regA = self.lsr(self.regA)
                self.cycles += 2; return
                #endregion
            case 0x4C:
                #region Jump
                tlow = self.read(); self.pgmctr += 1
                thigh = self.read()
                self.pgmctr = (tlow + thigh * 256); self.cycles += 3
                return # prevent auto increment to pgmctr since we just set it
                #endregion
            case 0x4D:
                #region EOR w/ Accumulator Absolute
                addr = self.get_abs()
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                #endregion
            case 0x4E:
                #region Logical Shift Right Absolute
                addr = self.get_abs()
                self.write(addr, self.rol(self.read(addr)))
                self.cycles += 6
                #endregion
            case 0x50:
                #region Branch on Not Overflow
                if not self.flag_Overflow:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
                #endregion
            case 0x51:
                #region EOR w/ Accumulator Indirect, Y Indexed (Exclusive Indirect)
                addr, addcycle = self.get_excl_indr()
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 5 + addcycle
                #endregion
            case 0x55:
                #region EOR w/ Accumulator Zero Page, X Indexed
                addr = self.read() + self.regX
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                #endregion
            case 0x56:
                #region Logical Shift Right Zero Page, X Indexed
                addr = (self.read() + self.regX) % 256
                self.write(addr, self.lsr(self.read(addr)))
                #endregion
            case 0x58:
                #region Clear Interrupt-Disable
                self.flag_InterruptDisable = False; self.cycles += 2
                return
                #endregion
            case 0x59:
                #region EOR w/ Accumulator Absolute Y Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regY)  # Add cycle if page boundary crossed
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                #endregion
            case 0x5D:
                #region EOR w/ Accumulator Absolute X Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regX)  # Add cycle if page boundary crossed
                self.regA ^= self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                #endregion
            case 0x5E:
                #region Logical Shift Right Absolute, X Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regX)  # Add cycle if page boundary crossed
                self.write(addr, self.lsr(self.read(addr))); self.cycles += 7
                #endregion
            case 0x60:
                #region Return from Subroutine
                tlow = self.pull()
                self.pgmctr = (tlow+self.pull()*256); self.cycles += 6
                #endregion
            case 0x61:
                #region Add with Carry Indirect, X Indexed (Inclusive Indirect)
                addr = self.get_incl_indr()
                self.regA = self.adc(self.read(addr), self.regA)
                self.cycles += 6
                #endregion
            case 0x65:
                #region Add to Accumulator Zero Page
                addr = self.read()
                self.regA = self.adc(self.regA, self.read(addr))
                self.cycles += 3
                #endregion
            case 0x66:
                #region Rotate Right Zero Page
                addr = self.read()
                self.write(addr, self.ror(self.read(addr))); self.cycles += 5
                #endregion
            case 0x68:
                #region Pull Accumulator
                self.regA = self.pull(); self.cycles += 4
                self.set_flags(self.regA)
                return
                #endregion
            case 0x69:
                #region Add to Accumulator Immediate
                self.regA = self.adc(self.regA, self.read())
                self.cycles += 2
                # Fun fact, the NES does not use the Decimal flag, ask me how much time I spent implementing BCD from the raw 6502 docs before coming to this realization
                #endregion
            case 0x6A:
                #region Rotate Right Accumulator
                self.regA = self.ror(self.regA)
                self.cycles += 2; return
                #endregion
            case 0x6C:
                #region Jump to Indirect Address
                addr = self.get_abs()
                tlow = self.read(addr)
                addr += 1
                if addr % 256 == 0:
                    addr -= 256
                thigh = self.read(addr)
                self.pgmctr = tlow + thigh*256
                self.cycles += 5
                return
                #endregion
            case 0x6D:
                #region Add to Accumulator Absolute
                addr = self.get_abs()
                self.regA = self.adc(self.regA, self.read(addr))
                self.cycles += 4
                #endregion
            case 0x6E:
                #region Rotate Right Absolute
                addr = self.get_abs()
                self.write(addr, self.ror(self.read(addr)))
                self.cycles += 6
                #endregion
            case 0x70:
                #region Branch on Overflow
                if self.flag_Overflow:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
                #endregion
            case 0x71:
                #region Add with Carry Indirect, Y Indexed (Exclusive Indirect)
                addr, addcycle = self.get_excl_indr()
                self.regA = self.adc(self.regA, self.read(addr))
                self.cycles += 5 + addcycle
                #endregion
            case 0x75:
                #region Add to Accumulator Zero Page, X Indexed
                addr = (self.read() + self.regX) % 256
                self.regA = self.adc(self.regA, self.read(addr))
                self.cycles += 4
                #endregion
            case 0x76:
                #region Rotate Right Zero Page, X Indexed
                addr = (self.read() + self.regX) % 256
                self.write(addr, self.ror(self.read(addr)))
                self.cycles += 6
                #endregion
            case 0x78:
                #region Set Interrupt-Disable
                self.flag_InterruptDisable = True; self.cycles += 2
                return
                #endregion
            case 0x79:
                #region Add to Accumulator Absolute, Y Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regY) # Add cycle if page boundary crossed
                self.regA = self.adc(self.regA, self.read(addr + self.regY))
                self.cycles += 4
                #endregion
            case 0x7D:
                #region Add to Accumulator Absolute, X Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regX)  # Add cycle if page boundary crossed
                self.regA = self.adc(self.regA, self.read(addr + self.regX))
                self.cycles += 4
                #endregion
            case 0x7E:
                #region Rotate Right Absolute, X Indexed
                addr = self.get_abs() + self.regX # No Additional cycles when boundary crossed
                self.write(addr, self.ror(self.read(addr)))
                self.cycles += 7
                #endregion
            case 0x81:
                #region Store Accumulator Indirect, X Indexed (Inclusive Indirect)
                addr = self.get_incl_indr()
                self.write(self.read(addr),self.regA)
                self.cycles += 6
                #endregion
            case 0x84:
                #region STY Zero Page
                self.write(self.read(), self.regY); self.cycles += 3
                #endregion
            case 0x85:
                #region STA Zero Page
                self.write(self.read(), self.regA)
                self.cycles += 3
                #endregion
            case 0x86:
                #region STX Zero Page
                self.write(self.read(), self.regX); self.cycles += 3
                #endregion
            case 0x88:
                #region Decrement Y
                self.regY = self.dec(self.regY)
                self.cycles += 2
                self.set_flags(self.regY)
                #endregion
            case 0x8A:
                #region Transfer X > A
                self.regA = self.regX; self.cycles += 2
                self.set_flags(self.regA); return
                #endregion
            case 0x8C:
                #region Store Register Y Absolute
                self.write(self.read(self.get_abs()), self.regY); self.cycles += 4
                #endregion
            case 0x8D:
                #region Store Register A Absolute
                self.write(self.get_abs(), self.regA)
                self.cycles += 4
                #endregion
            case 0x8E:
                #region Store Register X Absolute
                self.write(self.read(self.get_abs()), self.regX); self.cycles += 4
                #endregion
            case 0x90:
                #region Branch on Not Carry
                if not self.flag_Carry:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
                #endregion
            case 0x91:
                #region Store Accumulator Indirect, XY Indexed (Exclusive Indirect)
                addr, addcycle = self.get_excl_indr()
                self.write(self.read(addr), self.regA)
                self.cycles += 6
                #endregion
            case 0x95:
                #region STA Zero Page, X Indexed
                addr = (self.read() + self.regX) % 256
                self.write(addr, self.regA)
                self.cycles += 4
                #endregion
            case 0x98:
                #region Transfer Y > A
                self.regA = self.regY; self.cycles += 2
                self.set_flags(self.regA); return
                #endregion
            case 0x99:
                #region Store Accumulator Absolute, Y Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regX)
                self.write(self.read(addr), self.regA)
                self.cycles += 5
                #endregion
            case 0x9A:
                #region Transfer X to Stack Pointer
                self.stackptr = self.regX
                self.set_flags(self.regX)
                self.cycles += 2
                return
                #endregion
            case 0x9D:
                #region Store Accumulator Absolute, X Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regX)
                self.write(addr, self.regA)
                self.cycles += 5
                #endregion
            case 0xA0:
                #region Load Y Immediate
                self.regY = self.read(); self.cycles += 2
                self.set_flags(self.regY)
                #endregion
            case 0xA1:
                #region Load Accumulator Indirect, X Indexed (Inclusive Indirect)
                addr = self.get_incl_indr()
                self.regA = self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 6
                #endregion
            case 0xA2:
                #region Load Immediate X
                self.regX = self.read(); self.cycles += 2
                self.set_flags(self.regX)
                #endregion
            case 0xA5:
                #region Load A Zero Page
                self.regA = self.read(); self.cycles += 2
                self.set_flags(self.regA)
                #endregion
            case 0xA8:
                #region Transfer A > Y
                self.regY = self.regA; self.cycles += 2
                self.set_flags(self.regY); return
                #endregion
            case 0xA9:
                #region Load A Immediate
                self.regA = self.read(); self.cycles += 2
                self.set_flags(self.regA)
                #endregion
            case 0xAA:
                #region Transfer A > X
                self.regX = self.regA; self.cycles += 2
                self.set_flags(self.regX); return
                #endregion
            case 0xAD:
                #region Load A Absolute
                addr = self.get_abs()
                self.regA = self.read(addr)
                self.set_flags(self.regA); self.cycles += 4
                #endregion
            case 0xB0:
                #region Branch on Carry
                if self.flag_Carry:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1 # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1 # Takes 1 additional cycles if nonzero
                self.cycles += 2 # Takes 2 cycles no matter what
                #endregion
            case 0xB1:
                #region Load Accumulator Indirect, Y Indexed (Exclsuive Indirect)
                addr, addcycle = self.get_excl_indr()
                self.regA = self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 5 + addcycle
                #endregion
            case 0xB5:
                #region Load Accumulator Zero Page, X Indexed
                addr = (self.read() + self.regX) % 256
                self.regA = self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                #endregion
            case 0xB8:
                #region Clear Overflow
                self.flag_Overflow = False; self.cycles += 2
                return
                #endregion
            case 0xB9:
                #region Load Accumulator Absolute, Y Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regY)
                self.regA = self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                #endregion
            case 0xBA:
                #region Transfer Stack Pointer to X
                self.regX = self.stackptr
                self.set_flags(self.regX)
                self.cycles += 2
                return
                #endregion
            case 0xBD:
                #region Load Accumulator Absolute, X Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regX)
                self.regA = self.read(addr)
                self.set_flags(self.regA)
                self.cycles += 4
                #endregion
            case 0xC0:
                #region Compare with Y Register Immediate
                self.cmp(self.regY, self.read())
                self.cycles += 2
                #endregion
            case 0xC1:
                #region Compare with Accumulator Indirect, X Indexed (Inclusive Indirect)
                addr = self.get_incl_indr()
                self.cmp(self.regA, self.read(addr))
                self.cycles += 6
                #endregion
            case 0xC4:
                #region Compare with Y Zero Page
                addr = self.read()
                self.cmp(self.regY, self.read(addr))
                self.cycles += 3
                #endregion
            case 0xC5:
                #region Compare with Accumulator Zero Page
                addr = self.read()
                self.cmp(self.regA, self.read(addr))
                self.cycles += 3
                #endregion
            case 0xC6:
                #region Decrement Memory Zero Page
                addr = self.read()
                self.write(addr, self.dec(self.read(addr)))
                self.cycles += 5
                #endregion
            case 0xC8:
                #region Increment Y
                self.regY = self.inc(self.regY)
                self.cycles += 2; return
                #endregion
            case 0xC9:
                #region Compare with Accumulator Immediate
                self.cmp(self.regA, self.read())
                self.cycles += 2
                #endregion
            case 0xCA:
                #region Decrement X
                self.regX = self.dec(self.regX)
                self.cycles += 2
                self.set_flags(self.regX)
                return
                #endregion
            case 0xCC:
                #region Compare with Y Register Absolute
                addr = self.get_abs()
                self.cmp(self.regY, self.read(addr))
                self.cycles += 4
                #endregion
            case 0xCD:
                #region Compare with Accumulator Absolute
                addr = self.get_abs()
                self.cmp(self.regA, self.read(addr))
                self.cycles += 4
                #endregion
            case 0xCE:
                #region Decrement Memory Absolute
                addr = self.get_abs()
                self.write(addr,self.dec(self.read(addr)))
                self.cycles += 3
                #endregion
            case 0xD0:
                #region Branch on Not Equal
                if not self.flag_Zero:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1 # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1 # Takes 1 additional cycles if nonzero
                self.cycles += 2 # Takes 2 cycles no matter what
                #endregion
            case 0xD1:
                #region Compare with Accumulator Indirect, Y Indexed (Exclusive Indirect)
                addr = self.get_incl_indr()
                self.cmp(self.regA, self.read(addr))
                self.cycles += 5
                #endregion
            case 0xD5:
                #region Compare with Accumulator Zero Page, X Indexed
                addr = (self.read() + self.regX) % 256
                self.cmp(self.regA, self.read(addr))
                self.cycles += 3
                #endregion
            case 0xD6:
                #region Decrement Memory Zero Page, X Indexed
                addr = (self.read() + self.regX) % 256
                self.write(addr, self.dec(self.read(addr)))
                self.cycles += 6
                #endregion
            case 0xD8:
                #region Clear Decimal -- Not Used
                self.flag_Decimal = False; self.cycles += 2
                return
                #endregion
            case 0xD9:
                #region Compare with Accumulator Absolute, y Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regY)
                self.cmp(self.regA, self.read(addr))
                self.cycles += 4
                #endregion
            case 0xDD:
                #region Compare with Accumulator Absolute, X Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regX)
                self.cmp(self.regA, self.read(addr))
                self.cycles += 4
                #endregion
            case 0xDE:
                #region Decrement Memory Absolute, X Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regX)
                self.write(addr, self.dec(self.read(addr)))
                self.write += 7
                #endregion
            case 0xE0:
                #region Compare with X Register Immediate
                self.cmp(self.regX, self.read())
                self.cycles += 2
                #endregion
            case 0xE1:
                #region Subtract with Carry Indirect, X Indexed (Inclusive Indirect)
                addr = self.get_incl_indr()
                self.regA = self.sbc(self.regA, self.read(addr))
                self.cycles += 6
                #endregion
            case 0xE4:
                #region Compare with X Register Zero Page
                addr = self.read()
                self.cmp(self.regX, self.read(addr))
                self.cycles += 3
                #endregion
            case 0xE5:
                #region Subtract with Carry Zero Page
                addr = self.read()
                self.regA = self.sbc(self.regA, self.read(addr))
                self.cycles += 3
                #endregion
            case 0xE6:
                #region Increment Memory Zero page
                addr = self.read()
                self.write(addr, self.inc(self.read(addr)))
                self.cycles += 5
                #endregion
            case 0xE8:
                #region Increment X
                self.regX = self.inc(self.regX)
                self.cycles += 2; return
                #endregion
            case 0xE9:
                #region Subtract with Carry Immediate
                self.regA = self.sbc(self.regA, self.read())
                self.cycles += 2
                #endregion
            case 0xEA:
                #region No Operation
                self.cycles += 2; return
                #endregion
            case 0xEC:
                #region Compare with X Register Absolute
                addr = self.get_abs()
                self.cmp(self.regX, self.read(addr))
                self.cycles += 4
                #endregion
            case 0xED:
                #region Subtract with Carry Absolute
                addr = self.get_abs()
                self.regA = self.sbc(self.regA, self.read(addr))
                self.cycles += 4
                #endregion
            case 0xEE:
                #region Increment Memory Absolute
                addr = self.get_abs()
                self.write(addr, self.inc(self.read(addr)))
                self.cycles += 6
                #endregion
            case 0xF0:
                #region Branch on Equal
                if self.flag_Zero:
                    signedval = signed8(self.read())
                    temppg = self.pgmctr
                    self.pgmctr += signedval
                    if math.floor(temppg / 256) != math.floor(self.pgmctr / 256):
                        self.cycles += 1  # Branch takes extra cycle if crossing page boundary
                    self.cycles += 1  # Takes 1 additional cycles if nonzero
                self.cycles += 2  # Takes 2 cycles no matter what
                #endregion
            case 0xF1:
                #region Subtract with Carry Indirect, Y Indexed (Exclusive Indirect)
                addr, addcycle = self.get_excl_indr()
                self.regA = self.sbc(self.regA, self.read(addr))
                self.cycles += 5 + addcycle
                #endregion
            case 0xF5:
                #region Subtract with Carry Zero Page, X Indexed
                addr = (self.read() + self.regX) % 256
                self.regA = self.sbc(self.regA, self.read(addr))
                self.cycles += 4
                #endregion
            case 0xF6:
                #region Increment Memory Zero Page, X Indexed
                addr = (self.read() + self.regX) % 256
                self.write(addr, self.inc(self.read(addr)))
                self.cycles += 6
                #endregion
            case 0xF8:
                #region Set Decimal Flag -- Not Used
                self.flag_Decimal = True; self.cycles = 2
                return
                #endregion
            case 0xF9:
                #region Subtract with Carry Absolute, Y Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regY)
                self.regA = self.sbc(self.regA, self.read(addr))
                self.cycles += 4
                #endregion
            case 0xFD:
                #region Subtract with Carry Absolute, X Indexed
                addr = self.get_abs_indx(self.get_abs(), self.regX)
                self.regA = self.sbc(self.regA, self.read(addr))
                self.cycles += 4
                #endregion
            case 0xFE:
                #region Increment Memory Absolute, X Indexed
                addr = self.get_abs() + self.regX
                self.write(addr, self.inc(self.read(addr)))
                self.cycles += 7 # No additional cycles for crossing page boundary
                #endregion
            case _:
                print(hex(self.opcode) + " not implemented")
                self.halt = True
        # The below line automatically increments the counter for all cases
        # This can be skipped for one byte instructions by returning, it saves space
        self.pgmctr += 1

# TODO: Check if I can simplify ADC/SBC to not take RegA as an argument, as well as get_abs_inx taking get_abs as an arg
# TODO: Function to shorten length of branch instructions?
# TODO: Implement Overflow of 16 bit addresses, double check 8 bits are also handled correctly
# TODO: All standard arrays should be replaced with np arrays, especially arrays with more than one dimension, in these cases make sure to replace[x][y] with [x, y] as it is more efficient
# TODO: np has custom data types for signed and unsigned, look into dropping the custom signed type for np

