# Copyright (c) 2024 TouchNetix
# 
# This file is part of axutils and is released under the MIT License:
# See the LICENSE file in the root directory of this project or http://opensource.org/licenses/MIT.

import os
import sys
import struct
from time import sleep
from axiom_tc import axiom
from axiom_tc import u31_DeviceInformation
from axiom_tc import u33_CRCData
from interface_arg_parser import *


def show_progress(current, total):
    progress = (float(current) / float(total)) * 100
    sys.stdout.write('\033[?25l')  # Hide cursor
    sys.stdout.write("Progress: %3.0f%%\r" % progress)
    sys.stdout.flush()
    sys.stdout.write('\033[?25h')  # Show cursor


def extract_usages_from_config_file(config_file):
    all_usages_size = 0
    usages = {}

    try:
        all_usages_size = os.path.getsize(config_file)

        with open(config_file, "rb") as file:
            # The first 4 bytes of the file contains a signature that we use to
            # identify the file as an aXiom config file.
            signature = struct.unpack(">I", file.read(4))[0]
            if signature == 0x20071969:
                # Skip to offset 13 (from start of file) to skip over the header and
                # get straight to the usage contents.
                file.seek(13)

                # Keep decoding the file until the end of file position is reached.
                while True:
                    # Extract the usage contents from the config file
                    usage, revision, _, length = struct.unpack("<3BH", file.read(5))
                    usage_content = list(struct.unpack("<" + str(length) + "B", file.read(length)))

                    # Store the contents into the usages list
                    usages[usage] = (usage, revision, usage_content)

                    # Check if the end of file has been reached
                    if file.tell() == all_usages_size:
                        break

            # Remove the config file header from the size. Also remove the 5 bytes of
            # overhead for each usage from the overall length.
            all_usages_size -= 13 + (len(usages) * 5)
    except FileNotFoundError:
        print("Config file not found: " + config_file)
    except IOError:
        print("An error occurred while accessing the config file")

    return all_usages_size, usages


def axcfg(ax, config_file, overwrite_u04):
    # Read u33 from the device to validate the config file is compatible later. u31 is
    # also required, but that is already available via the ax.u31 object.
    u33 = u33_CRCData(ax)

    # Extract out of the config file all the usages into a dictionary.
    all_usages_size, usages = extract_usages_from_config_file(config_file)

    # Before the new config is written to the device, check that the config file
    # is compatible with the device by comparing the runtime CRC in u33. Manually
    # populate the u33 content with the content from the file so that a compatibility
    # check can be performed
    u33_from_file = u33_CRCData(ax, False)
    u33_from_file._usage_revision = usages[0x33][1]
    u33_from_file._usage_binary_data = usages[0x33][2]
    u33_from_file.init_usage()
    u33_from_file._unpack()

    # Similarly, if the config file that was specified is incompatible, the details
    # would be in u31. Capture that here, but it will only be used if the config file
    # is not compatible. This information will tell us what firmware the config came from
    u31_from_file = u31_DeviceInformation(ax)
    u31_from_file._usage_revision = usages[0x31][1]
    u31_from_file._usage_binary_data = usages[0x31][2]
    u31_from_file._unpack()

    # Compare the firmware runtime CRC from the file with the CRC from the device.
    # Only proceed if the CRCs match.
    if u33_from_file.reg_runtime_crc != u33.reg_runtime_crc:
        print("ERROR: Cannot load config file as it was saved from a different revision of firmware.")
        print("Firmware info from device      : 0x{0:08X}, {1}".format(u33.reg_runtime_crc,
                                                                       ax.u31.get_device_info_short()))
        print("Firmware info from config file : 0x{0:08X}, {1}".format(u33_from_file.reg_runtime_crc,
                                                                       u31_from_file.get_device_info_short()))
        return 3

    # Stop axiom from performing measurements whilst loading the config file.
    ax.u02.send_command(ax.u02.CMD_STOP)

    # Zero out the config for good measure, this is mostly useful when switching between firmware variants. However,
    # this will also affect u04. Cache u04, fill the config and write u04 back. u04 contains data that a customer would
    # have written to the device. It may get overwritten later based on the config file and the script arguments.
    u04 = ax.read_usage(0x04)
    ax.u02.send_command(ax.u02.CMD_FILL_CONFIG)
    ax.write_usage(0x04, u04)

    # Write the config to the device by iterating over all the usages from the config file
    bytes_written = 0
    for usage in usages:
        _ = usages[usage][1]  # Usage Revision
        usage_content = usages[usage][2]

        # u04 contains customer populated data, such as serial numbers, part numbers
        # serial numbers, etc. Therefore, it is assumed that the customer would want
        # to keep the data they have input unless otherwise specified (-c option).
        if usage != 0x04 or (usage == 0x04 and overwrite_u04):
            ax.config_write_usage_to_device(usage, usage_content)

        bytes_written += len(usage_content)
        show_progress(bytes_written, all_usages_size)

    # The CDUs will already have had their contents stored to NVM, but the main
    # usages are still only in RAM. Issuing this command to commit them to
    # NVM.
    ax.u02.send_command(ax.u02.CMD_SAVE_CONFIG)

    # Give aXiom some time to write the contents to NVM.
    sleep(2)

    # Restart aXiom
    ax.u02.send_command(ax.u02.CMD_SOFT_RESET)
    sleep(1)

    # Verify if the contents have been loaded onto the device correctly by re-reading
    # u33 from the device and comparing it with the file
    u33 = u33_CRCData(ax)
    config_loaded_successfully = u33.compare_u33(u33_from_file, True)
    if not config_loaded_successfully:
        print("ERROR: The config file does not match the config on the device.")
        return 4

    return 0

