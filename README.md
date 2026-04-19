# Continuity Camera MCP Server v1.0

An MCP (Model Context Protocol) server that captures photos from an iPhone via macOS Continuity Camera. Created for agentic IoT projects where the agent can see the state of the project — great for UI design, inspecting hardware, reading screens, checking wiring, and more.

## How It Works

The server uses macOS **Continuity Camera** to wirelessly access your iPhone's camera from Python via the `AVFoundation` framework (through PyObjC). It exposes a single MCP tool — `capture_photo` — that captures a high-resolution JPEG and returns it as an image.

Key features:
- **Hardware zoom** via the iPhone's `videoZoomFactor` (up to 16x depending on device)
- **Software crop** for repositioning the frame to any region of the image
- **stdio transport** for reliable integration with VS Code (avoids threading issues with HTTP)

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
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Verify your iPhone is detected:

   ```bash
   python -c "
   import AVFoundation
   types = [AVFoundation.AVCaptureDeviceTypeBuiltInWideAngleCamera,
            AVFoundation.AVCaptureDeviceTypeExternalUnknown]
   s = AVFoundation.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
       types, AVFoundation.AVMediaTypeVideo, AVFoundation.AVCaptureDevicePositionUnspecified)
   for d in s.devices():
       print(f'{d.localizedName()} (continuity={d.isContinuityCamera()})')
   "
   ```

   You should see your iPhone listed with `continuity=True`.

## Adding to VS Code

1. Create `.vscode/mcp.json` in your workspace (or any workspace where you want camera access):

   ```json
   {
     "servers": {
       "iPhone-Camera-Server": {
         "type": "stdio",
         "command": "/path/to/camera-server/.venv/bin/python",
         "args": ["/path/to/camera-server/camera_server.py"]
       }
     }
   }
   ```

   Replace `/path/to/camera-server` with the actual path to this repository.

2. Start the MCP server from the VS Code Command Palette:

   - Press **Cmd+Shift+P**
   - Type **MCP: List Servers**
   - Select **iPhone-Camera-Server** and click **Start**

3. The `capture_photo` tool will now be available to GitHub Copilot in chat.

### Why stdio and not HTTP?

The server **must** use stdio transport. The HTTP transport runs request handlers on worker threads, but macOS `AVFoundation` requires `NSRunLoop` callbacks to fire on the thread that initiated the capture session. With stdio, everything runs on the main thread and callbacks work reliably.

## Usage

Once configured, you can ask Copilot to capture and analyse photos:

- *"Capture a photo and describe what you see"*
- *"Zoom in on the LCD panel"*
- *"Take a photo at 3x zoom"*

### Tool Parameters

| Parameter | Type   | Default | Description |
|-----------|--------|---------|-------------|
| `label`   | string | `"iot_device"` | A label for the capture |
| `zoom`    | float  | `1.0`   | Hardware zoom factor (1.0 = no zoom, 2.0 = 2x, etc.) |
| `crop_x`  | float  | `0.5`   | Horizontal crop center (0.0 = left, 0.5 = center, 1.0 = right) |
| `crop_y`  | float  | `0.5`   | Vertical crop center (0.0 = top, 0.5 = center, 1.0 = bottom) |

- **`zoom`** applies hardware zoom on the iPhone sensor — higher quality than digital crop
- **`crop_x` / `crop_y`** apply a software crop to reposition the frame (useful for targeting objects near the edges)

### Examples

Full image, no zoom:
```
capture_photo(label="overview")
```

3x zoom on center:
```
capture_photo(label="detail", zoom=3.0)
```

2x zoom, targeting bottom-right corner:
```
capture_photo(label="corner", zoom=2.0, crop_x=0.9, crop_y=0.8)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No iPhone found" | Ensure iPhone is nearby, unlocked, and on the same Apple ID. Toggle Bluetooth off/on. |
| "Capture timed out" | Restart the MCP server. The iPhone may need to re-establish the Continuity Camera connection. |
| Zoom not working | Restart the MCP server — code changes require a server restart since stdio servers are long-lived processes. |
| Server crashes (exit code 134) | This is SIGABRT, usually from AVFoundation threading issues. Ensure you're using stdio transport, not HTTP. |
