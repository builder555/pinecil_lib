import logging
from typing import List
from bleak import BleakClient
from bleak import BleakScanner
from bleak.exc import BleakDeviceNotFoundError
from bleak.exc import BleakError
from bleak.backends.characteristic import BleakGATTCharacteristic
import asyncio


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
        """BLE device wrapper

        Args:
            address (str): MAC address of the device (or uuid for mac os)
        """
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
        """Connects to the device if not connected, otherwise does nothing

        Raises:
            DeviceNotFoundException: If the device is gone.
        """
        try:
            if self.__client.is_connected:
                return
            await self.__client.connect()
        except (BleakDeviceNotFoundError, asyncio.exceptions.TimeoutError):
            logging.info(f'Could not find device with "{self.__address}" address')
            raise DeviceNotFoundException
        except BleakError as e:
            err_msg = str(e).lower()
            if "disconnected" in err_msg or "turned off" in err_msg:
                logging.info(f'Could not find device with "{self.__address}" address')
                raise DeviceNotFoundException
            else:
                raise e

    async def get_services(self) -> List[str]:
        """Get list of services available on the device

        Returns:
            List[str]: List of service uuids
        """
        await self.ensure_connected()
        return [s.uuid for s in self.__client.services]

    async def get_characteristics(
        self, service_uuid: str
    ) -> List[BleakGATTCharacteristic]:
        """Get list of characteristics available on the service

        Args:
            service_uuid (str): Service uuid

        Raises:
            Exception: If the service is not found

        Returns:
            List[BleakGATTCharacteristic]: Characteristics handles
        """
        await self.ensure_connected()
        service = self.__client.services.get_service(service_uuid)
        if service:
            return service.characteristics
        raise Exception(f"Could not find service {service_uuid}")

    async def read_characteristic(self, handle: BleakGATTCharacteristic) -> bytes:
        """Reads the value of the characteristic

        Args:
            handle (BleakGATTCharacteristic): Characteristic handle

        Raises:
            DeviceDisconnectedException: If the device is disconnected
            Exception: Any other exception

        Returns:
            bytes: Value of the characteristic
        """
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
        """Writes the value to the characteristic

        Args:
            handle (BleakGATTCharacteristic): Characteristic handle
            value (bytes): Value to write
        """
        await self.ensure_connected()
        logging.debug(f"Writing characteristic {handle.uuid}")
        await self.__client.write_gatt_char(handle, value)
        logging.debug(f"Writing characteristic {handle.uuid} DONE")
