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

import os
import sys
import struct
import argparse
import binascii
from time import sleep
from axiom_tc import axiom
from axiom_tc import u33_CRCData

# status codes
STATUS_SUCCESS = 0
INVALID_PARAMETER = -1

def axiom_init(args, verbose=False):
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
        comms = USB_Comms(verbose)

    return axiom(comms, verbose=verbose)

# this function retrieves the header information (first 16 bytes) 
# returns a status code indicating whether retrieving the header was a success or not
# returns the header information
def get_axfw_header(firmware_file):

    status = STATUS_SUCCESS
    if not firmware_file.endswith(".axfw"):
        print("Invalid file type provided")
        status = INVALID_PARAMETER

    if status == STATUS_SUCCESS:
        with open(firmware_file, "rb") as file:
            file.seek(0)
            axfw_header = list(struct.unpack(">24B", file.read(24)))
            status = STATUS_SUCCESS
    else:
        axfw_header = INVALID_PARAMETER
        status = INVALID_PARAMETER

    return status, axfw_header
        
# this function prints out the information about the device the .axfw file was generated for
# returns the status code from the get header function indicating whether or not the header is valid
def print_axfw_header_info(firmware_file):

    status, axfw_header = get_axfw_header(firmware_file)
    if status == STATUS_SUCCESS:
        device_id = axfw_header[10] + axfw_header[11]
        build_variant_int = axfw_header[12]
        fw_version_major = axfw_header[14]
        fw_version_minor = axfw_header[13]
        patch_number = axfw_header[15]
        silicon_id_minor = axfw_header[17]
        silicon_revision = axfw_header[19]

        print("  Device ID   : AX%u%c " % (device_id, chr(0x41 + build_variant_int)))
        print("  FW Revision : %d.%d.%d" % ( fw_version_major, fw_version_minor, patch_number))
        print("  Silicon     : 0x%04X (Rev %c)" % (silicon_id_minor, chr(0x41 + silicon_revision)))
        print("")

    else:
        print("Unable to retrieve .axfw file header information")

    return status

# this function checks the header information and ensures that the contents of the header are valid
# returns a status code which indicates if the information inside the header file is correct
def axfw_check_file_and_validate_parameters(device_info, firmware_file):

    status = STATUS_SUCCESS

    get_header_status, axfw_header = get_axfw_header(firmware_file)
    if get_header_status == STATUS_SUCCESS:
        signature = chr(axfw_header[0]) + chr(axfw_header[1]) + chr(axfw_header[2]) + chr(axfw_header[3])
        axfw_crc_struct = [axfw_header[4], axfw_header[5], axfw_header[6], axfw_header[7]]
        axfw_crc_bytes = bytes(bytearray(axfw_crc_struct))
        axfw_crc = int.from_bytes(axfw_crc_bytes, 'little')
        file_format_version_minor = axfw_header[8]
        file_format_version_major = axfw_header[9]
        new_device_id = axfw_header[10] + axfw_header[11]
        new_fw_version_major = axfw_header[14]
        new_fw_version_minor = axfw_header[13]
        new_patch_number = axfw_header[15]

        if signature != "AXFW":
            print("Invalid device signature")
            status = INVALID_PARAMETER

        if (file_format_version_minor != 0) and (file_format_version_major != 2):
            print("Unsupported axfw file version, expected v2.00 but got v%d.%02d" % (file_format_version_major, file_format_version_minor))
            status = INVALID_PARAMETER

        original_device_id            = ((device_info[1] & 0x7f) << 8) + device_info[0]
        original_device_channel_count = original_device_id & 0x3FF

        original_fw_ver_major = int(device_info[3])
        original_fw_ver_minor = int(device_info[2])
        original_fw_ver_rc    = (device_info[11] & 0xf0) >> 4

        with open(firmware_file, 'rb') as temp_file_handle:
            # seed of the crc is 0
            crc32_value = 0
            file_size = os.path.getsize(firmware_file)
            temp_file_handle.seek(8) # skip over the first 8 bytes as this contains the file signature which is not part of the crc, and the crc itself
            axfw_file = temp_file_handle.read((file_size - 8))
            calculated_axfw_crc = binascii.crc32(axfw_file, crc32_value)

        if axfw_crc != calculated_axfw_crc:
            status = INVALID_PARAMETER
            print("CRCs do not match")

        if original_device_channel_count != new_device_id:
            print("Device ID mismatch")
            if force_download != True:
                status = INVALID_PARAMETER
        if(new_fw_version_major == original_fw_ver_major) and (new_fw_version_minor == original_fw_ver_minor) and (new_patch_number == original_fw_ver_rc):
            print("Device Firmware Version already on Device")
            if(force_download != True):
                status = INVALID_PARAMETER
    else:
        status = INVALID_PARAMETER
        print("Unable to check .axfw header and validate parameters")
    return status

