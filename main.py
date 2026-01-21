from Emulation import Emulation
from customTypes import *
import datetime
from pathlib import Path
import pygame as pg
import time



# Using pathlib for more robust path handling

def main():
    # Pygame Initialization
    pg.init()
    screen = pg.display.set_mode((256, 128))
    clock = pg.time.Clock()
    running = True
    dt = 0
    # TODO Varialbe rom selection on startup
    rompath = "7_Graphics.nes"
    # TODO Hardcoded debug mode selectable on startup
    emu_instance = Emulation(rompath, screen)
    # TODO Deprecate timing for pg Clock?
    timenow = datetime.datetime.now()
    timeform = "%Y-%m-%d.%H.%M.%S"
    # Create a logfile and log folder if one does not already exist
    logfile = Path(f"logs/{timenow.strftime(timeform)}.csv")
    logfile.parent.mkdir(parents=True, exist_ok=True)




        # TODO Refactor logging to use a seperate thread instead of living insidethe main loop?
    # primary loop
    while running:
        with logfile.open("w", newline="") as log:
            emu_instance.run_emu(log)
            toprint = []
            for value in emu_instance.addSpace[0x10:0x1D]:
                toprint.append(value)
            output = list(map(hex, toprint))
            print(output)
            pass


if __name__ == '__main__':
    main()
