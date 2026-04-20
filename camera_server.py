import io
import time
import objc
import AVFoundation
from Foundation import NSObject, NSRunLoop, NSDate
from PIL import Image as PILImage
from mcp.server.fastmcp import FastMCP, Image

# Create the MCP Server
mcp = FastMCP(
    "iPhone-Camera-Server",
    instructions="Use capture_photo directly for normal operation. Only call list_cameras if the user explicitly asks for device status, or if a capture fails with a camera-availability error and you need diagnostics."
)

class PhotoDelegate(NSObject):
    """Helper class to handle the asynchronous callback from macOS"""
    def init(self):
        self = objc.super(PhotoDelegate, self).init()
        if self is None:
            return None
        self.data = None
        self.done = False
        return self

    def captureOutput_didFinishProcessingPhoto_error_(self, output, photo, error):
        if error:
            print(f"Capture error: {error}")
        else:
            self.data = photo.fileDataRepresentation()
        self.done = True

def get_iphone_camera():
    """Finds the Continuity Camera device"""
    device_types = [
        AVFoundation.AVCaptureDeviceTypeBuiltInWideAngleCamera,
        AVFoundation.AVCaptureDeviceTypeExternalUnknown
    ]
    session = AVFoundation.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
        device_types, AVFoundation.AVMediaTypeVideo, AVFoundation.AVCaptureDevicePositionUnspecified
    )
    return next((d for d in session.devices() if d.isContinuityCamera()), None)

@mcp.tool()
def list_cameras() -> str:
    """Lists all available video capture devices and their Continuity Camera status."""
    device_types = [
        AVFoundation.AVCaptureDeviceTypeBuiltInWideAngleCamera,
        AVFoundation.AVCaptureDeviceTypeExternalUnknown
    ]
    session = AVFoundation.AVCaptureDeviceDiscoverySession.discoverySessionWithDeviceTypes_mediaType_position_(
        device_types, AVFoundation.AVMediaTypeVideo, AVFoundation.AVCaptureDevicePositionUnspecified
    )
    devices = session.devices()
    if not devices:
        return "No video capture devices found."
    lines = []
    for d in devices:
        continuity = "Yes" if d.isContinuityCamera() else "No"
        lines.append(f"- {d.localizedName()} (Continuity Camera: {continuity})")
    return "\n".join(lines)

@mcp.tool()
def capture_photo(label: str = "iot_device", zoom: float = 1.0, crop_x: float = 0.5, crop_y: float = 0.5, resolution: int = 1080, rotate: int = 0, pre_capture_delay_seconds: float = 0.0) -> Image:
    """
    Captures a photo from the connected iPhone camera.
    Use this to inspect hardware, read screens, or check wiring.

    Args:
        label: A label for the capture.
        zoom: Software zoom factor (1.0 = no zoom, 2.0 = 2x, etc).
        crop_x: Horizontal center of the crop region (0.0 = left edge, 0.5 = center, 1.0 = right edge).
        crop_y: Vertical center of the crop region (0.0 = top edge, 0.5 = center, 1.0 = bottom edge).
        resolution: Max dimension in pixels for the returned image (default 1080). Lower values reduce LLM token cost.
        rotate: Rotate the image clockwise in degrees (0, 90, 180, or 270).
        pre_capture_delay_seconds: Wait this many seconds immediately before taking the photo.
    """
    iphone = get_iphone_camera()
    if not iphone:
        return "Error: No iPhone found. Ensure Continuity Camera is enabled."

    # Setup Session
    session = AVFoundation.AVCaptureSession.alloc().init()
    session.setSessionPreset_(AVFoundation.AVCaptureSessionPresetPhoto)
    
    input_device = AVFoundation.AVCaptureDeviceInput.deviceInputWithDevice_error_(iphone, None)[0]
    if not session.canAddInput_(input_device):
        return "Error: Could not add iPhone as input."
    session.addInput_(input_device)
    
    output = AVFoundation.AVCapturePhotoOutput.alloc().init()
    session.addOutput_(output)

    session.startRunning()

    # Warm up
    warmup_start = time.time()
    while time.time() - warmup_start < 3.0:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))

    # Always reset hardware zoom so captures are fully controlled by the
    # software pipeline below and no stale device zoom persists between calls.
    success, err = iphone.lockForConfiguration_(None)
    if success:
        iphone.setVideoZoomFactor_(1.0)
        iphone.unlockForConfiguration()
        # Let the device settle after resetting zoom.
        settle_start = time.time()
        while time.time() - settle_start < 1.0:
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))

    # Optional delay so external firmware/UI has time to render before capture.
    if pre_capture_delay_seconds > 0:
        delay_start = time.time()
        while time.time() - delay_start < pre_capture_delay_seconds:
            NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))

    # Capture Logic
    delegate = PhotoDelegate.alloc().init()
    settings = AVFoundation.AVCapturePhotoSettings.photoSettings()
    output.capturePhotoWithSettings_delegate_(settings, delegate)

    # Wait for the wireless handoff (max 15s)
    timeout = 15.0
    start = time.time()
    while not delegate.done and (time.time() - start < timeout):
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))

    session.stopRunning()

    if delegate.data:
        img = PILImage.open(io.BytesIO(bytes(delegate.data)))

        # Rotate first so crop coordinates are relative to the final image
        if rotate in (90, 180, 270):
            img = img.rotate(-rotate, expand=True)

        # Software crop for zooming and repositioning in the final orientation.
        # Keep the user-facing zoom control a bit gentler so moderate values
        # still preserve context for framing.
        requested_zoom = max(1.0, float(zoom))
        software_zoom = 1.0 + (requested_zoom - 1.0) * 0.65
        if crop_x != 0.5 or crop_y != 0.5 or software_zoom > 1.001:
            w, h = img.size
            crop_ratio = max(0.5, min(1.0, 1.0 / software_zoom))
            crop_w, crop_h = w * crop_ratio, h * crop_ratio
            cx = max(crop_w / 2, min(crop_x * w, w - crop_w / 2))
            cy = max(crop_h / 2, min(crop_y * h, h - crop_h / 2))
            box = (int(cx - crop_w / 2), int(cy - crop_h / 2),
                   int(cx + crop_w / 2), int(cy + crop_h / 2))
            img = img.crop(box)

        # Resize to limit LLM token cost, but preserve more detail for
        # heavily zoomed/cropped images where downsampling is more damaging.
        effective_resolution = int(resolution)
        if software_zoom >= 1.5:
            effective_resolution = min(4096, int(resolution * 2))
        elif software_zoom >= 1.25:
            effective_resolution = min(4096, int(resolution * 1.5))
        img.thumbnail((effective_resolution, effective_resolution), PILImage.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return Image(data=buf.getvalue(), format="jpeg")
    
    return "Error: Capture timed out or failed."

if __name__ == "__main__":
    mcp.run(transport="stdio")
