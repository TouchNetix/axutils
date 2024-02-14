# Copyright (c) 2024 TouchNetix
# 
# This file is part of [Project Name] and is released under the MIT License: 
# See the LICENSE file in the root directory of this project or http://opensource.org/licenses/MIT.

import sys
import argparse
from time import sleep
from axiom_tc import axiom

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Utility to load aXiom config files onto a device')
    parser.add_argument("-i", help='comms interface to communicate with aXiom', choices=["spi", "i2c", "usb"], required=True, type=str)
    parser.add_argument("--i2c-bus", help='I2C bus number, as per `/dev/i2c-<bus>`', metavar='BUS', required=False, type=int)
    parser.add_argument("--i2c-address", help='I2C address, either 0x66 or 0x67', choices=["0x66", "0x67"], metavar='ADDR', required=False, type=str)
    parser.add_argument("--spi-bus", help='SPI bus number, as per `/dev/spi<bus>.<device>`', metavar='BUS', required=False, type=int)
    parser.add_argument("--spi-device", help='SPI device for CS, as per `/dev/spi<bus>.<device>`', metavar='DEV', required=False, type=int)
    args = parser.parse_args()

    # Import the requested comms layer
    if args.i == "i2c":
        if args.i2c_bus == None or args.i2c_address == None:
            print("The I2C bus and the I2C address arguments need to be specified.")
            parser.print_help()
            sys.exit(-1)
        else:
            from axiom_tc.I2C_Comms import I2C_Comms
            comms = I2C_Comms(args.i2c_bus, int(args.i2c_address, 16))

    elif args.i == "spi":
        if args.spi_bus == None or args.spi_device == None:
            print("The SPI bus and the SPI device arguments need to be specified.")
            parser.print_help()
            sys.exit(-1)
        else:
            from axiom_tc.SPI_Comms import SPI_Comms
            comms = SPI_Comms(args.spi_bus, args.spi_device)

    elif args.i == "usb":
        from axiom_tc.USB_Comms import USB_Comms
        comms = USB_Comms()


    # When instantiating the aXiom object, pass in the comms object which will
    # provide access to the low level reads and write methods.
    axiom = axiom(comms)

    axiom.u31.print_device_info()
    axiom.u31.print_usage_table()

    axiom.close()
    sys.exit(0)
