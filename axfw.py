# Copyright (c) 2024 TouchNetix
# 
# This file is part of [Project Name] and is released under the MIT License: 
# See the LICENSE file in the root directory of this project or http://opensource.org/licenses/MIT.

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
INVALID_PARAMETER = 1

def show_progress(current, total):
    progress = (float(current) / float(total)) * 100
    sys.stdout.write('\033[?25l') # Hide cursor
    sys.stdout.write("Progress: %3.0f%%\r" % (progress))
    sys.stdout.flush()
    sys.stdout.write('\033[?25h') # Show cursor

def get_axfw_file_crc(firmware_file):
    """
    The .axfw file contains a CRC value that is used to validate the contents of
    firmware file. This function returns the calculated .axfw file CRC.
    """
    file_size = os.path.getsize(firmware_file)
    with open(firmware_file, 'rb') as file:
        # Data to do the CRC calculation starts at byte 8 in the .axfw file
        file.seek(8)
        axfw_file = file.read((file_size - 8))
        crc = binascii.crc32(axfw_file, 0)
    return crc

def convert_device_id_to_string(device_id):
    device_channel_count =  device_id & 0x3FF
    device_variant       = (device_id & 0x7C00) >> 10
    return "AX%u%c" % (device_channel_count, chr(0x41 + device_variant))

def axfw_check_file_and_validate_parameters(axiom, firmware_file):
    """
    Validates the .axfw file before attempting a download.

    Returns:
        0 : File is valid, compatible with the device and can be loaded
        5 : .axfw file is invalid. E.g. failed signature check or CRC mismatch
        6 : The .axfw is intended for a different aXiom device
        7 : The .axfw firmware is already on the device

        firmware_crc : The CRC of the firmware in the file to be used for comparrison after the download completes
    """

    # Get some of the u31 registers are these are going to be used shortly as part
    # of the validation process.
    u31_device_id = axiom.u31.reg_device_id
    u31_fw_major  = axiom.u31.reg_fw_major
    u31_fw_minor  = axiom.u31.reg_fw_minor
    u31_fw_patch  = axiom.u31.reg_fw_patch

    with open(firmware_file, "rb") as file:
        signature, axfw_crc, axfw_format_ver = list(struct.unpack("<2IH", file.read(10)))

        # Validate the signature, file format and file CRC values before decoding the 
        # rest of the file
        if struct.pack("<I", signature).decode() != 'AXFW':
            print("ERROR: Invalid .axfw signature")
            return 5
        
        if axfw_format_ver != 0x0200:
            print("ERROR: Unknown .axfw format verion")
            return 5
        
        axfw_crc_calculated = get_axfw_file_crc(firmware_file)
        if axfw_crc != axfw_crc_calculated:
            print("ERROR: The .axfw CRC was invalid")
            return 5
        
        device_id, fw_variant, fw_ver_minor, fw_ver_major, fw_ver_patch, fw_status = list(struct.unpack("<H5B", file.read(7)))
        silicon_version, silicon_revision, fw_crc = list(struct.unpack("<HBI", file.read(7)))

        if u31_device_id != device_id:
            u31_device_str = convert_device_id_to_string(u31_device_id)
            device_id_str  = convert_device_id_to_string(device_id)
            print(f"ERROR: The .axfw file is for a different device. Device: {u31_device_str}, File: {device_id_str}")
            return 6
        
        if u31_fw_major == fw_ver_major and u31_fw_minor == fw_ver_minor and u31_fw_patch == fw_ver_patch:
            print("INFO: The firmware is already on the device")
            return 7, fw_crc
    return 0, fw_crc

# def validate_runtime_crc(axiom, firmware_file):
#     u33 = u33_CRCData(axiom)
#     u33.read()
#     runtime_nvm_crc = u33.reg_runtime_crc
#     _, axfw_header = get_axfw_header(firmware_file)
#     stored_nvm_crc_struct = axfw_header[20], axfw_header[21], axfw_header[22], axfw_header[23]
#     stored_nvm_crc_bytes = bytes(bytearray(stored_nvm_crc_struct))
#     stored_nvm_crc = int.from_bytes(stored_nvm_crc_bytes, 'little')

#     if runtime_nvm_crc != stored_nvm_crc:
#         print("Runtime CRC do not match")

# this function opens the .axfw file and performs the download starting from the end of the axfw header
def axfw_download(axiom, firmware_file):
    alc_download(axiom, firmware_file)

# this functions opens the .alc file and performs the download from the beginning of the file 
def alc_download(axiom, firmware_file):
    if firmware_file.endswith("alc"):
        firmware_start_offset = 0
    else:
        firmware_start_offset = 24

    if not axiom.enter_bootloader_mode():
        print("Error: Failed to enter bootloader mode.")
        return 4

    # Open the firmware file and parse it into chunks.
    with open(firmware_file, "rb") as file:

        # Seek to the end of the file to determine how long the file is.
        file.seek(0, os.SEEK_END)
        eof_pos = file.tell()

        # Seek back to the start of the firmware in the file
        file.seek(firmware_start_offset)

        # Iterate through the file, identifying the different chunks.
        while True:
            chunk_header = list(struct.unpack(">8B", file.read(8)))
            chunk_length = (chunk_header[6] << 8) + (chunk_header[7])
            chunk_payload = list(struct.unpack(">"+str(chunk_length)+"B", file.read(chunk_length)))

            # Send the chunk to be downloaded, the aXiom core code will further
            # segment the chunk into smaller payloads to be sent to aXiom.
            axiom.bootloader_write_chunk(chunk_header, chunk_payload)

            show_progress(file.tell(), eof_pos)

            # Check if the end of file has been reached
            if file.tell() == eof_pos:
                print("")
                break
    
    print("Rebooting aXiom device")
    axiom.bootloader_reset_axiom()
    sleep(2)
    return 0

