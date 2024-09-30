# Copyright (c) 2024 TouchNetix
# 
# This file is part of axutils and is released under the MIT License:
# See the LICENSE file in the root directory of this project or http://opensource.org/licenses/MIT.

import sys
import time
import logging
import signal
import math
from functools import partial
from axiom_tc import axiom
from interface_arg_parser import *
from exitcodes import *

# Global Variables  ------------------------------------------------------------
keyboard_signal_interrupt_requested = False

# End of Global Variables ------------------------------------------------------


class AxiomReportLoggingFilter(logging.Filter):
    def __init__(self):
        super().__init__()

        # A list of reports that aXiom can produce. Not all reports are decoded in this script
        # When the script is run, the user will pass in an argument to specify which reports
        # they want to consume, so this will default to all reports being off. See --help
        self.reports = {0x01: False,
                        0x21: False,  # Not yet decoded
                        0x41: False,
                        0x45: False,  # Not yet decoded
                        0x46: False,  # Not yet decoded
                        0x4C: False,  # Not yet decoded
                        0x81: False,  # Not yet decoded
                        0xF3: False}  # Not yet decoded

    def filter(self, record):
        # Each log will have a "usage" attribute that will be used to compare
        # against the filter enable/disable list
        usage = getattr(record, 'usage', False)
        return self.reports[usage]

    def update_filter(self, usage, enabled):
        if usage in self.reports:
            self.reports[usage] = enabled


def custom_signal_handler(signum, frame):
    """
    Custom CTRL+C handler that will set a global flag that will allow the script
    to exit at a safe point and close the connection to the aXiom device.
    """
    global keyboard_signal_interrupt_requested
    keyboard_signal_interrupt_requested = True


def arg_hex_type(x):
    """
    Custom argparse type to allow hex values to be input as script arguments
    """
    return int(x, 16)


def decode_and_process_report(report, report_logger):
    """
    A report has been received, pass it off to the relevant decoder.
    Byte 0: bits 14-0 - Report length in words
            bit 15    - Report overflow, i.e. a previous report has been missed
    Byte 1: Usage ID, which usage generated this report
    """
    if report[1] == 0x01:
        decode_u01(report_logger, report[2:])
    elif report[1] == 0x41:
        decode_u41(report_logger, report[2:])
    elif report[1] == 0x45:
        decode_u45(report_logger, report[2:])


def decode_u41(report_logger, report):
    """
    NOTE: This code assumes the system has been configured to report pilot ID values. See pilot_id_init() for prerequisites
    """

    # Extract the timestamp from the report
    timestamp = report[52] + (report[53] << 8)

    # Find out which targets are reporting a position in this report
    target_status = (report[0]) + ((report[1] & 0x03) << 8)

    # Log Header
    report_string = "u41 {0:>5} {1:3X}  ".format(timestamp, target_status)

    # Loop over all the targets in the report and extract the X, Y and Z values.
    for t in range(0, 10):
        # X & Y, the pilot ID is also encoded in these fields
        u41_offset = (t * 4) + 2
        x = report[u41_offset + 0] + (report[u41_offset + 1] << 8)
        y = report[u41_offset + 2] + (report[u41_offset + 3] << 8)

        # Z
        u41_offset = (t * 1) + 42
        z = report[u41_offset]

        # Extract the pilot ID field out of the X and Y values and then adjust the X and Y values accordingly
        pilot_id = ((x & 0x03) |        # X contains the lowest 2 bits of the pilot ID value
                    ((y & 0x03) << 2))  # Y contains the upper 2 bits of the pilot ID value
        x = x >> 2
        y = y >> 2

        log_entry_colour_reset = "\033[0m"
        if pilot_id == 0:
            pilot_id_string = "NoID" # No ID (normal touch, non-pilot ID)
            log_entry_colour = "\033[95m"
        elif pilot_id == 15:
            pilot_id_string = "????" # Undetermined ID
            log_entry_colour = "\033[91m"
        else:
            pilot_id_string = f"ID{pilot_id:02}"
            log_entry_colour = "\033[32m"

        if target_status & (1 << t) != 0:
            report_string += "{5}(T{0}: {1:>4},{2:>4},{3}, {4:4}){6} ".format(t, x, y, z, pilot_id_string,
                                                                                  log_entry_colour,
                                                                                  log_entry_colour_reset)
        else:
            report_string += "                        "

    # Only log the report if there was something to report
    if target_status != 0:
        report_logger.info(report_string, extra={'usage': 0x41})

