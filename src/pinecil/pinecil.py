from typing import List, Tuple, Dict
import struct
import logging
import asyncio
from .pinecil_setting_limits import value_limits
from .pinecil_setting_limits import temperature_limits
from .crx_uuid_name_map import (
    names_v220,
    names_v221beta1,
    names_v221beta2,
    bulk_data_names_v220,
    bulk_data_names_v221beta2,
)
from .ble import (
    BleakGATTCharacteristic,
    BLE,
    find_device_addresses,
)
import time


_LOGGER = logging.getLogger(__name__)

class ValueOutOfRangeException(Exception):
    message = "Value out of range"


class InvalidSettingException(Exception):
    message = "Invalid setting"


class SettingNameToUUIDMap:
    def __init__(self):
        self.names = names_v220

    def set_version(self, version: str):
        names = {
            "2.20": names_v220,
            "2.21beta1": names_v221beta1,
            "2.21beta2": names_v221beta2,
        }
        self.names = names.get(version, names_v220)

    def get_name(self, uuid: str) -> str:
        return self.names.get(uuid, uuid)

    def get_uuid(self, name: str) -> str:
        return next((k for k, v in self.names.items() if v == name), name)


class BulkDataToUUIDMap:
    def __init__(self):
        self.names = bulk_data_names_v220

    def set_version(self, version: str):
        names = {
            "2.20": bulk_data_names_v220,
            "2.21beta1": bulk_data_names_v220,
            "2.21beta2": bulk_data_names_v221beta2,
        }
        self.names = names.get(version, names_v220)

    def get_name(self, uuid: str) -> str:
        return self.names.get(uuid, uuid)

    def get_uuid(self, name: str) -> str:
        return next((k for k, v in self.names.items() if v == name), name)


