# Copyright (c) 2024 TouchNetix
# 
# This file is part of axutils and is released under the MIT License:
# See the LICENSE file in the root directory of this project or http://opensource.org/licenses/MIT.

import sys
import time
import logging
import signal
from functools import partial
from axiom_tc import axiom
from interface_arg_parser import *
from exitcodes import *

keyboard_signal_interrupt_requested = False


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


def char_reverse(b):
    """
    reverse the 8 bits of the char "b"
    """
    b = (b & 0xF0) >> 4 | (b & 0x0F) << 4;
    b = (b & 0xCC) >> 2 | (b & 0x33) << 2;
    b = (b & 0xAA) >> 1 | (b & 0x55) << 1;
    return b;

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
    Decode u41 2DCTS report. This decode assumes all targets are either touch, press, hover,
    proximity or center of mass. Dials are not being handled. u42 could be read to determine
    what data is present in each target slot and decoded accordingly.
    """
    # Find out which targets are reporting a position in this report
    target_status = (report[0]) + ((report[1] & 0x03) << 8)

    # Other status information from the report, see docs for details
    extra_info = (report[1] & 0xFC) >> 2

    # Extract the timestamp and checksum from the report
    timestamp = report[52] + (report[53] << 8)
    checksum = report[54] + (report[55] << 8)

    #print("u41",report[52],report[53])
    report_string = "u41 {0:>5} {1:>3X} {2:>2X}  ".format(timestamp, target_status, extra_info)

    # Loop over all the targets in the report and extract the X, Y and Z values.
    for t in range(0, 10):
        # X & Y
        offset = (t * 4) + 2
        x = report[offset + 0] + (report[offset + 1] << 8)
        y = report[offset + 2] + (report[offset + 3] << 8)

        # Z
        offset = (t * 1) + 42
        z = report[offset]

        if target_status & (1 << t) != 0:
            report_string += "(T{0}: {1:>5},{2:>5},{3:>4}) ".format(t, x, y, z)
        elif target_status != 0:
            report_string += "                       "

    # Only log the report if there was something to report
    if target_status != 0 or extra_info != 0:
        report_logger.info(report_string, extra={'usage': 0x41})

def decode_u45(report_logger, report):
    """
    Decode u45 Hotspots report.
    Structure of the hotspots report according to the firmware:
        --Contact or CoM #i
            HotspotIndex            8 bits
            ValidSubreport          1 bit
            Reserved                7 bits
            ------------
            QualificationIndex      8 bits
            Reason                  8 bits
            -------------
            X                      16 bits 
            -------------
            Y                      16 bits
            -------------

    """
    ForceOnly = True   #For only Force chip, we expect 4 CoMs. For any other variant, we expect Contact and CoM
    PossibleReasonsEffect = ['Entered Hotspot', 'Exited Hotspot', 'Press threshold exceeded','Release threshold exceeded', 'Move', 'Entered and press threshold exceeded','Exited and release threshold exceeded']

    if ForceOnly:
        # Extract the timestamp from the report
        timestamp = report[32] + (report[33] << 8)
        report_string = "u45 {0:>5} ".format(timestamp)
        CoMValidReport = list([0,0,0,0])
        
        offset = 0
        for CoM in range(4):
            ValidReport = report[offset+1]
            if ValidReport == 1:
                CoMHotpostIndex = report[offset+0]
                CoMIndex = CoM
                CoMQualificationIndex = report[offset+2]
                CoMReason =PossibleReasonsEffect[report[offset+3]]
                
                CoMX = report[offset+4] + (report[offset+5] << 8)
                CoMY = report[offset+6] + (report[offset+7] << 8)
                report_string += "HotpostIndex:  {0:>4} CoM Index: {1:>4}  QualificationIndex: {2:>4}  X: {3:>6}   Y: {4:>6}".format(CoMHotpostIndex, CoMIndex,CoMQualificationIndex, CoMX,CoMY)
                report_string += " " + CoMReason + " "
                CoMValidReport[CoM] = 1
            offset+=8
        if any(CoMValidReport):
            report_logger.info(report_string, extra={'usage': 0x45})
    else:
        # Extract the timestamp from the report
        timestamp = report[18] + (report[19] << 8)
        ContactValidReport = report[1] 
        if ContactValidReport ==1:
            ContactHotpostIndex = report[0]
            ContactIndex = 0
            ContactQualificationIndex = report[2]
            ContactReason =PossibleReasonsEffect[report[3]]
            
            ContactX = report[4] + (report[5] << 8)
            ContactY = report[6] + (report[7] << 8)
            
        
        CoMValidReport = report[9]
        if CoMValidReport ==1:
            CoMHotpostIndex = report[8]
            CoMIndex = 0
            CoMQualificationIndex = report[10]
            CoMReason =PossibleReasonsEffect[report[11]]
            
            CoMX = report[12] + (report[13] << 8)
            CoMY = report[14] + (report[15] << 8)
        if ContactValidReport==1:
            report_string = "u45  {0:>5} HotpostIndex(Contact):  {1:>4} Contact Index: {2:>4}  QualificationIndex(Contact): {3:>4}  X(Contact): {4:>6}   Y(Contact): {5:>6}".format(timestamp,ContactHotpostIndex,ContactIndex,ContactQualificationIndex, ContactX,ContactY)
            report_string += " " + ContactReason + " "
            if CoMValidReport==1:
                report_string = "HotpostIndex(CoM):  {0:>4} CoM Index: {1:>4}  QualificationIndex(CoM): {2:>4}  X(CoM): {3:>6}   Y(CoM): {4:>6}".format(ContactHotpostIndex,ContactIndex,ContactQualificationIndex, CoMX,CoMY)
                report_string += " " + CoMReason
            report_logger.info(report_string, extra={'usage': 0x45})

        elif CoMValidReport==1:
            report_string = "u45  {0:>5} HotpostIndex(CoM):  {1:>4} CoM Index: {2:>4}  QualificationIndex(CoM): {3:>4}  X(CoM): {4:>6}   Y(CoM): {5:>6}".format(timestamp,CoMHotpostIndex,CoMIndex,CoMQualificationIndex, CoMX,CoMY)
            report_string += " " + CoMReason 
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
                              help='List of reports to enable, e.g., --reports 0x41 0x81 0x46', required=False,
                              default=[0x01, 0x41])

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

    if ax.is_in_bootloader_mode():
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