def decode_u45(report_logger, report):
    """
    Decode u45 Hotspots report.
    Structure of the hotspots report according to the current firmware:
      HSI   CI  QI   Re    X    X    Y    Y    Timestamp + checksum
    |    |    |    |    |    |    |    |    |    |    |    |    |  
      0    1    2    3    4    5    6    7    8    9    10   11 
    """
    PossibleReasonsEffect = ['Entered Hotspot', 'Exited Hotspot', 'Press threshold exceeded','Release threshold exceeded', 'Move', 'Entered and press threshold exceeded','Exited and release threshold exceeded']
    # Extract the timestamp and checksum from the report
    timestamp = report[8] + (report[9] << 8)
    HotspotIndex = report[0]
    ContactIndex = report[1]
    QualificationIndex = report[2]
    Reason = PossibleReasonsEffect[report[3]]
    report_string = "u45  {0:>5} HotpostIndex:  {1:>4} ContactIndex: {2:>4} QualificationIndex: {3:>4}".format(timestamp,HotspotIndex,ContactIndex,QualificationIndex)
    report_string += " " + Reason
    report_logger.info(report_string, extra={'usage': 0x45})
        
def decode_u01(report_logger, report):
    """
    Basic decoding of the u01 System manager report.
    """
    report_types = ["Hello", "Heartbeat", "Alert", "Op complete"]
    type = report[0]
    count = report[2] + (report[3] << 8)
    timestamp = report[42] + (report[43] << 8)
    report_logger.info("u01 {0:>5} {1} {2}".format(timestamp, report_types[type], count), extra={'usage': 0x01})


def gpio_interrupt(channel, comms, report_logger, u34_ta, u34_max_report_length):
    """
    For systems that support GPIO interrupts, like a RPi, this callback will be called
    when an IRQ signal from aXiom is received. It will read the u34 Report FIFO buffer
    and then process the report contents.
    """
    decode_and_process_report(comms.read_page(u34_ta, u34_max_report_length), report_logger)


def main_loop_polled(comms, report_logger, u34_ta, u34_max_report_length):
    """
    In polled mode, read u34 often to get any new reports. If no report is available,
    then the response will be discarded. This will continue indefinitely, until the
    SIGINT is signalled by the user. It will then return from here and safely
    disconnect from the device.
    """
    global keyboard_signal_interrupt_requested

    while not keyboard_signal_interrupt_requested:
        # Poll for reports (not great, but the best we can do without an
        # interrupt from nIRQ). Extract the report, and remove the first 2
        # bytes and send it onto a function to decode accordingly
        decode_and_process_report(comms.read_page(u34_ta, u34_max_report_length), report_logger)
        time.sleep(0.001)


