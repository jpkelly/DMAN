"""Build the codeless DSANInterfaceStringFix.kext (Info.plist only, no executable).

Merges kUSBDescriptorOverride onto the VC-2000PC's IOUSBHostDevice via Apple's
AppleUSBHostMergeProperties, the same pattern Apple's IOBluetoothFamily uses.
The override is the dongle's own configuration descriptor with iInterface
changed from 0x5C (92) to 0, so macOS never requests string 92, which hangs
the dongle (docs/hid-investigation.md). The device itself is not modified.
"""
import plistlib
import shutil
from pathlib import Path

# Configuration descriptor read from the dongle (0483:101A, bcdDevice 0x0100).
ORIGINAL = bytes.fromhex(
    "09 02 22 00 01 01 00 a0 32"      # configuration
    "09 04 00 00 01 03 00 00 5c"      # interface 0, HID, iInterface 0x5C
    "09 21 00 01 00 01 22 2f 00"      # HID descriptor
    "07 05 81 03 08 00 0a")           # interrupt IN 0x81
I_INTERFACE_OFFSET = 9 + 8
assert len(ORIGINAL) == 34 and ORIGINAL[I_INTERFACE_OFFSET] == 0x5C
PATCHED = ORIGINAL[:I_INTERFACE_OFFSET] + b"\x00" + ORIGINAL[I_INTERFACE_OFFSET + 1:]

BUNDLE_ID = "local.dman.DSANInterfaceStringFix"
INFO = {
    "CFBundleDevelopmentRegion": "English",
    "CFBundleIdentifier": BUNDLE_ID,
    "CFBundleInfoDictionaryVersion": "6.0",
    "CFBundleName": "DSAN VC-2000PC interface string fix",
    "CFBundlePackageType": "KEXT",
    "CFBundleShortVersionString": "1.0",
    "CFBundleVersion": "1.0",
    "OSBundleRequired": "Root",
    "IOKitPersonalities": {
        "DSAN VideoClock USB Interface iInterface fix": {
            "CFBundleIdentifier": "com.apple.driver.AppleUSBHostMergeProperties",
            "IOClass": "AppleUSBHostMergeProperties",
            "IOProviderClass": "IOUSBHostDevice",
            "idVendor": 0x0483,
            "idProduct": 0x101A,
            "bcdDevice": 0x0100,
            "IOProviderMergeProperties": {
                "kUSBDescriptorOverride": {"descriptor": PATCHED, "index": 0, "languageID": 0},
            },
        },
    },
}


def build(out_dir):
    kext = Path(out_dir) / "DSANInterfaceStringFix.kext"
    if kext.exists():
        shutil.rmtree(kext)
    (kext / "Contents").mkdir(parents=True)
    with open(kext / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump(INFO, f)
    return kext


if __name__ == "__main__":
    kext = build(Path(__file__).parent / "build")
    print(kext)
    print("original:", ORIGINAL.hex(" "))
    print("patched: ", PATCHED.hex(" "))
