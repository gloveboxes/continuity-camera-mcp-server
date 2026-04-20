# Continuity Camera MCP Server

An MCP (Model Context Protocol) server built with FastMCP that captures photos from an iPhone via macOS Continuity Camera. Created for agentic IoT projects where the agent can see the state of the project — great for UI design, inspecting hardware, reading screens, checking wiring, and more.

## How It Works

The server uses macOS **Continuity Camera** to wirelessly access your iPhone's camera from Python via the `AVFoundation` framework (through PyObjC). It exposes two MCP tools:

- **`capture_photo`** — Captures a high-resolution JPEG from the iPhone camera with optional zoom, crop, rotation, and delay control
- **`list_cameras`** — Lists all available video capture devices and their Continuity Camera status

Key features:
- **Software zoom** for predictable framing (gentler control curve to preserve context)
- **Software crop** for repositioning the frame to any region of the image
- **Rotation support** (0°, 90°, 180°, 270°) for correcting image orientation
- **Built-in agent guidance** to help the AI use the tools effectively
- **stdio transport** for reliable integration with VS Code (avoids threading issues with HTTP)
- **Smart resolution scaling** — boosts output resolution for heavily zoomed images to preserve detail

## Requirements

- **macOS** (uses AVFoundation and Continuity Camera)
- **iPhone** with Continuity Camera enabled (iOS 16+)
- Both devices signed into the **same Apple ID** with **Bluetooth** and **Wi-Fi** enabled
- **Python 3.10+**

## Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/gloveboxes/continuity-camera-mcp-server.git
   cd continuity-camera-mcp-server
   ```

2. Create a virtual environment and install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Optional but recommended**: Before starting to use the MCP server, open the Camera app on your iPhone and review the device position from the iPhone's perspective. This helps you understand the camera's view and plan your framing when using `crop_x`, `crop_y`, and `zoom` parameters.

## Adding to VS Code

The camera server is a standalone MCP server that you reference from any workspace. Add it to your IoT project (or any workspace) by creating a `.vscode/mcp.json` file:

```json
{
  "servers": {
    "iPhone-Camera-Server": {
      "type": "stdio",
      "command": "/path/to/continuity-camera-mcp-server/.venv/bin/python",
      "args": ["/path/to/continuity-camera-mcp-server/camera_server.py"]
    }
  }
}
```

Replace `/path/to/continuity-camera-mcp-server` with the actual path to this repository.

VS Code automatically starts the stdio MCP server when the workspace loads. The `capture_photo` tool will be available to GitHub Copilot in chat.

## Usage

Once configured, GitHub Copilot can use the server's tools. Common patterns:

- *"List available cameras"*
- *"Capture a photo and describe what you see"*
- *"Take a photo with 3x zoom on the center"*
- *"Zoom in on the bottom-right corner at 2x zoom"*
- *"Capture a portrait-oriented photo"*
- *"Wait 15 seconds for the firmware to boot, then capture"*

The server includes built-in guidance to help Copilot use `capture_photo` for normal operations and only call `list_cameras` for diagnostics.

### Tool Parameters for `capture_photo`

| Parameter    | Type   | Default | Description |
|--------------|--------|---------|-------------|
| `label`      | string | `"iot_device"` | A descriptive label for this capture |
| `zoom`       | float  | `1.0`   | Software zoom factor. Uses a gentle curve (1.0 = no zoom, 2.0 ≈ 1.65x actual, 3.0 ≈ 2.3x actual) |
| `crop_x`     | float  | `0.5`   | Horizontal crop center (0.0 = left, 0.5 = center, 1.0 = right) |
| `crop_y`     | float  | `0.5`   | Vertical crop center (0.0 = top, 0.5 = center, 1.0 = bottom) |
| `resolution` | int    | `1080`  | Base max image dimension in pixels. Heavily zoomed/cropped images may use up to 2x this value to preserve detail |
| `rotate`     | int    | `0`     | Rotate image clockwise (0, 90, 180, or 270 degrees) |
| `pre_capture_delay_seconds` | float | `0.0` | Wait this many seconds before the shutter fires (useful for device boot or UI render time) |

**Parameter notes:**
- **`zoom`** applies software zoom for predictable framing. The control curve is intentionally gentler than literal crop magnification to preserve more context and make small zoom values less aggressive.
- **`crop_x` / `crop_y`** pan the zoomed frame relative to the final (rotated) image. Combined with `zoom`, this lets you focus on specific regions.
- **`resolution`** is the base output size. When `zoom >= 1.25`, the server increases output resolution (up to 4096px) to preserve fine details that would otherwise be lost to downsampling.
- **`pre_capture_delay_seconds`** pauses before snapping the photo — useful when capturing external hardware that needs time to boot or render a screen.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No iPhone found" | Ensure iPhone is nearby, unlocked, and on the same Apple ID. Toggle Bluetooth off/on. May take 5-10 seconds to reconnect. |
| "Capture timed out" | The iPhone may have dropped the Continuity Camera connection. Try again in a few seconds, or restart the MCP server. |
| "Capture timed out" (after 15 seconds) | Restart the MCP server. The wireless handoff may have stalled. |
| Zoom not working as expected | Restart the MCP server — since stdio servers are long-lived processes, code changes require a server restart to take effect. |
| Server crashes (exit code 134) | This is SIGABRT, usually from AVFoundation threading issues. Ensure you're using `stdio` transport (not `exec` or HTTP). |
| Image appears upside-down or rotated | Use the `rotate` parameter to correct the orientation: `rotate=180` for upside-down, `rotate=90` for 90° clockwise, etc. |
| Black/blank images | The iPhone camera may not have initialized. Wait a few seconds and try again, or check that Continuity Camera is enabled on both devices. |

## Performance & Optimization

- **Image size**: Default resolution of 1080px is optimized for LLM token cost. Reduce further if token usage is a concern.
- **Zoom with high resolution**: When using `zoom >= 1.5`, the server automatically scales output to 2× the base resolution to preserve fine details. Keep this in mind when optimizing for latency.
- **Capture warmup**: The first capture after starting the server takes ~3-4 seconds as the Continuity Camera connection initializes. Subsequent captures are faster (~1-2 seconds).
- **Timeout**: The server waits up to 15 seconds for the wireless handoff to complete. If your iPhone is far from your Mac, the connection may timeout.

## Requirements Detail

- **macOS 11+** (tested on macOS 13+; earlier versions may work but are unsupported)
- **Python 3.10+**
- **PyObjC** and **Pillow** dependencies
- **iPhone with iOS 16+** (Continuity Camera feature)
- **Apple ID**: Both devices must be signed into the same Apple ID
- **Connectivity**: Bluetooth and Wi-Fi must be enabled on both devices; they should be on the same Wi-Fi network or in close range
