import argparse
import asyncio
import numpy as np
from bleak import BleakClient
from PIL import Image

parser = argparse.ArgumentParser(description='Prints an image on a DYMO LetraTag 200B')
parser.add_argument('--address', type=str, help='MAC address of printer', required=True)
parser.add_argument('--image', type=str, help='Image file to print', required=True)
args = parser.parse_args()

def print_hex(data):
    print(' '.join(f'{i:02x}' for i in data))

def get_checksum(data):
    checksum = 0
    for byte in data:
        checksum += byte
    return checksum & 0xFF

def get_header_bytes(length):
    return [
        0xFF, # preamble
        0xF0, # flags, always this value
        0x12, 0x34, # magic
        *(length_bytes := length.to_bytes(4, byteorder='little')), # data length
        get_checksum([0xFF, 0xF0, 0x12, 0x34, *length_bytes])
    ]

def get_start_job():
    return [
        0x1B,
        0x73, # type: start job
        0x9A, 0x02, 0x00, 0x00 # job id, always this value
    ]

def get_print_data(data, width, height):
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

def get_form_feed():
    return [
        0x1B,
        0x45 # type: form feed
    ]

def get_status():
    return [
        0x1B,
        0x41 # type: status
    ]

def get_end():
    return [
        0x1B,
        0x51 # type: end
    ]

def split_chunks(data):
    chunks = []
    chunk_size = 500
    for i in range(0, len(data), chunk_size):
        chunks.append([i // chunk_size, *data[i:i + chunk_size]])
    chunks[-1].extend([0x12, 0x34])
    return chunks

def prepare_image(img):
    # convert to 1-bit monochrome
    img = img.convert('1', dither=Image.Dither.NONE)
    # rotate since the printer expects a portrait image
    img = img.rotate(-90, expand=1)
    # resize to width 32
    width = 32
    height = int(64 / img.height * img.width)
    img = img.resize((width, height))
    # convert to zeroes and ones
    return [1 if x < 128 else 0 for x in img.getdata()], width, height

async def print_image(address, data, width, height):
    # a valid job always consists of the following parts:
    # * header bytes
    # * chunked body consisting of:
    #   * start job
    #   * print data
    #   * form feed
    #   * status
    #   * end

    packed_data = np.packbits(np.array(data), bitorder='little').tolist()
    body = [
        *get_start_job(),
        *get_print_data(packed_data, width, height),
        *get_form_feed(),
        *get_status(),
        *get_end()
    ]
    chunks = split_chunks(body)
    header = get_header_bytes(len(body))

    async with BleakClient(address) as client:
        # unsure if every device has the same uuid, so we search for it
        for service in client.services:
            first, second, _, _, _ = service.uuid.split('-')
            if first == 'be3dd650':
                uuid = second
                break
        
        print_hex(header)
        await client.write_gatt_char(f'be3dd651-{uuid}-42f1-99c1-f0f749dd0678', bytearray(header))
        for chunk in chunks:
            print_hex(chunk)
            await client.write_gatt_char(f'be3dd651-{uuid}-42f1-99c1-f0f749dd0678', bytearray(chunk))

async def main():
    with Image.open(args.image) as img:
        data, width, height = prepare_image(img)
        await print_image(args.address, data, height, width)

asyncio.run(main())
