import argparse
import asyncio
from bleak import BleakClient
from PIL import Image
from job import create_job

parser = argparse.ArgumentParser(description='Prints an image on a DYMO LetraTag 200B')
parser.add_argument('--address', type=str, help='MAC address of printer', required=True)
parser.add_argument('--image', type=str, help='Image file to print', required=True)
args = parser.parse_args()

def print_hex(data):
    print(' '.join(f'{i:02x}' for i in data))

async def print_image(address, job):
    async with BleakClient(address) as client:
        # unsure if every device has the same uuid, so we search for it
        for service in client.services:
            first, second, _, _, _ = service.uuid.split('-')
            if first == 'be3dd650':
                uuid = second
                break
        
        for chunk in job:
            print_hex(chunk)
            await client.write_gatt_char(f'be3dd651-{uuid}-42f1-99c1-f0f749dd0678', bytearray(chunk))

async def main():
    with Image.open(args.image) as img:
        request = create_job(img)
        await print_image(args.address, request)

asyncio.run(main())
