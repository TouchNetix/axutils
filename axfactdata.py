# Copyright (c) 2024 TouchNetix
# 
# This file is part of axutils and is released under the MIT License:
# See the LICENSE file in the root directory of this project or http://opensource.org/licenses/MIT.

import sys
from axiom_tc import axiom
from interface_arg_parser import *
from exitcodes import *

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
    3 : aXiom device is in bootloader mode
''',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[interface_arg_parser()])

    # Create argument groups
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument("-o", "--output",
                              help='Output file for the u36 Factory Calibration Data',
                              metavar='DATA_FILE',
                              required=False, type=str, default='')

    args = parser.parse_args()

    # Initialise comms with aXiom
    ax = axiom(get_comms_from_args(parser))

    # Prime the exit code
    exit_code = SUCCESS

    if ax.is_in_bootloader_mode():
        exit_code = ERROR_AXIOM_IN_BOOTLOADER
        print("INFO: aXiom device is in bootloader mode.")
    else:
        # Read the u36 from the aXiom device
        u36 = ax.read_usage(0x36)

        # Either print the output to stdout or write the contents to a file
        if args.output != "":
            write_data_to_file(args.output, u36)
        else:
            print_data(u36)

    # Safely close the connection to aXiom
    ax.close()
    sys.exit(exit_code)
