# Copyright (c) 2024 TouchNetix
# 
# This file is part of [Project Name] and is released under the MIT License: 
# See the LICENSE file in the root directory of this project or http://opensource.org/licenses/MIT.


import argparse
from version import __version__
from axiom_tc import axiom

def print_data(data):
    # Header for byte indexes
    print('Offset (h) ', end='')
    for i in range(16):
        print(f'{i:02X}', end=' ')
    print()

    # Print each byte with an offset
    for i, byte in enumerate(data):
        if i % 16 == 0:
            print(f'{i:08X}: ', end=' ')
        print(f'{byte:02X}', end=' ')
        if (i + 1) % 16 == 0:
            print()  # Newline after every 16 bytes

    # Handle case where byte_array length is not a multiple of 16
    if len(data) % 16 != 0:
        print()

def write_data_to_file(file, data):
    with open(file, 'wb') as f:
        f.write(bytearray(data))

if __name__ == '__main__':
    # Create argument parser
    parser = argparse.ArgumentParser(
        description='Utility to retrieve the u36 Factory Calibration Data from an aXiom device',
        epilog='''
Usage examples:
    python %(prog)s -i usb
    python %(prog)s -i usb -o u36_output.bin
    python %(prog)s -i i2c --i2c-bus 1 --i2c-address 0x67 -o u36_output.bin
    python %(prog)s -i spi --spi-bus 0 --spi-device 0 -o u36_output.bin

Exit status codes:
    0 : Success
    2 : Script argument syntax issue. See --help
''', formatter_class=argparse.RawDescriptionHelpFormatter)
    
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')

    # Create argument groups
    interface_group = parser.add_argument_group('Interface Options')
    output_group = parser.add_argument_group('Output Options')

    # Add arguments to their respective groups
    interface_group.add_argument("-i", "--interface", help='Comms interface to communicate with aXiom', choices=["spi", "i2c", "usb"], required=True)
    interface_group.add_argument("--i2c-bus", help='I2C bus number, as per `/dev/i2c-<bus>`', metavar='BUS', type=int)
    interface_group.add_argument("--i2c-address", help='I2C address, either 0x66 or 0x67', choices=["0x66", "0x67"], metavar='ADDR')
    interface_group.add_argument("--spi-bus", help='SPI bus number, as per `/dev/spi<bus>.<device>`', metavar='BUS', type=int)
    interface_group.add_argument("--spi-device", help='SPI device for CS, as per `/dev/spi<bus>.<device>`', metavar='DEV', type=int)

    output_group.add_argument("-o", "--output", help='Output file for the u36 Factory Calibration Data', metavar='DATA_FILE', required=False, type=str, default='')

    args = parser.parse_args()
    
    if args.interface == "i2c":
        if (args.i2c_bus is None or args.i2c_address is None):
            parser.error("The --i2c-bus and --i2c-address arguments are required when using the I2C interface.")

        from axiom_tc.I2C_Comms import I2C_Comms
        comms = I2C_Comms(args.i2c_bus, int(args.i2c_address, 16))

    if args.interface == "spi":
        if (args.spi_bus is None or args.spi_device is None):
            parser.error("The --spi-bus and --spi-device arguments are required when using the SPI interface.")

        from axiom_tc.SPI_Comms import SPI_Comms
        comms = SPI_Comms(args.spi_bus, args.spi_device)

    if args.interface == "usb":
        from axiom_tc.USB_Comms import USB_Comms
        comms = USB_Comms()

    # Initialise comms with axiom 
    axiom = axiom(comms)

    # Read the u36 from the aXiom device
    u36 = axiom.read_usage(0x36)

    # Either print the output to stdout or write the contents to a file
    if args.output != "":
        write_data_to_file(args.output, u36)
    else:
        print_data(u36)

    # Safely close the connection to aXiom
    axiom.close()
