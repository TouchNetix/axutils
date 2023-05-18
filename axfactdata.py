#!/usr/bin/env python3
################################################################################
#                                    NOTICE
#
# Copyright (c) 2010 - 2020 TouchNetix Limited
# ALL RIGHTS RESERVED.
#
# The source  code contained  or described herein  and all documents  related to
# the source code ("Material") are owned by TouchNetix Limited ("TouchNetix") or
# its suppliers  or licensors. Title to the Material  remains with TouchNetix or
# its   suppliers  and  licensors. The  Material  contains  trade  secrets   and
# proprietary  and confidential information  of TouchNetix or its  suppliers and
# licensors.  The  Material  is  protected  by  worldwide  copyright  and  trade
# secret  laws and  treaty  provisions.  No part  of the Material  may be  used,
# copied,  reproduced,  modified,   published,  uploaded,  posted,  transmitted,
# distributed or disclosed in any way without TouchNetix's prior express written
# permission.
#
# No  license under any  patent, copyright,  trade secret or other  intellectual
# property  right is granted to or conferred upon you by disclosure or  delivery
# of  the Materials, either  expressly, by implication, inducement, estoppel  or
# otherwise.  Any  license  under  such  intellectual  property rights  must  be
# expressly approved by TouchNetix in writing.
#
################################################################################

import sys
import argparse
from time import sleep
from axiom_tc import axiom

FORMAT_STRING="0x%01X"
def write_to_csv(file,data):
    for byte in data:
        file.write((FORMAT_STRING + "\n") % byte)

def print_array(data):
    for byte in data:
        print(FORMAT_STRING % byte)


def axiom_init(args, verbose=False):
    if args.i == "i2c":
        comms = I2C_Comms(args.i2c_bus, int(args.i2c_address, 16))

    elif args.i == "spi":
        comms = SPI_Comms(args.spi_bus, args.spi_device)

    elif args.i == "usb":
        comms = USB_Comms()

    # When instantiating the aXiom object, pass in the comms object which will
    # provide access to the low level reads and write methods.
    ax = axiom(comms)

    # Build the usage table, essentially discover the aXiom device. The main
    # aim with this is to locate all the usages so that when the config file is
    # loaded, it knows where to put all the data.
    ret = ax.build_usage_table()
    if ret:
        if verbose: ax.print_usage_table()
    else:
        raise ConnectionError

    if verbose:
        print("u33 CRC Data:")
        ax.get_u33_crc_data().show_crc_data()

    return ax


if __name__ == '__main__':

    exit_code = 0
    parser = argparse.ArgumentParser(description=\
    'Utility to retrieve the Factory Calibration Data from an aXiom device')
    parser.add_argument("-o", help='Output file for the Factory Calibration Data.', metavar='DATA_FILE', required=False, type=str, default='')
    parser.add_argument("-i", help='comms interface to communicate with aXiom', choices=["spi", "i2c", "usb"], required=True, type=str)
    parser.add_argument("-v", help='Print verbose messages', action="store_true")
    parser.add_argument("--i2c-bus", help='I2C bus number, as per `/dev/i2c-<bus>`', metavar='BUS', required=False, type=int)
    parser.add_argument("--i2c-address", help='I2C address, either 0x66 or 0x67', choices=["0x66", "0x67"], metavar='ADDR', required=False, type=str)
    parser.add_argument("--spi-bus", help='SPI bus number, as per `/dev/spi<bus>.<device>`', metavar='BUS', required=False, type=int)
    parser.add_argument("--spi-device", help='SPI device for CS, as per `/dev/spi<bus>.<device>`', metavar='DEV', required=False, type=int)
    args = parser.parse_args()

    # Get the config file path from the arguments
    data_file_name = args.o
    verbose = args.v


    # Import the requested comms layer
    if args.i == "i2c":
        if args.i2c_bus == None or args.i2c_address == None:
            print("The I2C bus and the I2C address arguments need to be specified.")
            parser.print_help()
            sys.exit(-1)
        else:
            from axiom_tc.I2C_Comms import I2C_Comms

    elif args.i == "spi":
        if args.spi_bus == None or args.spi_device == None:
            print("The SPI bus and the SPI device arguments need to be specified.")
            parser.print_help()
            sys.exit(-1)
        else:
            from axiom_tc.SPI_Comms import SPI_Comms

    elif args.i == "usb":
            from axiom_tc.USB_Comms import USB_Comms


    axiom = axiom_init(args, verbose=verbose)

    try:
        u36 = axiom.read_usage(0x36)

        # Parse get factory data and write to file
        if data_file_name != "":
            data_file = open(data_file_name, "w")
            write_to_csv(data_file, u36)
            print("%d bytes of factory Calibration Data saved to file." % len(u36))
        else:
            print_array(u36)

    except:
        print("Failed to read factory calibration data from aXiom.")
        exit_code = -1
        
    # Safely close the connection to aXiom
    axiom.close()
    sys.exit(exit_code)
