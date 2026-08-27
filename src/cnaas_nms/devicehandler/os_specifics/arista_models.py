from typing import Optional, TYPE_CHECKING

from cnaas_nms.db.device import CpuArchitecture
from cnaas_nms.db.settings import get_settings

if TYPE_CHECKING:
    from cnaas_nms.db.device import Device

# List of models that require/prefer 32bit images
# All other models and all future models should use 64bit images according to Arista SE
models_32bit = [
    "CCS-710P-12",
    "CCS-710P-16P",
    "CCS-720DF-48Y-2F",
    "CCS-720DF-48Y-F",
    "CCS-720DP-24S-2F",
    "CCS-720DP-24S-F",
    "CCS-720DP-48S-2F",
    "CCS-720DP-48S-F",
    "CCS-720DT-24S-2F",
    "CCS-720DT-24S-F",
    "CCS-720XP-24Y6-F",
    "CCS-720XP-24Y6-R",
    "CCS-720XP-24ZY4-F",
    "CCS-720XP-48Y6-F",
    "CCS-720XP-48Y6-R",
    "CCS-720XP-48ZC2-F",
    "CCS-720XP-96ZC2-F",
    "CCS-722XPM-48Y4-F",
    "CCS-722XPM-48ZY8-F",
    "DCS-7010TX-48-DC-F",
    "DCS-7010TX-48-DC-R",
    "DCS-7010TX-48-F",
    "DCS-7010TX-48-R",
    "DCS-7050CX3-32S-F",
    "DCS-7050CX3-32S-R",
    "DCS-7050CX3M-32S-F",
    "DCS-7050CX3M-32S-R",
    "DCS-7050SX3-48C8-F",
    "DCS-7050SX3-48C8-R",
    "DCS-7050SX3-48YC12-F",
    "DCS-7050SX3-48YC8-F",
    "DCS-7050SX3-48YC8-R",
    "DCS-7050SX3-96YC8-F",
    "DCS-7050SX3-96YC8-R",
    "DCS-7280CR3-32D4-F",
    "DCS-7280CR3-32D4-R",
    "DCS-7280CR3-32P4-F",
    "DCS-7280CR3-32P4-R",
    "DCS-7280DR3-24-F",
    "DCS-7280PR3-24-F",
    "DCS-7280QR-C36-F",
    "DCS-7280QR-C36-R",
    "DCS-7280QR-C72-F",
    "DCS-7280QR-C72-R",
    "DCS-7280QRA-C36S-F",
    "DCS-7280QRA-C36S-R",
    "DCS-7280SR-48C6-F",
    "DCS-7280SR-48C6-R",
    "DCS-7280SR2-48YC6-F",
    "DCS-7280SR2-48YC6-R",
    "DCS-7280SR2A-48YC6-F",
    "DCS-7280SR2A-48YC6-R",
    "DCS-7280SR3-40YC6-F",
    "DCS-7280SR3-40YC6-R",
    "DCS-7280SR3-48YC8-F",
    "DCS-7280SR3-48YC8-R",
    "DCS-7280SR3E-40YC6-F",
    "DCS-7280SR3E-40YC6-R",
    "DCS-7280SR3M-48YC8-F",
    "DCS-7280SR3M-48YC8-R",
    "DCS-7280SRA-48C6-F",
    "DCS-7280SRA-48C6-R",
    "DCS-7280TR-48C6-F",
    "DCS-7280TR-48C6-R",
    "DCS-7280TR3-40C6-F",
    "DCS-7280TR3-40C6-R",
    "DCS-7280TRA-48C6-F",
    "DCS-7280TRA-48C6-R",
]

models_arm = [
    "CCS-710XP-12TH-2S",
    "CCS-710XP-28TNH-2S",
]


def detect_arch(dev: "Device") -> Optional[CpuArchitecture]:
    """Get architecture type for an Arista device.

    Checks device settings for additional 32bit or ARM model overrides.
    Returns None for non-EOS devices.
    """
    if dev.platform != "eos":
        return None

    dev_settings, _ = get_settings(dev, dev.device_type)

    # 32bit in settings?
    arch_models_32bit = models_32bit
    if dev_settings and "arista_models_32bit" in dev_settings and dev_settings["arista_models_32bit"] is not None:
        arch_models_32bit = arch_models_32bit + dev_settings["arista_models_32bit"]

    # ARM in settings?
    arch_models_arm = models_arm
    if dev_settings and "arista_models_arm" in dev_settings and dev_settings["arista_models_arm"] is not None:
        arch_models_arm = arch_models_arm + dev_settings["arista_models_arm"]

    if dev.model in arch_models_32bit:
        return CpuArchitecture.X86_32
    elif dev.model in arch_models_arm:
        return CpuArchitecture.ARM64
    else:
        return CpuArchitecture.X86_64