def validate_runtime_crc(axiom, firmware_file):
    u33 = u33_CRCData(axiom)
    u33.read()
    runtime_nvm_crc = u33.reg_runtime_crc
    _, axfw_header = get_axfw_header(firmware_file)
    stored_nvm_crc_struct = axfw_header[20], axfw_header[21], axfw_header[22], axfw_header[23]
    stored_nvm_crc_bytes = bytes(bytearray(stored_nvm_crc_struct))
    stored_nvm_crc = int.from_bytes(stored_nvm_crc_bytes, 'little')

    if runtime_nvm_crc != stored_nvm_crc:
        print("Runtime CRC do not match")

# this function opens the .axfw file and performs the download starting from the end of the axfw header
def axfw_download(axiom, firmware_file):
    # Open the firmware file and parse it into chunks.
    with open(firmware_file, "rb") as file:

        # Seek to the end of the file to determine how long the file is.
        file.seek(0, os.SEEK_END)
        eof_pos = file.tell()

        # header is 24 bytes long, start of actual firmware is at byte no. 24
        file.seek(24)

        # Iterate through the file, identifying the different chunks.
        while True:
            chunk_header = list(struct.unpack(">8B", file.read(8)))
            chunk_length = (chunk_header[6] << 8) + (chunk_header[7])
            if verbose: 
                print("chunk_length is %d bytes" % chunk_length)
            chunk_payload = list(struct.unpack(">"+str(chunk_length)+"B", file.read(chunk_length)))

            # Send the chunk to be downloaded, the aXiom core code will further
            # segment the chunk into smaller payloads to be sent to aXiom.
            axiom.bootloader_write_chunk(chunk_header, chunk_payload)

            # Report current progress of the donwload
            progress = (float(file.tell()) / float(eof_pos)) * 100
            if not verbose:
                sys.stdout.write("Progress: %3.0f%%\r" % (progress))
                sys.stdout.flush()
            # Check if the end of file has been reached
            if file.tell() == eof_pos:
                print("")
                break

# this functions opens the .alc file and performs the download from the beginning of the file 
def alc_download(firmware_file):
    # Open the firmware file and parse it into chunks.
    with open(firmware_file, "rb") as file:

        # Seek to the end of the file to determine how long the file is.
        file.seek(0, os.SEEK_END)
        eof_pos = file.tell()

        # Return back to the start of the file
        file.seek(0)

        # Iterate through the file, identifying the different chunks.
        while True:
            chunk_header = list(struct.unpack(">8B", file.read(8)))
            chunk_length = (chunk_header[6] << 8) + (chunk_header[7])
            if verbose: 
                print("chunk_length is %d bytes" % chunk_length)
            chunk_payload = list(struct.unpack(">"+str(chunk_length)+"B", file.read(chunk_length)))

            # Send the chunk to be downloaded, the aXiom core code will further
            # segment the chunk into smaller payloads to be sent to aXiom.
            axiom.bootloader_write_chunk(chunk_header, chunk_payload)

            # Report current progress of the donwload
            progress = (float(file.tell()) / float(eof_pos)) * 100
            if not verbose:
                sys.stdout.write("Progress: %3.0f%%\r" % (progress))
                sys.stdout.flush()
            # Check if the end of file has been reached
            if file.tell() == eof_pos:
                print("")
                break

