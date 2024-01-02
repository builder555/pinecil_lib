[![Automated lint and tests](https://github.com/builder555/pinecil_lib/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/builder555/pinecil_lib/actions/workflows/ci.yml)

# Pinecil V2 interface library

## Overview
Pinecil is a lightweight Python library designed to inetrafce with Pinecil V2 soldering iron.

## Requirements
- Python 3.10 or higher

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
    await devices = find_pinecils()
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

## License
This project is licensed under the MIT-0 License

## Authors
- **[builder555](https://github.com/builder555)** - *Initial work*

## References
- Originally started as [PineSAM](https://github.com/builder555/PineSAM)

## TODO

- [x] able to scan for ble devices
- [x] able to connect to pinecil
- [x] get pinecil info
- [x] get settings
- [x] set settings
- [x] proper readme
- [x] run build on merge
- [x] run tests on merge
- [x] run lint on merge
- [ ] ci/cd - build and push to pypi
