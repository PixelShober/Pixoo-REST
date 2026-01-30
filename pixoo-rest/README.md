# # Home Assistant Add-on: Pixoo REST

[![Release][release-shield]][release] [![License][license-shield]](LICENSE)

![Supports aarch64 Architecture][aarch64-shield]
![Supports amd64 Architecture][amd64-shield]
![Supports armhf Architecture][armhf-shield]
![Supports armv7 Architecture][armv7-shield]
![Supports i386 Architecture][i386-shield]

RESTful API to easily interact with Wi-Fi enabled Divoom Pixoo and Time Gate displays, including automatic device discovery and seamless Home Assistant integration.

## About

This add-on provides a REST API to control Divoom Pixoo devices (16x16, 32x32, and 64x64) and Time Gate displays. It wraps the [pixoo-rest](https://github.com/4ch1m/pixoo-rest) application and integrates it seamlessly into Home Assistant.

**Features:**

- 🔍 **Automatic Device Discovery** - Finds your Pixoo device on the local network automatically
- 🎨 **Full API Control** - 50+ endpoints for images, text, animations, and more
- 📱 **Swagger UI** - Interactive API documentation at `http://[HOST]:5000/docs#/`
- 🏠 **Home Assistant Integration** - Easy REST commands and automations
- 🖼️ **Image Support** - Display custom images, GIFs, and animations
- ⏱️ **Timers & Countdowns** - Built-in timer and countdown functionality
- 🌡️ **Sensor Data** - Display temperature, humidity, and other sensor values
- 🎵 **Visualizations** - Sound spectrum analyzer and visualizer effects
- **Time Gate Support** - Dedicated endpoints for multi-screen Time Gate devices
- **Multi-Device Support** - Configure and target multiple Pixoo/Time Gate devices

## Installation

1. Add this repository to your Home Assistant add-on store:
   ```
   https://github.com/PixelShober/Pixoo-REST
   ```

2. Install the "Pixoo REST" add-on

3. Configure the add-on (see Configuration section)

4. Start the add-on

5. Access the Swagger UI at `http://homeassistant.local:5000/docs#/`

## Configuration

### Minimal Configuration (Automatic Discovery)

```yaml
PIXOO_HOST_AUTO: true
PIXOO_DEVICE_TYPE: auto
PIXOO_SCREEN_SIZE: 64
```

### Manual Configuration

```yaml
PIXOO_HOST_AUTO: false
PIXOO_HOST: "192.168.1.100"
PIXOO_DEVICE_TYPE: auto
PIXOO_SCREEN_SIZE: 64
PIXOO_DEBUG: false
PIXOO_CONNECTION_RETRIES: 10
PIXOO_REST_DEBUG: false
```

### Time Gate Configuration (Manual)

```yaml
PIXOO_HOST_AUTO: false
PIXOO_HOST: "192.168.1.200"
PIXOO_DEVICE_TYPE: time_gate
PIXOO_SCREEN_SIZE: 128
```

### Multiple Devices Configuration

Use the add-on UI to add devices. Each entry can have its own auto-detect, IP, type, and screen size.
If `PIXOO_DEVICES` is set, the single-device options are used only as defaults.
For auto-detect, set `name` to the device name shown by Divoom so the correct IP is selected.

```yaml
PIXOO_DEVICES:
  - name: office
    host_auto: false
    host: "192.168.1.100"
    device_type: pixoo
    screen_size: 64
  - name: hallway
    host_auto: true
    device_type: auto
    screen_size: 128
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `PIXOO_DEVICES` | list | `[]` | List of device entries (name/host/type/size). When set, overrides single-device host/type/size. |
| `PIXOO_HOST_AUTO` | bool | `true` | Enable automatic device discovery |
| `PIXOO_HOST` | string | `null` | Manual IP address (required if auto is `false`) |
| `PIXOO_DEVICE_TYPE` | list | `auto` | Device type: `auto`, `pixoo`, or `time_gate` |
| `PIXOO_SCREEN_SIZE` | list | `64` | Screen size: `16`, `32`, `64`, or `128` pixels |
| `PIXOO_DEBUG` | bool | `false` | Enable debug logging for Pixoo library |
| `PIXOO_CONNECTION_RETRIES` | int | `10` | Connection retry attempts (1-30) |
| `PIXOO_REST_DEBUG` | bool | `false` | Enable REST API debug logging |

## Usage Examples

### Display Custom Text

```bash
curl -X POST http://homeassistant.local:5000/device/text \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello!",
    "position": 0,
    "color": "#FF0000",
    "font": 3
  }'
```

### Show Image from URL

```bash
curl -X POST http://homeassistant.local:5000/device/image/url \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/image.jpg"
  }'