if __name__ == '__main__':
    exit_code = 0
    parser = argparse.ArgumentParser(description='Utility to update aXiom firmware')
    parser.add_argument("-f", help='aXiom firmware file (.alc or .axfw format)', metavar='FIRMWARE_FILE', required=False, type=str, default='')
    parser.add_argument("-i", help='Comms interface to communicate with aXiom', choices=["spi", "i2c", "usb"], required=True, type=str)
    parser.add_argument("-v", help='Print verbose messages', action="store_true")
    parser.add_argument("--spi-bus", help='SPI bus number, as per `/dev/spi<bus>.<device>`', metavar='BUS', required=False, type=int)
    parser.add_argument("--spi-device", help='SPI device for CS, as per `/dev/spi<bus>.<device>`', metavar='DEV', required=False, type=int)
    parser.add_argument("--i2c-bus", help='I2C bus number, as per `/dev/i2c-<bus>`', metavar='BUS', required=False, type=int)
    parser.add_argument("--i2c-address", help='I2C address, either 0x66 or 0x67', choices=["0x66", "0x67"], metavar='ADDR', required=False, type=str)
    parser.add_argument("-force", help='Force the firmware to download even if there is a metadata warning, .axfw file only.', action="store_true", required=False)
    parser.add_argument("-info", help='Print information about the connected device and the firmware file provided, .axfw file only.', action="store_true", required=False)
    args = parser.parse_args()

    verbose = args.v
    force_download = args.force
    print_device_and_axfw_information = args.info

    # Get the firmware file path from the arguments
    firmware_file = args.f
    if firmware_file.endswith(".axfw"):
        file_type = "axfw"
    elif firmware_file.endswith(".alc"):
        file_type = "alc"
    else:
        print("ERROR: wrong file type, expecting .axfw or .alc")
        sys.exit(-1)
        
    axiom = axiom_init(args, verbose)

    # print device and .axfw information before starting any of the firmware download process
    if print_device_and_axfw_information == True and file_type == "axfw":
        print("Device Information")
        axiom.print_device_info()
        print("File Information")
        status = print_axfw_header_info(firmware_file)
        sys.exit(status)

    try:
        print("Device info before download:")
        axiom.print_device_info()
        u31_device_information = axiom.get_u31_device_info()
    except:
        print("WARNING: not able to print tables, trying to get into bootloader mode...")

    if len(firmware_file) != 0:
        # Instruct aXiom to enter bootloader mode
        status = axiom.enter_bootloader_mode()
        if status == False:
            print("Error: Failed to enter bootloader mode.")
            sys.exit(-1)

    #perform firmware download for the filetype provided
    if firmware_file.endswith(".axfw"):
        file_valid = axfw_check_file_and_validate_parameters(u31_device_information, firmware_file)
        if file_valid == STATUS_SUCCESS:
            axfw_download(axiom, firmware_file)
    elif firmware_file.endswith(".alc"):
        alc_download(firmware_file)
    else:
        print("Invalid firmware filetype")
        sys.exit(-1)

    # Issue a reset to aXiom so that the new code will run. It is surrounded by
    # a "try" as the low level comms may get upset as aXiom instantly the command
    # is received. Fail gracefully.
    try:
        print("about to reset aXiom...")
        axiom.bootloader_reset_axiom()
        print("aXiom reset requested...")
    except:
        print("Warning: ignoring axiom reset request exception...")
        pass

    sleep(2)

    print("")
    print("Device info after download:")
    axiom.print_device_info()
    validate_runtime_crc(axiom, firmware_file)

    # Safely close the connection to aXiom
    axiom.close()
    sys.exit(exit_code)
