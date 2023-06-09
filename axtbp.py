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
import argparse
from axiom_tc.USB_Comms import USB_Comms

BridgeMode_TBPBasic = 0
BridgeMode_TBPDigitizer = 1
BridgeMode_TBPAbsoluteMouse = 2

TBP_MODES = {
    'tbp'   : BridgeMode_TBPBasic,
    'digi'  : BridgeMode_TBPDigitizer,
    'mouse' : BridgeMode_TBPAbsoluteMouse
}

TBP_MODE_PID = dict(zip(USB_Comms.PRODUCT_ID, TBP_MODES.keys()))

description_string = 'Utility to change the operating mode of a TNx USB Protocol Bridge.\nIf no argument given program prints the current mode.'
help_string = 'mode to set the Protocol Bridge into.'

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description=description_string)
    parser.add_argument("-m", help=help_string, choices=TBP_MODES.keys(), \
                        required=False, default='', type=str)
    parser.add_argument("-v", help='Print verbose messages', action="store_true")
    args = parser.parse_args()
    verbose = args.v

    comms = USB_Comms(verbose)
    print("Current TNx USB Bridge mode: " + TBP_MODE_PID[comms.pid])
    current_mode = TBP_MODES[TBP_MODE_PID[comms.pid]]

    try:
        requested_mode = TBP_MODES[args.m]
        if (requested_mode != current_mode):
            OutBuffer = list(USB_Comms.EMPTY_PKT)
            if requested_mode == BridgeMode_TBPBasic:
                OutBuffer[0] = 0x0
                OutBuffer[1] = 0xFA
                OutBuffer[2] = 0xE7
                OutBuffer[3] = 0x00
            elif requested_mode == BridgeMode_TBPDigitizer:
                OutBuffer[0] = 0x0
                OutBuffer[1] = 0xFE
                OutBuffer[2] = 0xE7
                OutBuffer[3] = 0x00
            elif requested_mode == BridgeMode_TBPAbsoluteMouse:
                OutBuffer[0] = 0x0
                OutBuffer[1] = 0xFF
                OutBuffer[2] = 0xE7
                OutBuffer[3] = 0x01
                OutBuffer[4] = 0x01  # X scaling multiplier low byte
                OutBuffer[5] = 0x00  # X scaling multiplier high byte
                OutBuffer[6] = 0x01  # X scaling divisor low byte
                OutBuffer[7] = 0x00  # X scaling divisor high byte
                OutBuffer[8] = 0x01  # Y scaling multiplier low byte
                OutBuffer[9] = 0x00  # Y scaling multiplier high byte
                OutBuffer[10] = 0x01  # Y scaling divisor low byte
                OutBuffer[11] = 0x00  # Y scaling divisor high byte

            comms.stop_bridge()
            comms.write_device(bytes(OutBuffer))
            buffer = []
            while (len(buffer) != 0):
                buffer = comms.read_device()
            print("Changed bridge mode to " + args.m)

    except(KeyError):
        print("TNx USB Bridge in mode: " + TBP_MODE_PID[comms.pid])