```

### Home Assistant Automation

```yaml
automation:
  - alias: "Display temperature on Pixoo"
    trigger:
      - platform: state
        entity_id: sensor.living_room_temperature
    action:
      - service: rest_command.pixoo_text
        data:
          text: "{{ states('sensor.living_room_temperature') }}°C"
```

### Home Assistant REST Commands (Pixoo)

Add this to your `configuration.yaml` so you can call Pixoo endpoints with parameters from **Developer Tools -> Services**.

```yaml
rest_command:
  pixoo_text:
    url: "http://{{ host }}:5000/device/text?device={{ device }}"
    method: POST
    headers:
      Content-Type: application/json
    payload: >
      {{ {
        "text": text,
        "position": position,
        "color": color,
        "font": font
      } | tojson }}

  pixoo_brightness:
    url: "http://{{ host }}:5000/device/brightness?device={{ device }}"
    method: POST
    headers:
      Content-Type: application/json
    payload: >
      {{ {
        "brightness": brightness
      } | tojson }}

  pixoo_gif:
    url: "http://{{ host }}:5000/device/image/url?device={{ device }}"
    method: POST
    headers:
      Content-Type: application/json
    payload: >
      {{ {
        "url": url
      } | tojson }}
```

Developer Tools example data for `rest_command.pixoo_text`:

```yaml
host: 192.168.178.165
device: office
text: "Hello from Home Assistant"
position: 0
color: "#00FF00"
font: 3
```

Developer Tools example data for `rest_command.pixoo_brightness`:

```yaml
host: 192.168.178.165
device: office
brightness: 35
```

Developer Tools example data for `rest_command.pixoo_gif`:

```yaml
host: 192.168.178.165
device: office
url: "https://example.com/animation.gif"
```

If you omit `device`, the first entry in `PIXOO_DEVICES` is used. You can also target by IP with `?host=...`.

### Home Assistant REST Commands (Time Gate)

Add these to your `configuration.yaml` when using a Time Gate device. The payload and URL are parameterized so you can change them in **Developer Tools → Services**.

```yaml
rest_command:
  timegate_play_gif:
    url: "http://{{ host }}:5000/timegate/play-gif?device={{ device }}"
    method: POST
    headers:
      Content-Type: application/json
    payload: >
      {{ {
        "lcd_array": lcd_array,
        "file_name": file_name
      } | tojson }}

  timegate_send_text:
    url: "http://{{ host }}:5000/timegate/send-text?device={{ device }}"
    method: POST
    headers:
      Content-Type: application/json
    payload: >
      {{ {
        "lcd_index": lcd_index,
        "text_id": text_id,
        "x": x,
        "y": y,
        "direction": direction,
        "font": font,
        "text_width": text_width,
        "text": text,
        "speed": speed,
        "color": color,
        "align": align
      } | tojson }}
```

Developer Tools example data for `rest_command.timegate_play_gif`:

```yaml
host: 192.168.178.165
device: hallway
lcd_array: [0,0,0,1,0]
file_name:
  - "http://f.divoom-gz.com/128_128.gif"
```

Developer Tools example data for `rest_command.timegate_send_text`:

```yaml
host: 192.168.178.165
device: hallway
lcd_index: 4
text_id: 1
x: 0
y: 40
direction: 0
font: 4
text_width: 56
text: "Hallo"
speed: 10
color: "#FFFF00"
align: 1
```

Note: Time Gate text requires an active animation layer. Call `timegate_play_gif` first, then `timegate_send_text`.

See [DOCS.md](DOCS.md) for complete documentation and more examples.

## API Documentation

Interactive API documentation is available via Swagger UI at:
```
http://[HOST]:5000/docs#/
```

For detailed information about all available endpoints, see [AGENTS.md](../AGENTS.md).

## Support

- **Issues:** [GitHub Issues](https://github.com/PixelShober/Pixoo-REST/issues)
- **Upstream Project:** [pixoo-rest](https://github.com/4ch1m/pixoo-rest)
- **Pixoo Library:** [pixoo](https://github.com/SomethingWithComputers/pixoo)

## Credits

- **pixoo-rest** by [@4ch1m](https://github.com/4ch1m)
- **pixoo library** by [@SomethingWithComputers](https://github.com/SomethingWithComputers)

## License

MIT License - see [LICENSE](../LICENSE) for details.

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg
[license-shield]: https://img.shields.io/github/license/PixelShober/Pixoo-REST.svg
[release-shield]: https://img.shields.io/badge/version-2.0.15-blue.svg
[release]: https://github.com/PixelShober/Pixoo-REST/releases/tag/v2.0.15
