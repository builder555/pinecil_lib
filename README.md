[![Automated lint and tests](https://github.com/builder555/pinecil_lib/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/builder555/pinecil_lib/actions/workflows/ci.yml)

# Pinecil V2 interface library

## Overview
Pinecil is a lightweight Python library designed to inetrafce with Pinecil V2 soldering iron.

## Requirements
- Python 3.9 or higher
- bluez

## Installation

```bash
pip install pinecil
```

## Usage Example

A complete from-scratch example:

```python
from pinecil import find_pinecils # if running in a cloned repo, use `from src.pinecil`
import asyncio

async def main():
    devices = await find_pinecils()
    iron = devices[0]
    await iron.connect()
    settings = await iron.get_all_settings()
    await iron.set_one_setting('SetTemperature', 250)
    await iron.save_to_flash() # this is required to preserve settings after powering off
    info = await iron.get_info()
    live = await iron.get_live_data()
    print(settings)
    print('----------')
    print(info)
    print('----------')
    print(live)

if __name__ == '__main__':
    asyncio.run(main())
```

If you already know the address of your pinecil, you can use it directly:

```python
from pinecil import BLE, Pinecil
import asyncio

if __name__ == '__main__':
    p = Pinecil(BLE('<your-address>'))
    asyncio.run(p.get_all_settings())
```

To find addresses of all pinecils nearby:

```python
from pinecil import find_device_addresses
import asyncio

if __name__ == '__main__':
    asyncio.run(find_device_addresses('pinecil'))
```

## Testing

```bash
poetry shell
pytest -v
# for development convenience:
ptw --runner 'pytest -v'
```

## References
- Originally started as [PineSAM](https://github.com/builder555/PineSAM)

# Docs

## Exceptions

- `ValueOutOfRangeException`: Attempting to set a settings value that is out of range.
- `InvalidSettingException`: Setting does not exist.
- `DeviceNotFoundException`: Indicates the device was not found.
- `DeviceDisconnectedException`: Indicates the device was disconnected.

## Classes and Functions

### Class: `Pinecil`
- Constructor: `__init__(self, ble: BLE)`: Initializes Pinecil with `BLE` instance.
- Properties:
  - `is_connected -> bool`: True if Pinecil is connected.
- Methods:
  - `connect(self)`: Connects to Pinecil.
  - `get_all_settings(self) -> Dict[str, int]`: Retrieves all settings.
  - `set_one_setting(self, setting: str, value: int)`: Sets a single setting - does not save to flash.
  - `save_to_flash(self)`: Saves all settings to flash.
  - `get_info(self) -> Dict[str, str]`: Retrieves basic Pinecil info.
  - `get_live_data(self) -> Dict[str, int]`: Retrieves live data.

### Class: `BLE`
- Constructor: `__init__(self, address: str)`: Initializes BLE device wrapper.
- Properties:
  - `is_connected -> bool`: True if connected to the device.
- Methods:
  - `ensure_connected(self)`: Connects to the device if not connected (does nothing if connected)
  - `get_services(self) -> List[str]`: Gets list of services.
  - `get_characteristics(self, service_uuid: str) -> List[BleakGATTCharacteristic]`: Gets characteristics of a service.
  - `read_characteristic(self, handle: BleakGATTCharacteristic) -> bytes`: Reads value of a characteristic
  - `write_characteristic(self, handle: BleakGATTCharacteristic, value: bytes)`: Writes value to a characteristic.

### Function: `find_device_addresses`
- Description: Finds devices matching a given name and returns their UUIDs
- Returns: `List[str]`: List of device addresses.

### Function: `find_pinecils`
- Description: Finds nearby pinecils and returns their list.
- Returns: `List[Pinecil]`: List of found device instances.
