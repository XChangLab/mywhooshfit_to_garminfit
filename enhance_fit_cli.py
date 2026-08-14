#!/usr/bin/env python3
"""
enhance_fit_cli.py — CLI tool to modify MyWhoosh FIT files for Garmin upload.

Usage: python enhance_fit_cli.py <input.fit> <output.fit> [ftp]

Outputs JSON to stdout:
  {"success": true, "output": "/path/to/output.fit"}
  {"success": false, "error": "error message"}
"""

import json
import logging
import sys
from pathlib import Path

from fit_tool.fit_file import FitFile
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.file_creator_message import FileCreatorMessage
from fit_tool.profile.messages.device_info_message import DeviceInfoMessage
from fit_tool.profile.messages.sport_message import SportMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.profile_type import (
    FileType,
    Manufacturer,
    Sport,
    SubSport,
    Intensity,
    SessionTrigger,
)

logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger(__name__)


def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _calc_np(power_values: list[float], window: int = 30) -> float:
    """计算 Normalized Power：30秒滚动均值 → 4次方均值 → 4次方根。"""
    n = len(power_values)
    if n == 0:
        return 0.0
    if n < window:
        return _avg(power_values)
    rolling = [_avg(power_values[i - window + 1: i + 1]) for i in range(window - 1, n)]
    return (sum(p ** 4 for p in rolling) / len(rolling)) ** 0.25


def _set_field(msg, field_name: str, value):
    """安全设置消息字段，静默跳过不支持的字段。"""
    try:
        setattr(msg, field_name, value)
    except Exception:
        pass


