# JAVA SOURCE CODE REFERENCES

## Key Source Files

| File                              | Purpose                              |
|-----------------------------------|--------------------------------------|
| tc/b.java                         | Command builders (RGB, power, etc.)  |
| tc/d.java                         | HSV/Symphony command builder         |
| g2/c.java                         | Byte packing utilities               |
| ZGHBReceiveCallback.java          | Response handler                     |
| LowerTransportLayerDecoder.java   | Transport layer decoder              |
| UpperTransportLayer.java          | Transport layer structure            |
| HBConnectionImpl.java             | BLE connection management            |
| ZGHBDevice.java                   | Device model and parsing             |
| BaseDeviceInfo.java               | Device capability definitions        |
| Service.java                      | Service/characteristic UUIDs         |

## Command Builder References

| Command        | Method       | File          | Lines    |
|----------------|--------------|---------------|----------|
| RGB Color      | s(), t()     | tc/b.java     | ~        |
| Power On/Off   | m(), n()     | tc/b.java     | ~        |
| Brightness     | j()          | tc/b.java     | ~        |
| State Query    | l()          | tc/b.java     | ~        |
| HSV Color      | c()          | tc/d.java     | 19-35    |
| Effect         | ~            | tc/d.java     | 37-43    |
