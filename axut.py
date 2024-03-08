# Copyright (c) 2024 TouchNetix
# 
# This file is part of axutils and is released under the MIT License:
# See the LICENSE file in the root directory of this project or http://opensource.org/licenses/MIT.

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
''',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[interface_arg_parser()])

    args = parser.parse_args()

    # Initialise comms with aXiom
    axiom = axiom(get_comms_from_args(parser))

    # Show the device version information and the usage table
    axiom.u31.print_device_info()
    print()
    axiom.u31.print_usage_table()

    axiom.close()
