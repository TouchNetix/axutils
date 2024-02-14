#!/usr/bin/env python3
################################################################################
#                                    NOTICE
#
# Copyright (c) 2010 - 2023 TouchNetix Limited
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

import os
import sys
import struct
import argparse
from time import sleep
from axiom_tc import axiom
from axiom_tc import u31_DeviceInformation
from axiom_tc import u33_CRCData

def init_axiom_comms(interface):
    # Import the requested comms layer
    if interface == "i2c":
        if args.i2c_bus == None or args.i2c_address == None:
            print("The I2C bus and the I2C address arguments need to be specified.")
            parser.print_help()
            sys.exit(-1)
        else:
            from axiom_tc.I2C_Comms import I2C_Comms
            comms = I2C_Comms(args.i2c_bus, int(args.i2c_address, 16))

    elif interface == "spi":
        if args.spi_bus == None or args.spi_device == None:
            print("The SPI bus and the SPI device arguments need to be specified.")
            parser.print_help()
            sys.exit(-1)
        else:
            from axiom_tc.SPI_Comms import SPI_Comms
            comms = SPI_Comms(args.spi_bus, args.spi_device)

    elif interface == "usb":
            from axiom_tc.USB_Comms import USB_Comms
            comms = USB_Comms()

    else:
        raise Exception("Unsupported comms interface")

    # When instantiating the aXiom object, pass in the comms object which will
    # provide access to the low level reads and write methods.
    return axiom(comms)

def extract_usages_from_config_file(config_file):
    cfg_file_size = 0
    usages = {}

    try:
        with open(config_file, "rb") as file:
            cfg_file_size = os.path.getsize(config_file)

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
                    usage, revision, _, length = struct.unpack("<BBBH", file.read(5))
                    usage_content = list(struct.unpack("<"+str(length)+"B", file.read(length)))

                    # Store the contents into the usages list
                    usages[usage] = (usage, revision, usage_content)

                    # Check if the end of file has been reached
                    if file.tell() == cfg_file_size:
                        break
    except FileNotFoundError:
        print("Config file not found: " + config_file)
    except IOError:
        print("An error occurred while accessing the config file")

    return cfg_file_size, usages

if __name__ == '__main__':
    exit_code = 0

    parser = argparse.ArgumentParser(description='Utility to load aXiom config files onto a device')
    parser.add_argument("-f", help='aXiom config file (.bin format)', metavar='CONFIG_FILE', required=False, type=str, default='')
    parser.add_argument("-i", help='comms interface to communicate with aXiom', choices=["spi", "i2c", "usb"], required=True, type=str)
    parser.add_argument("-c", help='Load u04 data from the config file into the device', action="store_true")
    parser.add_argument("--i2c-bus", help='I2C bus number, as per `/dev/i2c-<bus>`', metavar='BUS', required=False, type=int)
    parser.add_argument("--i2c-address", help='I2C address, either 0x66 or 0x67', choices=["0x66", "0x67"], metavar='ADDR', required=False, type=str)
    parser.add_argument("--spi-bus", help='SPI bus number, as per `/dev/spi<bus>.<device>`', metavar='BUS', required=False, type=int)
    parser.add_argument("--spi-device", help='SPI device for CS, as per `/dev/spi<bus>.<device>`', metavar='DEV', required=False, type=int)
    args = parser.parse_args()

    # Get the config file path from the arguments
    config_file = args.f
    overwrite_u04 = args.c

    # Initialise comms with axiom 
    ax = init_axiom_comms(args.i)

    # Before we start, show the connected device's info
    ax.u31.print_device_info()
    
    # Read u33 from the device to validate the config file is compatible later
    u33 = u33_CRCData(ax)

    # Extract out of the config file all the usages into a dictionary.
    cfg_file_size, usages = extract_usages_from_config_file(config_file)
    
    # Before the new config is written to the device, check that the config file
    # is compatible with the device by comparing the runtime CRC in u33. Manually
    # populate the u33 content with the content from the file so that a compatibilty
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
        print("")
        print("ERROR: Cannot load config file as it was saved from a different revision of firmware.")
        print("       Firmware info from device      : 0x{0:08X}, {1}".format(u33.reg_runtime_crc, ax.u31.get_device_info_short()))
        print("       Firmware info from config file : 0x{0:08X}, {1}".format(u33_from_file.reg_runtime_crc, u31_from_file.get_device_info_short()))
        sys.exit(-1)

    # Stop axiom from performing measurements whilst loading the config file
    ax.u02.send_command(ax.u02.CMD_STOP)

    # Write the config to the device by iterating over all the usages from the config file
    bytes_written = 0
    for usage in usages:
        usage_rev     = usages[usage][1]
        usage_content = usages[usage][2]

        # u04 contains customer populated data, such as serial numbers, part numbers
        # serial numbers, etc. Therefore it is assumed that the customer would want 
        # to keep the data they have input unless otherwise specified (-c option).
        if usage != 0x04 or (usage == 0x04 and overwrite_u04):
            ax.config_write_usage_to_device(usage, usage_content)

        bytes_written += len(usage_content)
        progress = (float(bytes_written) / float(cfg_file_size)) * 100
        sys.stdout.write('\033[?25l') # Hide cursor
        sys.stdout.write("Progress: %3.0f%%\r" % (progress))
        sys.stdout.flush()
        sys.stdout.write('\033[?25h') # Show cursor

    # The CDUs will already have had their contents stored to NVM, but the main
    # usages are still only in RAM. Issusing this command to commit them to
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
    if config_loaded_successfully == False:
        print("ERROR: Failed to load config file")
        exit_code = -1

    # Safely close the connection to aXiom
    ax.close()
    sys.exit(exit_code)
