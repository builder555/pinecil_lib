import logging
from typing import List
from bleak import BleakClient
from bleak import BleakScanner
from bleak.exc import BleakDeviceNotFoundError
from bleak.exc import BleakError
from bleak.backends.characteristic import BleakGATTCharacteristic


class DeviceNotFoundException(Exception):
    message = "Device not found"


class DeviceDisconnectedException(Exception):
    message = "Device disconnected"


async def find_device_addresses(name: str) -> List[str]:
    logging.info(f'Detecting "{name}"...')
    devices = await BleakScanner.discover()
    results = []
    for d in devices:
        if d.name is not None and name in d.name.lower():
            logging.info(f"Found {name} at {d.address}")
            results.append(d.address)
    logging.debug(f'Detecting "{name}" DONE')
    return results


class BLE:
    def __init__(self, address: str):
        self.__address = address
        self.__client = BleakClient(
            self.__address, disconnected_callback=self.__on_disconnected
        )

    @property
    def is_connected(self) -> bool:
        return self.__client.is_connected

    def __on_disconnected(self, client: BleakClient):
        logging.info(f"Disconnected from {self.__address}")
        raise DeviceDisconnectedException

    async def ensure_connected(self):
        try:
            if self.__client.is_connected:
                return
            await self.__client.connect()
        except BleakDeviceNotFoundError:
            logging.info(f'Could not find device with "{self.__address}" address')
            raise DeviceNotFoundException

    async def get_services(self) -> List[str]:
        await self.ensure_connected()
        return [s.uuid for s in self.__client.services]

    async def get_characteristics(
        self, service_uuid: str
    ) -> List[BleakGATTCharacteristic]:
        await self.ensure_connected()
        service = self.__client.services.get_service(service_uuid)
        if service:
            return service.characteristics
        raise Exception(f"Could not find service {service_uuid}")

    async def read_characteristic(self, handle: BleakGATTCharacteristic) -> bytes:
        try:
            await self.ensure_connected()
            return await self.__client.read_gatt_char(handle)
        except BleakError as e:
            if (
                str(e).lower() == "disconnected"
                or str(e).lower().find("turned off") >= 0
            ):
                raise DeviceDisconnectedException
            raise e

    async def write_characteristic(self, handle: BleakGATTCharacteristic, value: bytes):
        await self.ensure_connected()
        logging.debug(f"Writing characteristic {handle.uuid}")
        await self.__client.write_gatt_char(handle, value)
        logging.debug(f"Writing characteristic {handle.uuid} DONE")
