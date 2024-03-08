# Copyright (c) 2024 TouchNetix
# 
# This file is part of axutils and is released under the MIT License:
# See the LICENSE file in the root directory of this project or http://opensource.org/licenses/MIT.

import os
import sys
import struct
import binascii
from time import sleep
from axiom_tc import axiom
from axiom_tc import u33_CRCData
from interface_arg_parser import *


def show_progress(current, total):
    progress = (float(current) / float(total)) * 100
    sys.stdout.write('\033[?25l')  # Hide cursor
    sys.stdout.write("Progress: %3.0f%%\r" % progress)
    sys.stdout.flush()
    sys.stdout.write('\033[?25h')  # Show cursor


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


def axfw_get_fw_info_from_file(firmware_file):
    """
    Extracts the firmware information from the .axfw file and provides some basic
    validation of the header.

    Returns:
        5 : .axfw file is invalid. E.g. failed signature check or CRC mismatch
        0, device_id, fw_variant, fw_ver_major, fw_ver_minor, fw_ver_patch, fw_status, fw_crc
    """
    with open(firmware_file, "rb") as file:
        signature, axfw_crc, axfw_format_ver = list(struct.unpack("<2IH", file.read(10)))

        # Validate the signature, file format and file CRC values before decoding the 
        # rest of the file
        if struct.pack("<I", signature).decode() != 'AXFW':
            print("ERROR: Invalid .axfw signature")
            return 5

        if axfw_format_ver != 0x0200:
            print("ERROR: Unknown .axfw format version")
            return 5

        axfw_crc_calculated = get_axfw_file_crc(firmware_file)
        if axfw_crc != axfw_crc_calculated:
            print("ERROR: The .axfw CRC was invalid")
            return 5

        device_id, fw_variant, fw_ver_minor, fw_ver_major, fw_ver_patch, fw_status = list(
            struct.unpack("<H5B", file.read(7)))
        _, _, fw_crc = list(struct.unpack("<HBI", file.read(7)))

    return 0, device_id, fw_variant, fw_ver_major, fw_ver_minor, fw_ver_patch, fw_status, fw_crc


def axfw_check_file_and_validate_parameters(ax, firmware_file):
    """
    Validates the .axfw file before attempting a download.

    Returns:
        0 : File is valid, compatible with the device and can be loaded
        5 : .axfw file is invalid. E.g. failed signature check or CRC mismatch
        6 : The .axfw is intended for a different aXiom device
        7 : The .axfw firmware is already on the device
        8 : The firmware variant in the .axfw does not match the device's firmware variant

        firmware_crc : The CRC of the firmware in the file to be used for comparison after the download completes
    """

    # Get some of the u31 registers are these are going to be used shortly as part
    # of the validation process.
    u31_device_id = ax.u31.reg_device_id
    u31_fw_major = ax.u31.reg_fw_major
    u31_fw_minor = ax.u31.reg_fw_minor
    u31_fw_patch = ax.u31.reg_fw_patch
    u31_fw_variant = ax.u31.reg_fw_variant
    u31_fw_status = ax.u31.reg_fw_status

    # Get the firmware information from the .axfw file
    (return_code, file_device_id, file_fw_variant,
     file_fw_ver_major, file_fw_ver_minor, file_fw_ver_patch,
     file_fw_status, file_fw_crc) = axfw_get_fw_info_from_file(firmware_file)

    # If the .axfw file is not valid, exit now
    if return_code != 0:
        return return_code, None

    # Compare the device ID from the device and the .axfw file. This returns a different
    # code as this is not something that the --force option can overcome.
    if u31_device_id != file_device_id:
        u31_device_str = ax.u31.convert_device_id_to_string(u31_device_id)
        device_id_str = ax.u31.convert_device_id_to_string(file_device_id)
        print(f"ERROR: The .axfw file is for a different device. Device: {u31_device_str}, File: {device_id_str}")
        return 6, None

    if u31_fw_variant != file_fw_variant:
        return 8, file_fw_crc

    # Compare the firmware information to prevent any unnecessary downloads. The --force
    # option can override this and still perform the download
    if (u31_fw_major == file_fw_ver_major and
            u31_fw_minor == file_fw_ver_minor and
            u31_fw_patch == file_fw_ver_patch and
            u31_fw_status == file_fw_status):
        return 7, file_fw_crc

    # File is OK and valid to be loaded onto the aXiom device
    return 0, file_fw_crc


def axfw_download(ax, firmware_file):
    """
    .axfw file downloads are pretty much exactly the same as the .alc downloads. The .axfw
    files have additional header information that can be used to identify the contents of
    a file and prevent any unnecessary downloads. Essentially, within each .axfw is an
    .alc file.
    """
    return alc_download(ax, firmware_file)