def axcfg_compare_u33(ax, config_file):
    # Read u33 from the device to validate the config file is compatible later. u31 is
    # also required, but that is already available via the ax.u31 object.
    u33 = u33_CRCData(ax)

    # Extract out of the config file all the usages into a dictionary.
    all_usages_size, usages = extract_usages_from_config_file(config_file)

    # Before the new config is written to the device, check that the config file
    # is compatible with the device by comparing the runtime CRC in u33. Manually
    # populate the u33 content with the content from the file so that a compatibility
    # check can be performed
    u33_from_file = u33_CRCData(ax, False)
    u33_from_file._usage_revision = usages[0x33][1]
    u33_from_file._usage_binary_data = usages[0x33][2]
    u33_from_file.init_usage()
    u33_from_file._unpack()

    # Similarly, if the config file that was specified is incompatible, the details
    # would be in u31. Capture that here, but it will only be used if the config file
    # is not compatible. This information will tell us what firmware the config came from
    u31_from_file = u31_DeviceInformation(ax)
    u31_from_file._usage_revision = usages[0x31][1]
    u31_from_file._usage_binary_data = usages[0x31][2]
    u31_from_file._unpack()

    # Compare the firmware runtime CRC from the file with the CRC from the device.
    # Only proceed if the CRCs match.
    if u33_from_file.reg_runtime_crc != u33.reg_runtime_crc:
        print("ERROR: The config file was saved from a different revision of firmware.")
        print("Firmware info from device      : 0x{0:08X}, {1}".format(u33.reg_runtime_crc,
                                                                       ax.u31.get_device_info_short()))
        print("Firmware info from config file : 0x{0:08X}, {1}".format(u33_from_file.reg_runtime_crc,
                                                                       u31_from_file.get_device_info_short()))
        return 3

    # Verify if the contents have been loaded onto the device correctly by re-reading
    # u33 from the device and comparing it with the file
    config_loaded_successfully = u33.compare_u33(u33_from_file, True)
    if not config_loaded_successfully:
        print("ERROR: The config file does not match the config on the device.")
        return 4

    return 0


if __name__ == '__main__':
    # Create argument parser
    parser = argparse.ArgumentParser(
        description='Utility to load aXiom config files onto a device',
        epilog='''
Usage examples:
    python %(prog)s -i usb -f config.th2cfgbin
    python %(prog)s -i usb -f config.th2cfgbin --load-u04
    python %(prog)s -i i2c --i2c-bus 1 --i2c-address 0x67 -f config.th2cfgbin
    python %(prog)s -i spi --spi-bus 0 --spi-device 0 -f config.th2cfgbin

Exit status codes:
    0 : Success
    2 : Script argument syntax issue. See --help
    3 : Config file not compatible with firmware on the device
    4 : Config file does not match the device's config
''',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[interface_arg_parser()])

    config_group = parser.add_argument_group('Configuration Options')
    config_group.add_argument("-f", "--file",
                              help='aXiom config file (.th2cfgbin format)',
                              metavar='CONFIG.th2cfgbin')
    config_group.add_argument("--check",
                              help='Reads u33 from the device, if a config file is specified, then the config will be '
                                   'compared against the u33 on the device',
                              action='store_true')
    config_group.add_argument("-c", "--load-u04",
                              help='Load u04 data from the config file into the device',
                              action="store_true")

    args = parser.parse_args()

    # Initialise comms with aXiom
    axiom = axiom(get_comms_from_args(parser))

    # Prime the exit code
    exit_code = 0

    if args.file is not None:
        if not os.path.isfile(args.file) or not args.file.endswith('.th2cfgbin'):
            parser.error("The config file does not exist or is not a valid config file.")

    # Load a config file if the check option is not selected
    if args.file is not None and not args.check:
        exit_code = axcfg(axiom, args.file, args.load_u04)

    # Compare the file with the device's u33
    elif args.file is not None and args.check:
        exit_code = axcfg_compare_u33(axiom, args.file)

    # Read the device's u33
    elif args.file is None and args.check:
        u33 = u33_CRCData(axiom)
        u33.print()
    else:
        parser.error('Both the --file and --check arguments were not specified.')

    # Safely close the connection to aXiom
    axiom.close()
    sys.exit(exit_code)
