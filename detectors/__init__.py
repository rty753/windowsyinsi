"""Privacy device detectors package."""

from detectors.hardware import (
    CameraDetector,
    MicrophoneDetector,
    BluetoothDetector,
    WiFiDetector,
    USBCameraDetector,
    SensorDetector,
)
from detectors.software import (
    LocationDetector,
    RDPDetector,
    TelemetryDetector,
    CortanaDetector,
    AdvertisingIDDetector,
    BackgroundAppsDetector,
    ClipboardDetector,
)
from detectors.processes import ProcessDetector

ALL_DETECTORS = [
    CameraDetector,
    MicrophoneDetector,
    LocationDetector,
    BluetoothDetector,
    WiFiDetector,
    USBCameraDetector,
    SensorDetector,
    RDPDetector,
    TelemetryDetector,
    CortanaDetector,
    AdvertisingIDDetector,
    BackgroundAppsDetector,
    ClipboardDetector,
]