if __name__ == '__main__':
    # Create argument parser
    parser = argparse.ArgumentParser(
        description='Utility to update aXiom firmware',
        epilog='''
Usage examples:
    python %(prog)s -i usb -f ax80a_3D_rt_r040807_prod.axfw
    python %(prog)s -i usb -f ax80a_3D_rt_r040807_prod.alc
    python %(prog)s -i i2c --i2c-bus 1 --i2c-address 0x67 -f ax80a_3D_rt_r040807_prod.axfw
    python %(prog)s -i spi --spi-bus 0 --spi-device 0 -f ax80a_3D_rt_r040807_prod.axfw
    python %(prog)s -i usb -f ax80a_3D_rt_r040807_prod.axfw --info
    python %(prog)s -i usb --info

Exit status codes:
    0 : Success
    2 : Script argument syntax issue. See --help
    3 : File is not an .axfw or .alc file
    4 : Failed to get the aXiom device to enter bootloader mode
    5 : The .axfw file was not valid
    6 : The .axfw is for a different aXiom device
    7 : The firmware is already loaded onto the aXiom device
''', formatter_class=argparse.RawDescriptionHelpFormatter)

    # Create argument groups
    interface_group = parser.add_argument_group('Interface Options')
    config_group = parser.add_argument_group('Configuration Options')

    # Add arguments to their respective groups
    interface_group.add_argument("-i", "--interface", help='Comms interface to communicate with aXiom', choices=["spi", "i2c", "usb"], required=True)
    interface_group.add_argument("--i2c-bus", help='I2C bus number, as per `/dev/i2c-<bus>`', metavar='BUS', type=int)
    interface_group.add_argument("--i2c-address", help='I2C address, either 0x66 or 0x67', choices=["0x66", "0x67"], metavar='ADDR')
    interface_group.add_argument("--spi-bus", help='SPI bus number, as per `/dev/spi<bus>.<device>`', metavar='BUS', type=int)
    interface_group.add_argument("--spi-device", help='SPI device for CS, as per `/dev/spi<bus>.<device>`', metavar='DEV', type=int)

    config_group.add_argument("-f", "--file", help='aXiom firmware file (.alc or .axfw format)', metavar='FIRMWARE_FILE')
    config_group.add_argument("--info", help='Displays the firmware information of the connected aXiom device and the firmware files (.axfw only)', action="store_true")

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

    error_code = 0

    if args.file is not None and not args.file.endswith(("axfw", "alc")):
        error_code = 3
        print("ERROR: Invalid file extension")
    elif args.file.endswith("axfw"):
        # axfw download
        error_code, fw_crc = axfw_check_file_and_validate_parameters(axiom, args.file)
        if error_code == 0 or error_code == 7:
            axfw_download(axiom, args.file)

            u33 = u33_CRCData(axiom)
            if u33.reg_runtime_nvm_crc == fw_crc:
                print("Download OK")
            else:
                print("Download failed!")
    else:
        # Must be alc download
        error_code = alc_download(axiom, args.file)


    # # Print device info
    # print("Device Info: {0}".format(axiom.u31.get_device_info_short()))

    # if args.info and args.file is None:
    #     # Nothing to do. The device info has already been shown and no file has been specified
    #     pass
    # elif args.info and args.file is not None:
    #     # Device info has already been shown, compare it to the .axfw file
    #     pass

    


    
    axiom.close()
    sys.exit(error_code)
    

    # exit_code = 0
    # #parser = argparse.ArgumentParser(description='Utility to update aXiom firmware')
    # #parser.add_argument("-f", help='aXiom firmware file (.alc or .axfw format)', metavar='FIRMWARE_FILE', required=False, type=str, default='')
    # #parser.add_argument("-i", help='Comms interface to communicate with aXiom', choices=["spi", "i2c", "usb"], required=True, type=str)
    # parser.add_argument("-v", help='Print verbose messages', action="store_true")
    # #parser.add_argument("--spi-bus", help='SPI bus number, as per `/dev/spi<bus>.<device>`', metavar='BUS', required=False, type=int)
    # #parser.add_argument("--spi-device", help='SPI device for CS, as per `/dev/spi<bus>.<device>`', metavar='DEV', required=False, type=int)
    # #parser.add_argument("--i2c-bus", help='I2C bus number, as per `/dev/i2c-<bus>`', metavar='BUS', required=False, type=int)
    # #parser.add_argument("--i2c-address", help='I2C address, either 0x66 or 0x67', choices=["0x66", "0x67"], metavar='ADDR', required=False, type=str)
    # parser.add_argument("-force", help='Force the firmware to download even if there is a metadata warning, .axfw file only.', action="store_true", required=False)
    # #parser.add_argument("-info", help='Print information about the connected device and the firmware file provided, .axfw file only.', action="store_true", required=False)
    # args = parser.parse_args()

    # verbose = args.v
    # force_download = args.force
    # print_device_and_axfw_information = args.info

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
    # elif firmware_file.endswith(".alc"):
    #     alc_download(firmware_file)
    # else:
    #     print("Invalid firmware filetype")
    #     sys.exit(-1)

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

    # The firmware CRC can be validated if a axfw file was used.
    if firmware_file.endswith(".axfw"):
        validate_runtime_crc(axiom, firmware_file)

    # Safely close the connection to aXiom
    axiom.close()
    sys.exit(exit_code)
