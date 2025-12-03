# CONNECTION MANAGEMENT

## BLE Connection Sequence

1. Discover device via BLE scanning
2. Initiate GATT connection: `bluetoothDevice.connectGatt()`
3. Wait for `onConnectionStateChange` with `STATE_CONNECTED`
4. Call `gatt.discoverServices()`
5. Wait for `onServicesDiscovered`
6. Enable notifications on notify characteristic
7. Request MTU (512 if bleVersion >= 8, else 255)
8. Device ready for commands

## Notification Enable (The "01 00" Packet)

The `01 00` bytes seen in Wireshark are the standard BLE CCCD notification enable value, NOT a protocol command.

**Source**: HBConnectionImpl.java lines 369-372:
```java
BluetoothGattDescriptor descriptor = characteristic.getDescriptor(CLIENT_CHARACTERISTIC_CONFIGURATION);
descriptor.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
bluetoothGatt.writeDescriptor(descriptor);
```

**CCCD UUID**: `00002902-0000-1000-8000-00805f9b34fb`

| Value | Meaning                 |
|-------|-------------------------|
| 01 00 | Enable notifications    |
| 02 00 | Enable indications      |
| 00 00 | Disable                 |

Most BLE libraries handle this automatically when you subscribe to notifications.
