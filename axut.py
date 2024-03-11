# Copyright (c) 2024 TouchNetix
# 
# This file is part of axutils and is released under the MIT License:
# See the LICENSE file in the root directory of this project or http://opensource.org/licenses/MIT.

import sys
from axiom_tc import axiom
from interface_arg_parser import *

if __name__ == '__main__':
    # Create argument parser
    parser = argparse.ArgumentParser(
        description='Utility to show the aXiom device\'s version information and usage table',
        epilog='''
Usage examples:
    python %(prog)s -i usb
    python %(prog)s -i usb
    python %(prog)s -i i2c --i2c-bus 1 --i2c-address 0x67
    python %(prog)s -i spi --spi-bus 0 --spi-device 0

Exit status codes:
    0 : Success
    2 : Script argument syntax issue. See --help
    3 : aXiom device is in bootloader mode
''',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[interface_arg_parser()])

    args = parser.parse_args()

    # Initialise comms with aXiom
    ax = axiom(get_comms_from_args(parser))

    # Prime the exit code
    exit_code = 0

    if ax.is_in_bootloader_mode():
        exit_code = 3
        print("INFO: aXiom device is in bootloader mode.")
    else:
        # Show the device version information and the usage table
        ax.u31.print_device_info()
        print()
        ax.u31.print_usage_table()

    # Safely close the connection to aXiom
    ax.close()
    sys.exit(exit_code)
