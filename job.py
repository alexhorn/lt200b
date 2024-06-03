import numpy as np
from PIL import Image

def _calculate_checksum(data):
    checksum = 0
    for byte in data:
        checksum += byte
    return checksum & 0xFF

def _split_chunks(data, chunk_size = 500):
    chunks = []
    for i in range(0, len(data), chunk_size):
        chunks.append([i // chunk_size, *data[i:i + chunk_size]])
    chunks[-1].extend([0x12, 0x34])
    return chunks

def _prepare_image(img):
    # convert to 1-bit monochrome
    img = img.convert('1', dither=Image.Dither.NONE)
    # rotate since the printer expects a portrait image
    img = img.rotate(-90, expand=1)
    # resize to width 32
    width = 32
    height = int(64 * (img.height / img.width))
    img = img.resize((width, height))
    # convert to zeroes and ones
    return [1 if x < 128 else 0 for x in img.getdata()], height, width

def _get_header_bytes(length):
    return [
        0xFF, # preamble
        0xF0, # flags, always this value
        0x12, 0x34, # magic
        *(length_bytes := length.to_bytes(4, byteorder='little')), # data length
        _calculate_checksum([0xFF, 0xF0, 0x12, 0x34, *length_bytes])
    ]

def _get_start_job():
    return [
        0x1B,
        0x73, # type: start job
        0x9A, 0x02, 0x00, 0x00 # job id, always this value
    ]

def _get_print_data(data, width, height):
    if width*height != len(data)*8:
        raise ValueError(f'data does not match dimensions ({width}*{height}!={len(data)*8})')
    
    return [
        0x1B,
        0x44, # type: print data
        0x01, # bits per pixel
        0x02, # alignment
        *width.to_bytes(4, byteorder='little'), # width
        *height.to_bytes(4, byteorder='little'), # height
        *data # data
    ]

def _get_form_feed():
    return [
        0x1B,
        0x45 # type: form feed
    ]

def _get_status():
    return [
        0x1B,
        0x41 # type: status
    ]

def _get_end():
    return [
        0x1B,
        0x51 # type: end
    ]

def create_job(image):
    # a job always consists of the following parts:
    # * header bytes
    # * chunked body consisting of:
    #   * start job
    #   * print data
    #   * form feed
    #   * status
    #   * end

    data, width, height = _prepare_image(image)
    packed_data = np.packbits(np.array(data), bitorder='little').tolist()

    body = [
        *_get_start_job(),
        *_get_print_data(packed_data, width, height),
        *_get_form_feed(),
        *_get_status(),
        *_get_end()
    ]
    header = _get_header_bytes(len(body))
    chunks = _split_chunks(body)

    return [header, *chunks]