def main_loop_interrupts(comms, report_logger, u34_ta, u34_max_report_length):
    """
    In interrupt mode, a GPIO is designated as an interrupt generator. This is configured
    for a RPi device and will require adjusting for any other system.
    Pin used for the interrupt is the GPIO/BCM pin 24, see: https://pinout.xyz/pinout/pin18_gpio24/
    When an interrupt occurs, the callback will be triggered which will read the report from
    aXiom and then the report will be processed.

    The while loop will stay here forever until the SIGINT is signaled by the user. Once SIGINT has
    been received, it will gracefully clean up the GPIO before safely disconnecting from the device.
    """
    global keyboard_signal_interrupt_requested

    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(24, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    gpio_interrupt_callback = partial(gpio_interrupt, comms=comms, report_logger=report_logger, u34_ta=u34_ta,
                                      u34_max_report_length=u34_max_report_length)
    GPIO.add_event_detect(24, GPIO.FALLING, callback=gpio_interrupt_callback, bouncetime=1)

    # The GPIO library can only trigger an interrupt on a falling or rising edge. Ideally, it would be
    # level triggered as there could be a report waiting before the interrupt was enabled and therefore
    # the falling edge was missed. Prime the system by performing a read now as that will deassert any
    # IRQ from aXiom.
    comms.read_page(u34_ta, u34_max_report_length)

    while not keyboard_signal_interrupt_requested:
        time.sleep(0.001)

    GPIO.cleanup()


def configure_report_logger(report_filter):
    """
    Create a logger with a custom filter to decide which reports will be printed on the console/logs
    """
    logger = logging.getLogger("aXiom Report Logger")
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    logger.addFilter(report_filter)
    return logger

def pilot_id_init(ax):
    # NOTE: Pilot ID feature is not officially released in any aXiom firmware yet. This is an early usage example.
    #
    # For Pilot ID to function, the system needs to be configured correctly. This method, pilot_id_init(), is intended
    # to check this. The intention is to report all the touch information and Pilot ID in a single report. There are
    # only 5 bytes available for each touch. Therefore, the 16bit X and Y fields have been converted into 14bit values.
    # The 2 spare bits in the X and Y fields can be combined to form a nibble of data. This nibble can then be decoded
    # into the Pilot ID value.
    #
    # u42 needs to be configured to enable coordinate scaling. When coordinate scaling is enabled, the spare bits are
    # available for Pilot ID. The content of the spare bits is configured in the nibble option field. With the
    # coordinates being scaled, the max X and max Y fields will determine the touch coordinates. Typically configured
    # to match the display resolution.
    u42 = ax.read_usage(0x42)

    coord_scaling = u42[2] & 0x1
    nibble_option = (u42[2] & 0xE) >> 1

    # Read the max X and max Y coordinate values (typically set to match the display resolution)
    max_x = u42[4] | (u42[5] << 8)
    max_y = u42[6] | (u42[7] << 8)

    if coord_scaling == 0 or nibble_option != 1:
        return ERROR_ARG_SYNTAX_ERROR

    print("Max Coordinate Values:")
    print(f"  X : {max_x}")
    print(f"  Y : {max_y}")

    return SUCCESS

if __name__ == '__main__':
    # Create argument parser
    parser = argparse.ArgumentParser(
        description='Utility read reports from aXiom',
        epilog='''
Usage examples:
    python %(prog)s -i usb
    python %(prog)s -i usb --reports 0x41
    python %(prog)s -i i2c --i2c-bus 1 --i2c-address 0x67
    python %(prog)s -i spi --spi-bus 0 --spi-device 0 --reports 0x01

    On RPi for interrupt driven report reads:
    python %(prog)s -i spi --spi-bus 0 --spi-device 0 --gpioint 24
    python %(prog)s -i spi --spi-bus 0 --spi-device 0 --gpioint 24 --reports 0x41

Press Ctrl+C at any time to safely exit the script.

Exit status codes:
    0 : Success
    2 : Script argument syntax issue. See --help
    3 : aXiom device is in bootloader mode
''',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[interface_arg_parser()])

    config_group = parser.add_argument_group('Configuration Options')
    config_group.add_argument("--gpioint",
                              help='RPi only. Specified the GPIO pin to use as aXiom IRQ interrupt. If not specified, '
                                   'reports will be polled',
                              required=False, action='count', default=None)
    config_group.add_argument("--reports", nargs='+', type=arg_hex_type,
                              help='List of reports to enable, e.g., --reports 0x41 0x4C', required=False,
                              default=[0x01, 0x41, 0x4C])

    args = parser.parse_args()

    comms = get_comms_from_args(parser)

    # Create a customer logging filter for the reports so that they can be individually enabled/disabled
    report_filter = AxiomReportLoggingFilter()
    report_logger = configure_report_logger(report_filter)

    # Only logs the reports that have been enabled via the script's arguments.
    for report in args.reports:
        report_filter.update_filter(report, True)

    # The main part of this code is going to sit in a while(1) loop. Pressing CTRL+C is the only way
    # to terminate the script. However, the connection to aXiom should be safely severed. Register a
    # custom SIGINT handler to set a flag that will allow the while(1) loops to exit at a convenient
    # point and close the connection.
    signal.signal(signal.SIGINT, custom_signal_handler)

    # Initialise comms with axiom 
    ax = axiom(comms)

    # Prime the exit code
    exit_code = SUCCESS

    exit_code = pilot_id_init(ax)
    if exit_code != SUCCESS:
        print("ERROR: Pilot ID is incorrectly configured. Contact TouchNetix.")
    elif ax.is_in_bootloader_mode():
        exit_code = ERROR_AXIOM_IN_BOOTLOADER
        print("INFO: aXiom device is in bootloader mode.")
    else:
        u34_ta = ax.u31.convert_usage_to_target_address(0x34)
        u34_max_report_length = ax.u31.max_report_len

        print("Press Ctrl+C at any time to safely exit the script.")

        if args.gpioint is not None:
            main_loop_interrupts(comms, report_logger, u34_ta, u34_max_report_length)
        else:
            main_loop_polled(comms, report_logger, u34_ta, u34_max_report_length)

    ax.close()
    sys.exit(exit_code)