# this functions opens the .alc file and performs the download from the beginning of the file
def alc_download(ax, firmware_file):
    """
    Download the file onto the device. If the firmware file is an .alc file, the firmware is
    at the start of the file. If the firmware file is an .axfw, skip past the header bytes.
    If an .axfw file is specified, it is assumed that all the validation and verification
    checks have already been done (see axfw_check_file_and_validate_parameters()).
    """
    if firmware_file.endswith("alc"):
        firmware_start_offset = 0
    else:
        firmware_start_offset = 24

    # Before the download can start, the aXiom device needs to be in bootloader mode
    if not ax.enter_bootloader_mode():
        print("Error: Failed to enter bootloader mode.")
        return 4

    file_size = os.path.getsize(firmware_file)
    with open(firmware_file, "rb") as file:
        # Seek to the position in the file where the firmware starts
        file.seek(firmware_start_offset)

        while True:
            # Extract all the "chunks" from the firmware file
            chunk_header = list(struct.unpack(">8B", file.read(8)))
            chunk_length = (chunk_header[6] << 8) + (chunk_header[7])
            chunk_payload = list(struct.unpack(">" + str(chunk_length) + "B", file.read(chunk_length)))

            # Send the chunk to be downloaded, the aXiom core code will further
            # segment the chunk into smaller payloads to be sent to aXiom.
            ax.bootloader_write_chunk(chunk_header, chunk_payload)

            show_progress(file.tell(), file_size)

            # Has all the firmware chunks been sent the device?
            if file.tell() == file_size:
                break

    print("")

    # Reset the aXiom bootloader so that the new firmware is active.
    ax.bootloader_reset_axiom()
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
    python %(prog)s -i usb -f ax80a_3D_rt_r040807_prod.axfw --force
    python %(prog)s -i usb --info

Exit status codes:
    0 : Success
    2 : Script argument syntax issue. See --help
    3 : File is not an .axfw or .alc file, or no file specified
    4 : Failed to get the aXiom device to enter bootloader mode
    5 : The .axfw file was not valid
    6 : The .axfw is for a different aXiom device
    7 : The firmware is already loaded onto the aXiom device
    8 : The .axfw firmware variant is different from the firmware on the aXiom device
    9 : The firmware CRC check failed after the download was completed
''',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[interface_arg_parser()])

    config_group = parser.add_argument_group('Configuration Options')
    config_group.add_argument("-f", "--file",
                              help='aXiom firmware file (.alc or .axfw format)',
                              metavar='FIRMWARE_FILE')
    config_group.add_argument("--info",
                              help='Displays the firmware information of the connected aXiom device and the firmware '
                                   'files (.axfw only)',
                              action="store_true")
    config_group.add_argument("--force",
                              help='Enforces firmware re-download regardless of current version (.axfw only)',
                              action="store_true")

    args = parser.parse_args()

    # Initialise comms with aXiom
    axiom = axiom(get_comms_from_args(parser))

    exit_code = 0

    # Always show the firmware version of the device
    print("Device FW Info : {0}".format(axiom.u31.get_device_info_short()))

    # If the --info option is specified, no download will occur. It will show the
    # version information of the attached device. If an .axfw file is also specified,
    # then show the contents of the firmware file. The same cannot be done with .alc
    # files.
    if args.info:
        if args.file is None:
            pass  # Nothing to do
        elif args.file is not None and not args.file.endswith(("axfw", "alc")):
            print("ERROR: Unknown filetype")
            exit_code = 3
        elif args.file.endswith("axfw"):
            exit_code, device_id, fw_variant, fw_ver_major, fw_ver_minor, fw_ver_patch, fw_status, _ = (
                axfw_get_fw_info_from_file(args.file))

            if exit_code == 0:
                print("File FW Info   : {0}".format(
                    axiom.u31.convert_device_info_to_string(device_id, fw_variant, fw_ver_major, fw_ver_minor,
                                                            fw_ver_patch, fw_status)))
            else:
                print("ERROR: Unknown .axfw file")
        else:
            print("INFO: Cannot compare an .alc file")
            exit_code = 0
    else:
        if args.file is None:
            exit_code = 3
            print("ERROR: No firmware file specified")
        elif args.file is not None and not args.file.endswith(("axfw", "alc")):
            exit_code = 3
            print("ERROR: Invalid file extension")
        elif args.file.endswith("axfw"):
            exit_code, fw_crc = axfw_check_file_and_validate_parameters(axiom, args.file)
            if exit_code == 0 or (exit_code in [7, 8] and args.force):
                exit_code = axfw_download(axiom, args.file)
                if exit_code == 0:
                    axiom.u31.build_usage_table()
                    print("Device FW Info : {0}".format(axiom.u31.get_device_info_short()))
                    u33 = u33_CRCData(axiom)
                    if u33.reg_runtime_nvm_crc != fw_crc:
                        print(
                            f"ERROR: Firmware CRC check failed. Device: 0x{u33.reg_runtime_nvm_crc:08X}, "
                            f"File: 0x{fw_crc:08X}")
                        exit_code = 9
            elif exit_code == 5:
                print("ERROR: Unknown .axfw file")
            elif exit_code == 7:
                print("INFO: Skipping download, the same firmware is already on the device")
            elif exit_code == 8:
                print("INFO: Skipping download, the firmware variant in the .axfw does not match the device")
        else:
            # Must be alc download
            exit_code = alc_download(axiom, args.file)
            if exit_code == 0:
                axiom.u31.build_usage_table()
                print("Device FW Info : {0}".format(axiom.u31.get_device_info_short()))

    # Safely close the connection to aXiom and set the exit code
    axiom.close()
    sys.exit(exit_code)
