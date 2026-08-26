# Copyright (c) 2024 TouchNetix
#
# This file is part of axutils and is released under the MIT License:
# See the LICENSE file in the root directory of this project or http://opensource.org/licenses/MIT.

import os
import binascii

def get_file_crc(file_name, data_index):
    file_size = os.path.getsize(file_name)
    with open(file_name, 'rb') as file:
        file.seek(data_index)
        file_data = file.read((file_size - data_index))
        crc = binascii.crc32(file_data, 0)
    return crc