class Pinecil:
    def __init__(self, ble: BLE):
        """Pinecil class

        Args:
            ble (BLE): instance of BLE connection to Pinecil
        """
        self.ble = ble
        self.settings_uuid: str
        self.bulk_data_uuid: str
        self.temp_unit_crx: str = "TemperatureUnit"
        self.settings_map = SettingNameToUUIDMap()
        self.bulk_data_map = BulkDataToUUIDMap()
        self.crx_settings: List[BleakGATTCharacteristic] = []
        self.crx_bulk_data: BleakGATTCharacteristic
        self.bulk_data_to_read: str = "BulkData"
        self.is_initialized = False
        self.is_getting_settings = False
        self.__last_read_settings = {}
        self.__last_read_settings_time = 0
        self.unique_id = ""
        self.build_version = ""

    @property
    def is_connected(self) -> bool:
        """Whether the Pinecil is connected

        Returns:
            bool: True if connected, False otherwise
        """
        return self.ble.is_connected and self.is_initialized

    async def __set_ble_uuids_based_on_version(self):
        # this is just a hack until the version is exposed in the settings
        uuid_settings_pre_221 = "f6d75f91-5a10-4eba-a233-47d3f26a907f"
        uuid_settings_221beta2 = "f6d80000-5a10-4eba-aa55-33e27f9bc533"
        uuid_bulk_data_pre_221 = "9eae1adb-9d0d-48c5-a6e7-ae93f0ea37b0"
        uuid_bulk_data_221beta2 = "9eae1000-9d0d-48c5-aa55-33e27f9bc533"
        services = await self.ble.get_services()
        if uuid_settings_221beta2 in services:
            self.settings_uuid = uuid_settings_221beta2
            self.bulk_data_uuid = uuid_bulk_data_221beta2
            self.settings_map.set_version("2.21beta2")
            self.bulk_data_map.set_version("2.21beta2")
            return
        crx_settings = await self.ble.get_characteristics(uuid_settings_pre_221)
        for crx in crx_settings:
            if crx.uuid == "0000ffff-0000-1000-8000-00805f9b34fb":
                self.settings_map.set_version("2.21beta1")
                self.bulk_data_map.set_version("2.21beta1")
                break
        else:
            self.settings_map.set_version("2.20")
            self.bulk_data_map.set_version("2.20")
        self.settings_uuid = uuid_settings_pre_221
        self.bulk_data_uuid = uuid_bulk_data_pre_221

    async def connect(self):
        """Attempts to connect to Pinecil
        Raises:
            DeviceNotFoundException: If Pinecil is not found
        """
        await self.ble.ensure_connected()
        await self.__set_ble_uuids_based_on_version()

        self.crx_settings = await self.ble.get_characteristics(self.settings_uuid)
        bulk_crx = await self.ble.get_characteristics(self.bulk_data_uuid)
        for crx in bulk_crx:
            if crx.uuid == self.bulk_data_map.get_uuid(self.bulk_data_to_read):
                self.crx_bulk_data = crx
                break
        self.unique_id, self.build_version = await self.__get_pinecil_info()
        self.is_initialized = True

    async def __read_setting(self, crx: BleakGATTCharacteristic) -> Tuple[str, int]:
        raw_value = await self.ble.read_characteristic(crx)
        number = struct.unpack("<H", raw_value)[0]
        return self.settings_map.get_name(crx.uuid), number

    async def __get_pinecil_info(self) -> Tuple[str, str]:
        try:
            device_id = ""
            build_version = ""
            characteristics = await self.ble.get_characteristics(self.bulk_data_uuid)
            for crx in characteristics:
                if crx.uuid == self.bulk_data_map.get_uuid("DeviceID"):
                    raw_value = await self.ble.read_characteristic(crx)
                    n = struct.unpack("<Q", raw_value)[0]
                    # using algorithm from here:
                    # https://github.com/Ralim/IronOS/commit/eb5d6ea9fd6acd221b8880650728e13968e54d3d
                    unique_id = (n & 0xFFFFFFFF) ^ ((n >> 32) & 0xFFFFFFFF)
                    device_id = f"{unique_id:X}"
                elif crx.uuid == self.bulk_data_map.get_uuid("Build"):
                    raw_value = await self.ble.read_characteristic(crx)
                    build_version = raw_value.decode("utf-8").strip("v")
            return device_id, build_version
        except Exception:
            return "", ""

    async def get_all_settings(self) -> Dict[str, int]:
        """Gets all settings from Pinecil

        Returns:
            Dict[str, int]: key-value pairs of setting name and value
        """
        _LOGGER.debug("REQUEST FOR SETTINGS")
        while self.is_getting_settings:
            await asyncio.sleep(0.5)
        if time.time() - self.__last_read_settings_time < 2:
            return self.__last_read_settings
        try:
            _LOGGER.debug("Reading all settings")
            self.is_getting_settings = True
            if not self.is_connected:
                await self.connect()
            tasks = [
                asyncio.ensure_future(self.__read_setting(crx))
                for crx in self.crx_settings
            ]
            results = await asyncio.gather(*tasks)
            settings = dict(results)
            _LOGGER.debug("Reading all settings DONE")
            self.__last_read_settings = settings
            self.__last_read_settings_time = time.time()
            return settings
        except Exception as e:
            raise e
        finally:
            self.is_getting_settings = False

    async def __ensure_valid_temperature(self, setting: str, temperature: int):
        characteristics = await self.ble.get_characteristics(self.settings_uuid)
        temp_uuid = self.settings_map.get_uuid(self.temp_unit_crx)
        for crx in characteristics:
            if crx.uuid == temp_uuid:
                raw_value = await self.ble.read_characteristic(crx)
                temp_unit = struct.unpack("<H", raw_value)[0]
                within_limit = temperature_limits[setting][temp_unit]
                if not within_limit(temperature):
                    _LOGGER.debug(
                        "Temp. %s is out of range for setting %s",
                        temperature,
                        setting,
                    )
                    raise ValueOutOfRangeException
                break

    async def set_one_setting(self, setting: str, value: int):
        """Sets one setting on Pinecil.
        Does not save to flash (changes will be lost after reboot).

        Args:
            setting (str): name of the setting
            value (int): value to set

        Raises:
            Exception: when trying to set a setting that does not exist
        """
        ensure_setting_exists(setting)
        ensure_setting_value_within_limits(setting, value)
        if not self.is_connected:
            await self.connect()
        if setting in temperature_limits:
            await self.__ensure_valid_temperature(setting, value)
        _LOGGER.debug("Setting %s (%s) to %s", value, type(value), setting)
        uuid = self.settings_map.get_uuid(setting)
        for crx in self.crx_settings:
            if crx.uuid == uuid:
                v = struct.pack("<H", value)
                await self.ble.write_characteristic(crx, bytearray(v))
                break
        else:
            raise Exception("Setting not found")

    async def save_to_flash(self):
        """Saves current settings to flash - settings will be preserved after reboot."""
        await self.set_one_setting("save_to_flash", 1)

    async def get_info(self) -> Dict[str, str]:
        """Get basic info about Pinecil

        Returns:
            Dict[str, str]: key-value pairs of info.
        Example:
            {"name": "Pinecil-123456", "id": "123456", "build": "2.20"}
        """
        if not self.is_connected:
            await self.connect()
        return {
            "name": f"Pinecil-{self.unique_id}",
            "id": self.unique_id,
            "build": self.build_version or "2.20",
        }

    async def __read_live_data(self, crx: BleakGATTCharacteristic) -> Dict[str, int]:
        raw_value = await self.ble.read_characteristic(crx)
        num_of_values = len(raw_value) >> 2
        values = struct.unpack(f"<{num_of_values}I", raw_value)
        values_map = [
            "LiveTemp",
            "SetTemp",
            "Voltage",
            "HandleTemp",
            "PWMLevel",
            "PowerSource",
            "TipResistance",
            "Uptime",
            "MovementTime",
            "MaxTipTempAbility",
            "uVoltsTip",
            "HallSensor",
            "OperatingMode",
            "Watts",
        ]
        return dict(zip(values_map, values))

    async def get_live_data(self) -> Dict[str, int]:
        """Retrieves live data from Pinecil.

        Returns:
            Dict[str, int]: key-value pairs of live data.
            Example:
            {
                "LiveTemp": 35
                "SetTemp": 320
                "Voltage": 199
                "HandleTemp": 299
                "PWMLevel": 0
                "PowerSource": 3
                "TipResistance": 80
                "Uptime": 639707
                "MovementTime": 593
                "MaxTipTempAbility": 452
                "uVoltsTip": 1063
                "HallSensor": 41
                "OperatingMode": 0
                "Watts": 0
            }
        """
        _LOGGER.debug("GETTING ALL LIVE VALUES")
        if not self.is_connected:
            await self.connect()
        values = await self.__read_live_data(self.crx_bulk_data)
        _LOGGER.debug("GETTING ALL LIVE VALUES DONE")
        return values


def ensure_setting_exists(name: str):
    if name not in names_v220.values() and name not in names_v221beta1.values():
        _LOGGER.debug("Setting %s does not exist", name)
        raise InvalidSettingException


def ensure_setting_value_within_limits(name: str, value: int):
    min_val, max_val = value_limits[name]
    if not min_val <= value <= max_val:
        _LOGGER.debug(
            "Value %s is out of range for setting %s (%s-%s)",
            value,
            name,
            min_val,
            max_val,
        )
        raise ValueOutOfRangeException


async def find_pinecils() -> List[Pinecil]:
    """Looks for BLE devices that have 'pinecil' in their name.

    Returns:
        List[Pinecil]: A list of available devices
    """
    addresses = await find_device_addresses("pinecil")
    return [Pinecil(BLE(a)) for a in addresses]
