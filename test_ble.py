import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from ble import find_device_addresses, BLE
from dataclasses import dataclass
from test_utils import Method

@dataclass
class MockDevice:
    name: str
    address: str


@dataclass
class MockCharacteristic:
    uuid: str


@dataclass
class MockService:
    uuid: str
    characteristics: list[MockCharacteristic]


@pytest.fixture
def fake_services():
    class Svcs:
        def __init__(self):
            self.services = [
                MockService(
                    uuid="f6d80000-5a10-4eba-aa55-33e27f9bc533",
                    characteristics=[
                        MockCharacteristic(uuid="f6d80000-5a10-4eba-aa55-33e27f9bc530"),
                        MockCharacteristic(uuid="f6d80000-5a10-4eba-aa55-33e27f9bc531"),
                    ],
                ),
                MockService(
                    uuid="9eae1000-9d0d-48c5-aa55-33e27f9bc533",
                    characteristics=[
                        MockCharacteristic(uuid="9eae1000-9d0d-48c5-aa55-33e27f9bc535"),
                        MockCharacteristic(uuid="9eae1000-9d0d-48c5-aa55-33e27f9bc536"),
                    ],
                ),
            ]
            self.value = 0
            self.limit = len(self.services)

        def get_service(self, uuid: str):
            for s in self.services:
                if s.uuid == uuid:
                    return s
            return None

        def __iter__(self):
            self.value = 0
            return self

        def __next__(self):
            if self.value < self.limit:
                self.value += 1
                return self.services[self.value - 1]
            else:
                raise StopIteration

    return Svcs()


@pytest.fixture
def mock_bleak_client(fake_services):
    client = MagicMock()
    client.is_connected = False

    def fake_connect():
        client.is_connected = True

    client.connect = AsyncMock(side_effect=fake_connect)
    client.services = fake_services
    client.read_gatt_char = AsyncMock(return_value=b"test")
    client.write_gatt_char = AsyncMock()
    return client


@pytest.mark.asyncio
async def test_find_all_pinecil_addresses():
    mock_devices = [
        MockDevice(name="pinecil-123", address="aa:bb:cc:dd:ee:ff"),
        MockDevice(name="pinecil-abc", address="11:22:33:44:55:66"),
    ]
    with patch("ble.BleakScanner.discover", return_value=mock_devices):
        addrs = await find_device_addresses("pinecil")

        assert addrs == ["aa:bb:cc:dd:ee:ff", "11:22:33:44:55:66"]


@pytest.mark.asyncio
async def test_ble_can_connect(mock_bleak_client):
    with patch("ble.BleakClient", return_value=mock_bleak_client):
        ble = BLE("00:11:22:33:44:55")
        assert not ble.is_connected

        await ble.ensure_connected()

        assert ble.is_connected


@pytest.mark.asyncio
async def test_list_available_services_on_device(mock_bleak_client, fake_services):
    with patch("ble.BleakClient", return_value=mock_bleak_client):
        ble = BLE("00:11:22:33:44:55")

        services = await ble.get_services()

        assert services == [s.uuid for s in fake_services]
        assert len(services) == 2


@pytest.mark.asyncio
async def test_list_GATT_characteristics_for_a_service(
    mock_bleak_client, fake_services
):
    with patch("ble.BleakClient", return_value=mock_bleak_client):
        ble = BLE("00:11:22:33:44:55")
        first_svc = next(fake_services)

        characteristics = await ble.get_characteristics(first_svc.uuid)

        assert characteristics == first_svc.characteristics
        assert len(characteristics) == 2


@pytest.mark.asyncio
async def test_can_read_characteristic(mock_bleak_client, fake_services):
    with patch("ble.BleakClient", return_value=mock_bleak_client):
        ble = BLE("00:11:22:33:44:55")
        first_svc = next(fake_services)
        first_crx = first_svc.characteristics[0]

        value = await ble.read_characteristic(first_crx)

        assert value == b"test"


@pytest.mark.asyncio
async def test_can_write_characteristic(mock_bleak_client, fake_services):
    with patch("ble.BleakClient", return_value=mock_bleak_client):
        ble = BLE("00:11:22:33:44:55")
        first_svc = next(fake_services)
        first_crx = first_svc.characteristics[0]

        await ble.write_characteristic(first_crx, b"write_test")
        assert Method(mock_bleak_client.write_gatt_char).was_called_with(first_crx, b"write_test")
