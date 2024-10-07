
# LPP Client

This is a Python-based LPP (Location Protocol Platform) client application designed to work with Cradlepoint routers.

## Overview

The LPP client connects to a specified host and port, retrieves cellular information, and sends NMEA data. It supports various configuration options and can output data to different destinations.

## Configuration

Use the following yaml in the Cradlepoint container configuration

```yaml
version: '2.4'
services:
  lpp:
    network_mode: bridge
    image: ghcr.io/dapplegatecp/lpp-client
    restart: unless-stopped
    volumes:
      - $CONFIG_STORE
    devices:
      - /dev/ttyS1

```
> Note: the application running in the container relies on the container auto-restarting, so be sure to set restart to "unless-stopped" as shown above.

The application uses the following configuration parameters, which can be set using the Cradlepoint SDK's appdata:

- `lpp-client.host`: The host to connect to (default: 129.192.82.125)
- `lpp-client.port`: The port to connect to (default: 5431)
- `lpp-client.serial`: The serial port for NMEA data (default: /dev/ttyS1)
- `lpp-client.baud`: The baud rate for the serial connection (default: 115200)
- `lpp-client.output`: The output destination (default: "un" for Unix socket)
- `lpp-client.format`: The data format (default: "osr")
- `lpp-client.forwarding`: Forwarding configuration (optional)
- `lpp-client.flags`: Additional flags for the LPP client (optional)
- `lpp-client.path`: The CS (Configuration System) path for storing NMEA data (default: "/status/rtk/nmea")
- `lpp-client.starting_mmc`: The starting mmc (optional)
- `lpp-client.starting_mnc`: The starting mnc (optional)
- `lpp-client.starting_tac`: The starting tac (optional)
- `lpp-client.starting_cell_id`: The starting cell ID (optional)
- `lpp-client.mcc`: Mobile Country Code (optional)
- `lpp-client.mnc`: Mobile Network Code (optional)
- `lpp-client.tac`: Tracking Area Code (optional)
- `lpp-client.cell_id`: Cell ID (optional)
- `lpp-client.imsi`: International Mobile Subscriber Identity (optional)


## Cellular Information

The application retrieves cellular information from the router, including:

- MCC (Mobile Country Code)
- MNC (Mobile Network Code)
- TAC (Tracking Area Code)
- Cell ID
- IMSI (International Mobile Subscriber Identity)

These values can be overridden using the corresponding appdata settings (e.g., `lpp-client.mcc`, `lpp-client.mnc`, etc.).

The _initial_ starting values can also be overridden, these are the values sent to the lpp software's command line, but will be updated with real values via a control mechanism with values from the modem. These are the starting_mcc, starting_mnc, etc. settings.

## Output Options

- Unix Socket: When `output` is set to "un", the application creates a Unix socket at `/tmp/nmea.sock` for NMEA data output.
- TCP: When `output` is set to "ip:port", the application sends NMEA data to the specified IP address and port.

## Data Formats

- OSR (Observation State Record): Default format
- SSR (State Space Representation): Alternative format

## Additional Features

- Periodic checking for configuration changes
- Automatic restart on configuration changes
- Real-time cellular information updates
- Support for various flags and formatting options

## Usage

The application is designed to run automatically on the Cradlepoint router. Configure the desired options using the Cradlepoint SDK's appdata, and the LPP client will start with the specified settings.

For more detailed information about the implementation, please refer to the `main.py` file.
