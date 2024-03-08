# Copyright (c) 2024 TouchNetix
#
# This file is part of axutils and is released under the MIT License:
# See the LICENSE file in the root directory of this project or http://opensource.org/licenses/MIT.

import argparse

from version import __version__


def interface_arg_parser():
    """
    Adds the interface options to the argument parser so that all scripts can have a common set of arguments when
    invoking the scripts.
    For convenience, it also adds the --version option to the argument parser as this will also be common.
    """
    parser = argparse.ArgumentParser(add_help=False)  # Disable help to allow custom help in main parsers
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')

    # Create a group in the parser for all the interface options
    interface_group = parser.add_argument_group('Interface Options')

    # Add arguments to all the interfaces
    interface_group.add_argument("-i", "--interface",
                                 help='Comms interface to communicate with aXiom',
                                 choices=["spi", "i2c", "usb"],
                                 required=True)

    # Add I2C options, the bus number and the address
    interface_group.add_argument("--i2c-bus",
                                 help='I2C bus number, as per `/dev/i2c-<bus>`',
                                 metavar='BUS',
                                 type=int)
    interface_group.add_argument("--i2c-address",
                                 help='I2C address, either 0x66 or 0x67',
                                 choices=["0x66", "0x67"],
                                 metavar='ADDR')

    # Add the SPI options, the bus number and the device (for chip select)
    interface_group.add_argument("--spi-bus",
                                 help='SPI bus number, as per `/dev/spi<bus>.<device>`',
                                 metavar='BUS',
                                 type=int)
    interface_group.add_argument("--spi-device",
                                 help='SPI device for CS, as per `/dev/spi<bus>.<device>`',
                                 metavar='DEV',
                                 type=int)
    return parser


def get_comms_from_args(parser):
    """
    Parses the interface options from the scripts arguments to establish a connection to aXiom.
    """
    comms = None
    args = parser.parse_args()

    if args.interface == "i2c":
        if args.i2c_bus is None or args.i2c_address is None:
            parser.error("The --i2c-bus and --i2c-address arguments are required when using the I2C interface.")

        from axiom_tc import I2C_Comms

        comms = I2C_Comms(args.i2c_bus, int(args.i2c_address, 16))

    if args.interface == "spi":
        if args.spi_bus is None or args.spi_device is None:
            parser.error("The --spi-bus and --spi-device arguments are required when using the SPI interface.")

        from axiom_tc import SPI_Comms

        comms = SPI_Comms(args.spi_bus, args.spi_device)

    if args.interface == "usb":
        from axiom_tc import USB_Comms

        comms = USB_Comms()

    return comms