def enhance_fit(input_path: Path, output_path: Path,
                ftp: float = 0,
                device_product_id: int = 3927) -> bool:  # Edge 1040（fit_tool 0.9.15 无此枚举）
    """
    增强单个 FIT 文件：设备伪装 + 平均值填充 + NP/IF/TSS 计算。

    Args:
        input_path: 源 FIT 文件路径。
        output_path: 输出 FIT 文件路径。
        ftp: 功能阈值功率（瓦特），0 表示跳过 NP/IF/TSS。
        device_product_id: 伪装设备 ID（默认 Edge 1040 = 3927）。

    Returns:
        True 表示成功。
    """
    with open(input_path, "rb") as f:
        raw_bytes = f.read()
    fit_file = FitFile.from_bytes(raw_bytes, check_crc=False)

    cadence_vals: list[float] = []
    power_vals: list[float] = []
    hr_vals: list[float] = []

    all_power: list[float] = []
    all_hr: list[float] = []
    all_cadence: list[float] = []

    for record in fit_file.records:
        msg = record.message
        msg_type = type(msg)

        # ── FileId: 伪装为 Garmin Edge 1040 ────────────────────────────
        if msg_type is FileIdMessage:
            msg.type = FileType.ACTIVITY
            msg.manufacturer = Manufacturer.GARMIN
            msg.product = device_product_id
            continue

        # ── FileCreator: 原样保留 ─────────────────────────────────
        if msg_type is FileCreatorMessage:
            continue

        # ── DeviceInfo: 伪装为 Garmin Edge 1040 ────────────────────────
        if msg_type is DeviceInfoMessage:
            msg.manufacturer = Manufacturer.GARMIN
            msg.product = device_product_id
            msg.software_version = 27.10  # Edge 1040 固件版本
            continue

        # ── Sport: 设置为骑行 + 虚拟活动 ──────────────────────────
        if msg_type is SportMessage:
            msg.sport = Sport.CYCLING
            msg.sub_sport = SubSport.VIRTUAL_ACTIVITY
            continue

        # ── Record: 采集数据点 ────────────────────────────────────
        if msg_type is RecordMessage:
            try:
                v = msg.cadence
                if v and v > 0:
                    cadence_vals.append(float(v))
                    all_cadence.append(float(v))
            except (AttributeError, ValueError):
                pass
            try:
                v = msg.power
                if v and v > 0:
                    power_vals.append(float(v))
                    all_power.append(float(v))
            except (AttributeError, ValueError):
                pass
            try:
                v = msg.heart_rate
                if v and v > 0:
                    hr_vals.append(float(v))
                    all_hr.append(float(v))
            except (AttributeError, ValueError):
                pass
            continue

        # ── Lap: 标记强度 + 填充平均值 ───────────────────────────
        if msg_type is LapMessage:
            _set_field(msg, "intensity", Intensity.ACTIVE)
            if not getattr(msg, "avg_cadence", None) and cadence_vals:
                _set_field(msg, "avg_cadence", round(_avg(cadence_vals)))
            if not getattr(msg, "avg_power", None) and power_vals:
                _set_field(msg, "avg_power", round(_avg(power_vals)))
            if not getattr(msg, "max_power", None) and power_vals:
                _set_field(msg, "max_power", round(max(power_vals)))
            if not getattr(msg, "avg_heart_rate", None) and hr_vals:
                _set_field(msg, "avg_heart_rate", round(_avg(hr_vals)))
            if not getattr(msg, "max_heart_rate", None) and hr_vals:
                _set_field(msg, "max_heart_rate", round(max(hr_vals)))
            cadence_vals, power_vals, hr_vals = [], [], []
            continue

        # ── Session: 设置运动类型 + 强度指标 ────────────────────
        if msg_type is SessionMessage:
            msg.sport = Sport.CYCLING
            msg.sub_sport = SubSport.VIRTUAL_ACTIVITY
            _set_field(msg, "trigger", SessionTrigger.ACTIVITY_END)

            if not getattr(msg, "avg_cadence", None) and all_cadence:
                _set_field(msg, "avg_cadence", round(_avg(all_cadence)))
            if not getattr(msg, "avg_power", None) and all_power:
                _set_field(msg, "avg_power", round(_avg(all_power)))
            if not getattr(msg, "max_power", None) and all_power:
                _set_field(msg, "max_power", round(max(all_power)))
            if not getattr(msg, "avg_heart_rate", None) and all_hr:
                _set_field(msg, "avg_heart_rate", round(_avg(all_hr)))
            if not getattr(msg, "max_heart_rate", None) and all_hr:
                _set_field(msg, "max_heart_rate", round(max(all_hr)))

            # total_work (焦耳 = 平均功率 × 运动秒数)
            try:
                total_timer = (getattr(msg, "total_timer_time", None)
                               or getattr(msg, "total_elapsed_time", None))
                avg_pwr = getattr(msg, "avg_power", None) or _avg(all_power)
                if avg_pwr and total_timer and avg_pwr > 0:
                    _set_field(msg, "total_work", int(avg_pwr * total_timer))
            except Exception:
                pass

            # NP / IF / TSS
            if ftp > 0 and len(all_power) > 0:
                np = _calc_np(all_power)
                if_val = np / ftp
                _set_field(msg, "normalized_power", round(np))
                _set_field(msg, "intensity_factor", round(if_val, 3))
                try:
                    total_seconds = (getattr(msg, "total_timer_time", 0)
                                     or getattr(msg, "total_elapsed_time", 0))
                    if total_seconds > 0:
                        tss = (total_seconds * np * if_val) / (ftp * 3600) * 100
                        _set_field(msg, "training_stress_score", round(tss))
                except Exception:
                    pass
            continue

        # ── Event / Activity / 其余：原样保留 ──────────────────
        continue

    fit_file.crc = None
    fit_file.to_file(str(output_path))
    return True


def main():
    if len(sys.argv) < 3:
        result = {
            "success": False,
            "error": "Usage: python enhance_fit_cli.py <input.fit> <output.fit> [ftp]"
        }
        print(json.dumps(result))
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    ftp = float(sys.argv[3]) if len(sys.argv) > 3 else 0

    if not input_path.exists():
        result = {"success": False, "error": f"Input file not found: {input_path}"}
        print(json.dumps(result))
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        enhance_fit(input_path, output_path, ftp=ftp)
        result = {"success": True, "output": str(output_path)}
        print(json.dumps(result))
    except Exception as e:
        result = {"success": False, "error": str(e)}
        print(json.dumps(result))
        sys.exit(1)


if __name__ == "__main__":
    main()
