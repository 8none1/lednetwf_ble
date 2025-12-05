# PYTHON IMPLEMENTATION GUIDE

## Complete Example

```python
import asyncio
from bleak import BleakClient, BleakScanner

SERVICE_UUID = "0000ffff-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000ff01-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"

class LEDController:
    def __init__(self, address: str, ble_version: int = 0):
        self.address = address
        self.ble_version = ble_version
        self.seq = 0
        self.client = None
        self.response_event = asyncio.Event()
        self.last_response = None

    def _checksum(self, data: bytes) -> int:
        return sum(data) & 0xFF

    def _wrap_transport(self, cmd: bytes, expect_response: bool = False) -> bytes:
        cmd_id = 10 if expect_response else 11
        packet = bytearray(8 + len(cmd))
        packet[0] = 0x00
        packet[1] = self.seq & 0xFF
        self.seq = (self.seq + 1) & 0xFF
        packet[2] = 0x80
        packet[3] = 0x00
        packet[4] = (len(cmd) >> 8) & 0xFF
        packet[5] = len(cmd) & 0xFF
        packet[6] = (len(cmd) + 1) & 0xFF
        packet[7] = cmd_id
        packet[8:] = cmd
        return bytes(packet)

    def _notification_handler(self, sender, data: bytearray):
        self.last_response = bytes(data)
        self.response_event.set()

    async def connect(self):
        self.client = BleakClient(self.address)
        await self.client.connect()
        await self.client.start_notify(NOTIFY_UUID, self._notification_handler)

    async def disconnect(self):
        if self.client:
            await self.client.disconnect()

    async def send(self, cmd: bytes, expect_response: bool = False) -> bytes:
        packet = self._wrap_transport(cmd, expect_response)
        await self.client.write_gatt_char(WRITE_UUID, packet)

        if expect_response:
            self.response_event.clear()
            try:
                await asyncio.wait_for(self.response_event.wait(), timeout=5.0)
                return self.last_response
            except asyncio.TimeoutError:
                return None
        return None

    async def power_on(self):
        cmd = bytes([0x11, 0x1A, 0x1B, 0xF0])
        cmd += bytes([self._checksum(cmd)])
        await self.send(cmd)

    async def power_off(self):
        cmd = bytes([0x11, 0x1A, 0x1B, 0x0F])
        cmd += bytes([self._checksum(cmd)])
        await self.send(cmd)

    async def set_rgb(self, r: int, g: int, b: int, ww: int = 0, cw: int = 0):
        cmd = bytes([0x31, r&0xFF, g&0xFF, b&0xFF, ww&0xFF, cw&0xFF, 0x5A, 0x0F])
        cmd += bytes([self._checksum(cmd)])
        await self.send(cmd)

    async def set_brightness(self, brightness: int):
        cmd = bytes([0x47, brightness & 0xFF])
        cmd += bytes([self._checksum(cmd)])
        await self.send(cmd)

    async def query_state(self) -> dict:
        cmd = bytes([0x81, 0x8A, 0x8B, 0x40])
        response = await self.send(cmd, expect_response=True)

        if response and len(response) >= 14 and response[0] == 0x81:
            return {
                'power_on': response[2] == 0x23,
                'red': response[6],
                'green': response[7],
                'blue': response[8],
                'warm_white': response[9],
                'brightness': response[10],
                'cool_white': response[11],
            }
        return None

# Usage
async def main():
    controller = LEDController("E4:98:BB:95:EE:8E", ble_version=5)
    await controller.connect()

    state = await controller.query_state()
    print(f"State: {state}")

    await controller.power_on()
    await controller.set_rgb(255, 0, 0)  # Red

    await controller.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```
