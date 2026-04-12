#!/usr/bin/env python3
"""
WAB11 Status Report Generator

Reads all sensor values from the WAB11 heat pump controller
and generates a comprehensive status report.

Usage:
    python scripts/report.py --host 192.168.1.100
    python scripts/report.py --host 192.168.1.100 --json
    python scripts/report.py --host 192.168.1.100 --output report.txt
    python scripts/report.py --host 192.168.1.100 --csv data.csv
    python scripts/report.py --host 192.168.1.100 --csv data.csv --interval 5
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from wab11 import WAB11SyncClient, SystemMode, OperatingState


def format_temp(temp) -> str:
    """Format a Temperature object for display."""
    if temp is None:
        return "N/A"
    celsius = temp.celsius if hasattr(temp, 'celsius') else temp
    if celsius is None:
        return "N/A"
    return f"{celsius:.1f}°C"


def format_bool(value: bool) -> str:
    """Format a boolean for display."""
    return "Yes" if value else "No"


def get_status_emoji(state: OperatingState) -> str:
    """Get an emoji representing the operating state."""
    emoji_map = {
        OperatingState.HEATING: "🔥",
        OperatingState.COOLING: "❄️",
        OperatingState.HOT_WATER: "🚿",
        OperatingState.DEFROST: "🧊",
        OperatingState.STANDBY: "💤",
        OperatingState.SUMMER: "☀️",
        OperatingState.FROST_PROTECTION: "🥶",
        OperatingState.EVU_LOCK: "🔒",
        OperatingState.SG_MAXIMUM: "⚡",
    }
    return emoji_map.get(state, "•")


def collect_sensor_data(client: WAB11SyncClient) -> dict[str, Any]:
    """Collect all sensor data from the WAB11."""
    client.sync()
    client.sync_energy()
    
    data = {
        "timestamp": datetime.now().isoformat(),
        "host": client.host,
        "system": {
            "mode": client.system.system_mode.name,
            "operating_state": client.system.operating_state.name,
            "outdoor_temp_1": client.system.outdoor_temp_1.celsius,
            "outdoor_temp_2": client.system.outdoor_temp_2.celsius,
            "error_code": client.system.error_code,
            "warning_code": client.system.warning_code,
            "is_error_free": client.system.is_error_free,
            "has_error": client.system.has_error,
            "has_warning": client.system.has_warning,
            "power_request_watts": client.system.power_request_watts,
        },
        "heating_circuits": [],
        "hot_water": {
            "is_configured": client.hot_water.is_configured,
            "temperature": client.hot_water.temperature.celsius,
            "setpoint_effective": client.hot_water.setpoint_effective.celsius,
            "setpoint_normal": client.hot_water.setpoint_normal.celsius,
            "setpoint_setback": client.hot_water.setpoint_setback.celsius,
            "is_push_active": client.hot_water.is_push_active,
            "push_minutes": client.hot_water.push_minutes,
            "is_charging": client.hot_water.is_charging,
            "status": client.hot_water.status.name if hasattr(client.hot_water.status, 'name') else str(client.hot_water.status),
        },
        "heat_pump": {
            "is_configured": client.heat_pump.is_configured,
            "operating_state": client.heat_pump.operating_state.name if hasattr(client.heat_pump.operating_state, 'name') else str(client.heat_pump.operating_state),
            "is_error_free": client.heat_pump.is_error_free,
            "power_request_percent": client.heat_pump.power_request_percent,
            "flow_temp_b4": client.heat_pump.flow_temp_b4.celsius,
            "return_temp": client.heat_pump.return_temp.celsius,
            "evaporator_temp": client.heat_pump.evaporator_temp.celsius,
            "suction_gas_temp": client.heat_pump.suction_gas_temp.celsius,
            "separator_temp_b2": client.heat_pump.separator_temp_b2.celsius,
            "buffer_temp_b11": client.heat_pump.buffer_temp_b11.celsius,
            "sum_flow_b7": client.heat_pump.sum_flow_b7.celsius,
            "spread": client.heat_pump.spread,
            "supports_cooling": client.heat_pump.supports_cooling,
            "is_quiet_mode": client.heat_pump.is_quiet_mode,
            "pump_power_heating": client.heat_pump.pump_power_heating,
            "pump_power_cooling": client.heat_pump.pump_power_cooling,
            "pump_power_hot_water": client.heat_pump.pump_power_hot_water,
        },
        "secondary_heat": {
            "is_wez2_configured": client.secondary_heat.is_wez2_configured,
            "is_wez2_active": client.secondary_heat.is_wez2_active,
            "is_e1_configured": client.secondary_heat.is_e1_configured,
            "is_e1_active": client.secondary_heat.is_e1_active,
            "is_e2_configured": client.secondary_heat.is_e2_configured,
            "is_e2_active": client.secondary_heat.is_e2_active,
            "operating_hours_wez2": client.secondary_heat.operating_hours_wez2,
            "operating_hours_e1": client.secondary_heat.operating_hours_e1,
            "operating_hours_e2": client.secondary_heat.operating_hours_e2,
            "limit_temp": client.secondary_heat.limit_temp.celsius,
            "bivalence_temp_heating": client.secondary_heat.bivalence_temp_heating.celsius,
            "bivalence_temp_hot_water": client.secondary_heat.bivalence_temp_hot_water.celsius,
        },
        "inputs": {
            "sg_ready_state": client.inputs.sg_ready_state.name,
            "sg_ready_1": client.inputs.sg_ready_1,
            "sg_ready_2": client.inputs.sg_ready_2,
            "is_evu_lock": client.inputs.is_evu_lock,
            "is_sg_maximum": client.inputs.is_sg_maximum,
            "active_inputs": client.inputs.get_active_inputs(),
        },
        "energy": {
            "total": {
                "today": client.energy.total.today,
                "yesterday": client.energy.total.yesterday,
                "month": client.energy.total.month,
                "year": client.energy.total.year,
            },
            "heating": {
                "today": client.energy.heating.today,
                "yesterday": client.energy.heating.yesterday,
                "month": client.energy.heating.month,
                "year": client.energy.heating.year,
            },
            "hot_water": {
                "today": client.energy.hot_water.today,
                "yesterday": client.energy.hot_water.yesterday,
                "month": client.energy.hot_water.month,
                "year": client.energy.hot_water.year,
            },
            "cooling": {
                "today": client.energy.cooling.today,
                "yesterday": client.energy.cooling.yesterday,
                "month": client.energy.cooling.month,
                "year": client.energy.cooling.year,
            },
        },
    }
    
    # Collect heating circuit data
    for i, hk in enumerate(client.heating_circuits, 1):
        hk_data = {
            "id": i,
            "is_configured": hk.is_configured,
        }
        if hk.is_configured:
            hk_data.update({
                "config": hk.config.name if hasattr(hk.config, 'name') else str(hk.config),
                "mode": hk.mode.name if hasattr(hk.mode, 'name') else str(hk.mode),
                "room_temp": hk.room_temp.celsius,
                "room_setpoint_effective": hk.room_setpoint_effective.celsius,
                "room_humidity": hk.room_humidity,
                "flow_temp": hk.flow_temp.celsius,
                "flow_setpoint": hk.flow_setpoint.celsius,
                "setpoint_comfort": hk.setpoint_comfort.celsius,
                "setpoint_normal": hk.setpoint_normal.celsius,
                "setpoint_setback": hk.setpoint_setback.celsius,
                "party_pause_info": hk.party_pause_info,
                "is_party_active": hk.is_party_active,
                "is_pause_active": hk.is_pause_active,
                "is_heating": hk.is_heating,
                "is_cooling": hk.is_cooling,
                "heating_curve_slope": hk.heating_curve_slope,
            })
        data["heating_circuits"].append(hk_data)
    
    return data


def flatten_data_for_csv(data: dict[str, Any]) -> dict[str, Any]:
    """Flatten the nested data structure into a single dictionary for CSV output."""
    flat = {
        "timestamp": data["timestamp"],
        "host": data["host"],
        # System
        "system_mode": data["system"]["mode"],
        "operating_state": data["system"]["operating_state"],
        "outdoor_temp_1": data["system"]["outdoor_temp_1"],
        "outdoor_temp_2": data["system"]["outdoor_temp_2"],
        "error_code": data["system"]["error_code"],
        "warning_code": data["system"]["warning_code"],
        "is_error_free": data["system"]["is_error_free"],
        "has_error": data["system"]["has_error"],
        "has_warning": data["system"]["has_warning"],
        "power_request_watts": data["system"]["power_request_watts"],
        # Hot water
        "ww_is_configured": data["hot_water"]["is_configured"],
        "ww_temperature": data["hot_water"]["temperature"],
        "ww_setpoint_effective": data["hot_water"]["setpoint_effective"],
        "ww_setpoint_normal": data["hot_water"]["setpoint_normal"],
        "ww_setpoint_setback": data["hot_water"]["setpoint_setback"],
        "ww_is_push_active": data["hot_water"]["is_push_active"],
        "ww_push_minutes": data["hot_water"]["push_minutes"],
        "ww_is_charging": data["hot_water"]["is_charging"],
        "ww_status": data["hot_water"]["status"],
        # Heat pump
        "wp_is_configured": data["heat_pump"]["is_configured"],
        "wp_operating_state": data["heat_pump"]["operating_state"],
        "wp_is_error_free": data["heat_pump"]["is_error_free"],
        "wp_power_request_percent": data["heat_pump"]["power_request_percent"],
        "wp_flow_temp_b4": data["heat_pump"]["flow_temp_b4"],
        "wp_return_temp": data["heat_pump"]["return_temp"],
        "wp_evaporator_temp": data["heat_pump"]["evaporator_temp"],
        "wp_suction_gas_temp": data["heat_pump"]["suction_gas_temp"],
        "wp_separator_temp_b2": data["heat_pump"]["separator_temp_b2"],
        "wp_buffer_temp_b11": data["heat_pump"]["buffer_temp_b11"],
        "wp_sum_flow_b7": data["heat_pump"]["sum_flow_b7"],
        "wp_spread": data["heat_pump"]["spread"],
        "wp_supports_cooling": data["heat_pump"]["supports_cooling"],
        "wp_is_quiet_mode": data["heat_pump"]["is_quiet_mode"],
        "wp_pump_power_heating": data["heat_pump"]["pump_power_heating"],
        "wp_pump_power_cooling": data["heat_pump"]["pump_power_cooling"],
        "wp_pump_power_hot_water": data["heat_pump"]["pump_power_hot_water"],
        # Secondary heat
        "sh_is_wez2_configured": data["secondary_heat"]["is_wez2_configured"],
        "sh_is_wez2_active": data["secondary_heat"]["is_wez2_active"],
        "sh_is_e1_configured": data["secondary_heat"]["is_e1_configured"],
        "sh_is_e1_active": data["secondary_heat"]["is_e1_active"],
        "sh_is_e2_configured": data["secondary_heat"]["is_e2_configured"],
        "sh_is_e2_active": data["secondary_heat"]["is_e2_active"],
        "sh_operating_hours_wez2": data["secondary_heat"]["operating_hours_wez2"],
        "sh_operating_hours_e1": data["secondary_heat"]["operating_hours_e1"],
        "sh_operating_hours_e2": data["secondary_heat"]["operating_hours_e2"],
        "sh_limit_temp": data["secondary_heat"]["limit_temp"],
        "sh_bivalence_temp_heating": data["secondary_heat"]["bivalence_temp_heating"],
        "sh_bivalence_temp_hot_water": data["secondary_heat"]["bivalence_temp_hot_water"],
        # Inputs
        "sg_ready_state": data["inputs"]["sg_ready_state"],
        "sg_ready_1": data["inputs"]["sg_ready_1"],
        "sg_ready_2": data["inputs"]["sg_ready_2"],
        "is_evu_lock": data["inputs"]["is_evu_lock"],
        "is_sg_maximum": data["inputs"]["is_sg_maximum"],
        "active_inputs": ",".join(data["inputs"]["active_inputs"]) if data["inputs"]["active_inputs"] else "",
        # Energy
        "energy_total_today": data["energy"]["total"]["today"],
        "energy_total_yesterday": data["energy"]["total"]["yesterday"],
        "energy_total_month": data["energy"]["total"]["month"],
        "energy_total_year": data["energy"]["total"]["year"],
        "energy_heating_today": data["energy"]["heating"]["today"],
        "energy_heating_yesterday": data["energy"]["heating"]["yesterday"],
        "energy_heating_month": data["energy"]["heating"]["month"],
        "energy_heating_year": data["energy"]["heating"]["year"],
        "energy_hot_water_today": data["energy"]["hot_water"]["today"],
        "energy_hot_water_yesterday": data["energy"]["hot_water"]["yesterday"],
        "energy_hot_water_month": data["energy"]["hot_water"]["month"],
        "energy_hot_water_year": data["energy"]["hot_water"]["year"],
        "energy_cooling_today": data["energy"]["cooling"]["today"],
        "energy_cooling_yesterday": data["energy"]["cooling"]["yesterday"],
        "energy_cooling_month": data["energy"]["cooling"]["month"],
        "energy_cooling_year": data["energy"]["cooling"]["year"],
    }
    
    # Add heating circuit data (up to 5 circuits)
    for i in range(1, 6):
        hk_data = next((hk for hk in data["heating_circuits"] if hk["id"] == i), None)
        prefix = f"hk{i}_"
        
        if hk_data and hk_data.get("is_configured"):
            flat[f"{prefix}is_configured"] = True
            flat[f"{prefix}config"] = hk_data.get("config")
            flat[f"{prefix}mode"] = hk_data.get("mode")
            flat[f"{prefix}room_temp"] = hk_data.get("room_temp")
            flat[f"{prefix}room_setpoint_effective"] = hk_data.get("room_setpoint_effective")
            flat[f"{prefix}room_humidity"] = hk_data.get("room_humidity")
            flat[f"{prefix}flow_temp"] = hk_data.get("flow_temp")
            flat[f"{prefix}flow_setpoint"] = hk_data.get("flow_setpoint")
            flat[f"{prefix}setpoint_comfort"] = hk_data.get("setpoint_comfort")
            flat[f"{prefix}setpoint_normal"] = hk_data.get("setpoint_normal")
            flat[f"{prefix}setpoint_setback"] = hk_data.get("setpoint_setback")
            flat[f"{prefix}is_party_active"] = hk_data.get("is_party_active")
            flat[f"{prefix}is_pause_active"] = hk_data.get("is_pause_active")
            flat[f"{prefix}is_heating"] = hk_data.get("is_heating")
            flat[f"{prefix}is_cooling"] = hk_data.get("is_cooling")
            flat[f"{prefix}heating_curve_slope"] = hk_data.get("heating_curve_slope")
        else:
            flat[f"{prefix}is_configured"] = False
            # Set other fields to None for non-configured circuits
            for field in ["config", "mode", "room_temp", "room_setpoint_effective", 
                          "room_humidity", "flow_temp", "flow_setpoint", "setpoint_comfort",
                          "setpoint_normal", "setpoint_setback", "is_party_active",
                          "is_pause_active", "is_heating", "is_cooling", "heating_curve_slope"]:
                flat[f"{prefix}{field}"] = None
    
    return flat


def write_csv(data: dict[str, Any], filepath: str) -> bool:
    """
    Write data to a CSV file. Appends if file exists, creates with header if not.
    
    Args:
        data: The collected sensor data
        filepath: Path to the CSV file
        
    Returns:
        True if file was appended to, False if new file was created
    """
    flat_data = flatten_data_for_csv(data)
    file_path = Path(filepath)
    file_exists = file_path.exists()
    
    # Get the column order (consistent across all writes)
    fieldnames = list(flat_data.keys())
    
    if file_exists:
        # Read existing headers to ensure consistency
        with open(file_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_fieldnames = reader.fieldnames or []
            
        # Use existing field order, but add any new fields at the end
        for field in fieldnames:
            if field not in existing_fieldnames:
                existing_fieldnames.append(field)
        fieldnames = existing_fieldnames
        
        # Append new data
        with open(file_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow(flat_data)
    else:
        # Create new file with header
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerow(flat_data)
    
    return file_exists


def generate_text_report(data: dict[str, Any]) -> str:
    """Generate a human-readable text report."""
    lines = []
    
    # Header
    lines.append("=" * 70)
    lines.append("                    WAB11 HEAT PUMP STATUS REPORT")
    lines.append("=" * 70)
    lines.append(f"Generated: {data['timestamp']}")
    lines.append(f"Controller: {data['host']}")
    lines.append("")
    
    # System Status
    sys_data = data["system"]
    state_emoji = get_status_emoji(OperatingState[sys_data["operating_state"]])
    
    lines.append("─" * 70)
    lines.append("  SYSTEM STATUS")
    lines.append("─" * 70)
    lines.append(f"  Operating State:    {state_emoji} {sys_data['operating_state']}")
    lines.append(f"  System Mode:        {sys_data['mode']}")
    lines.append(f"  Outdoor Temp 1:     {format_temp(sys_data['outdoor_temp_1'])}")
    lines.append(f"  Outdoor Temp 2:     {format_temp(sys_data['outdoor_temp_2'])}")
    lines.append(f"  Power Request:      {sys_data['power_request_watts']} W")
    
    # Error status
    if sys_data["has_error"]:
        lines.append(f"  ⚠️  ERROR:          Code {sys_data['error_code']}")
    else:
        lines.append(f"  Status:             ✅ No errors")
    
    if sys_data["has_warning"]:
        lines.append(f"  ⚠️  WARNING:        Code {sys_data['warning_code']}")
    lines.append("")
    
    # Heat Pump
    hp_data = data["heat_pump"]
    if hp_data["is_configured"]:
        lines.append("─" * 70)
        lines.append("  HEAT PUMP")
        lines.append("─" * 70)
        lines.append(f"  State:              {hp_data['operating_state']}")
        lines.append(f"  Power:              {hp_data['power_request_percent']}%")
        lines.append(f"  Flow Temp (B4):     {format_temp(hp_data['flow_temp_b4'])}")
        lines.append(f"  Return Temp:        {format_temp(hp_data['return_temp'])}")
        if hp_data["spread"] is not None:
            lines.append(f"  Spread (ΔT):        {hp_data['spread']:.1f} K")
        lines.append(f"  Evaporator Temp:    {format_temp(hp_data['evaporator_temp'])}")
        lines.append(f"  Suction Gas Temp:   {format_temp(hp_data['suction_gas_temp'])}")
        lines.append(f"  Buffer Temp (B11):  {format_temp(hp_data['buffer_temp_b11'])}")
        lines.append(f"  Sum Flow (B7):      {format_temp(hp_data['sum_flow_b7'])}")
        lines.append(f"  Quiet Mode:         {format_bool(hp_data['is_quiet_mode'])}")
        lines.append(f"  Supports Cooling:   {format_bool(hp_data['supports_cooling'])}")
        lines.append(f"  Error Free:         {format_bool(hp_data['is_error_free'])}")
        lines.append("")
    
    # Heating Circuits
    configured_circuits = [hk for hk in data["heating_circuits"] if hk["is_configured"]]
    if configured_circuits:
        lines.append("─" * 70)
        lines.append("  HEATING CIRCUITS")
        lines.append("─" * 70)
        
        for hk in configured_circuits:
            status = "🔥" if hk.get("is_heating") else ("❄️" if hk.get("is_cooling") else "•")
            lines.append(f"  HK{hk['id']}: {hk['config']}")
            lines.append(f"    Mode:             {hk['mode']}")
            lines.append(f"    Room Temp:        {format_temp(hk['room_temp'])} → {format_temp(hk['room_setpoint_effective'])} {status}")
            if hk.get("room_humidity") is not None:
                lines.append(f"    Room Humidity:    {hk['room_humidity']}%")
            lines.append(f"    Flow Temp:        {format_temp(hk['flow_temp'])} → {format_temp(hk['flow_setpoint'])}")
            lines.append(f"    Setpoints:        Comfort: {format_temp(hk['setpoint_comfort'])}, "
                        f"Normal: {format_temp(hk['setpoint_normal'])}, "
                        f"Setback: {format_temp(hk['setpoint_setback'])}")
            
            party_mode, party_hours = hk.get("party_pause_info", ("automatic", None))
            if party_mode != "automatic" and party_hours:
                lines.append(f"    Party/Pause:      {party_mode.upper()} ({party_hours}h)")
            lines.append("")
    
    # Hot Water
    hw_data = data["hot_water"]
    if hw_data["is_configured"]:
        lines.append("─" * 70)
        lines.append("  HOT WATER")
        lines.append("─" * 70)
        charging_status = "🚿 Charging" if hw_data["is_charging"] else "Standby"
        lines.append(f"  Status:             {charging_status}")
        lines.append(f"  Temperature:        {format_temp(hw_data['temperature'])} → {format_temp(hw_data['setpoint_effective'])}")
        lines.append(f"  Normal Setpoint:    {format_temp(hw_data['setpoint_normal'])}")
        lines.append(f"  Setback Setpoint:   {format_temp(hw_data['setpoint_setback'])}")
        if hw_data["is_push_active"]:
            lines.append(f"  Push Active:        ✅ {hw_data['push_minutes']} min remaining")
        lines.append("")
    
    # Secondary Heat Source
    sh_data = data["secondary_heat"]
    if sh_data["is_wez2_configured"] or sh_data["is_e1_configured"] or sh_data["is_e2_configured"]:
        lines.append("─" * 70)
        lines.append("  SECONDARY HEAT SOURCES")
        lines.append("─" * 70)
        
        if sh_data["is_wez2_configured"]:
            status = "🔥 Active" if sh_data["is_wez2_active"] else "Standby"
            lines.append(f"  2nd Heat Source:    {status}")
            lines.append(f"    Operating Hours:  {sh_data['operating_hours_wez2']}h")
        
        if sh_data["is_e1_configured"]:
            status = "⚡ Active" if sh_data["is_e1_active"] else "Standby"
            lines.append(f"  Electric Heater 1:  {status}")
            lines.append(f"    Operating Hours:  {sh_data['operating_hours_e1']}h")
        
        if sh_data["is_e2_configured"]:
            status = "⚡ Active" if sh_data["is_e2_active"] else "Standby"
            lines.append(f"  Electric Heater 2:  {status}")
            lines.append(f"    Operating Hours:  {sh_data['operating_hours_e2']}h")
        
        lines.append(f"  Bivalence Temp:     {format_temp(sh_data['bivalence_temp_heating'])}")
        lines.append(f"  Limit Temp:         {format_temp(sh_data['limit_temp'])}")
        lines.append("")
    
    # SG-Ready / Inputs
    inp_data = data["inputs"]
    lines.append("─" * 70)
    lines.append("  SMART GRID / INPUTS")
    lines.append("─" * 70)
    lines.append(f"  SG-Ready State:     {inp_data['sg_ready_state']}")
    if inp_data["is_evu_lock"]:
        lines.append(f"  🔒 EVU Lock Active")
    if inp_data["is_sg_maximum"]:
        lines.append(f"  ⚡ SG Maximum Active (PV Surplus)")
    if inp_data["active_inputs"]:
        lines.append(f"  Active Inputs:      {', '.join(inp_data['active_inputs'])}")
    lines.append("")
    
    # Energy Statistics
    energy = data["energy"]
    lines.append("─" * 70)
    lines.append("  ENERGY STATISTICS")
    lines.append("─" * 70)
    lines.append(f"  {'':20} {'Today':>10} {'Yesterday':>10} {'Month':>10} {'Year':>10}")
    lines.append(f"  {'─' * 60}")
    lines.append(f"  {'Total':20} {energy['total']['today']:>10.1f} {energy['total']['yesterday']:>10.1f} "
                f"{energy['total']['month']:>10.1f} {energy['total']['year']:>10.1f} kWh")
    lines.append(f"  {'Heating':20} {energy['heating']['today']:>10.1f} {energy['heating']['yesterday']:>10.1f} "
                f"{energy['heating']['month']:>10.1f} {energy['heating']['year']:>10.1f} kWh")
    lines.append(f"  {'Hot Water':20} {energy['hot_water']['today']:>10.1f} {energy['hot_water']['yesterday']:>10.1f} "
                f"{energy['hot_water']['month']:>10.1f} {energy['hot_water']['year']:>10.1f} kWh")
    lines.append(f"  {'Cooling':20} {energy['cooling']['today']:>10.1f} {energy['cooling']['yesterday']:>10.1f} "
                f"{energy['cooling']['month']:>10.1f} {energy['cooling']['year']:>10.1f} kWh")
    lines.append("")
    
    # Footer
    lines.append("=" * 70)
    lines.append("                         END OF REPORT")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def run_single_collection(client: WAB11SyncClient, args) -> dict[str, Any]:
    """Run a single data collection and output."""
    data = collect_sensor_data(client)
    
    # Handle CSV output
    if args.csv:
        appended = write_csv(data, args.csv)
        if appended:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Data appended to {args.csv}", file=sys.stderr)
        else:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] CSV file created: {args.csv}", file=sys.stderr)
    
    # Handle text/JSON output
    if args.json:
        output = json.dumps(data, indent=2, default=str)
    else:
        output = generate_text_report(data)
    
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Report written to {args.output}", file=sys.stderr)
    elif not args.csv and not args.interval:
        # Only print to stdout if no CSV output, no file output, and not in continuous mode
        print(output)
    
    return data


def main():
    parser = argparse.ArgumentParser(
        description="Generate a status report from WAB11 heat pump controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/report.py --host 192.168.1.100
    python scripts/report.py --host 192.168.1.100 --json
    python scripts/report.py --host 192.168.1.100 --output report.txt
    python scripts/report.py --host 192.168.1.100 --json --output data.json
    python scripts/report.py --host 192.168.1.100 --csv data.csv
    python scripts/report.py --host 192.168.1.100 --csv data.csv --interval 5
        """
    )
    
    parser.add_argument(
        "--host",
        required=True,
        help="IP address of the WAB11 controller"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=502,
        help="Modbus TCP port (default: 502)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output in JSON format instead of text"
    )
    parser.add_argument(
        "--csv",
        type=str,
        metavar="FILE",
        help="Write data to CSV file (appends if file exists)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Write output to file instead of stdout"
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        metavar="MINUTES",
        help="Continuous mode: collect data every N minutes (use with --csv)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Connection timeout in seconds (default: 5.0)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    
    # Validate continuous mode requirements
    if args.interval is not None and args.interval <= 0:
        print("Error: --interval must be a positive number", file=sys.stderr)
        sys.exit(1)
    
    if args.interval and not args.csv:
        print("Warning: --interval without --csv will only print to stderr", file=sys.stderr)
    
    try:
        if args.interval:
            # Continuous mode
            run_continuous(args)
        else:
            # Single run mode
            run_single(args)
                
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(1)


def run_single(args):
    """Run a single data collection."""
    print(f"Connecting to WAB11 at {args.host}:{args.port}...", file=sys.stderr)
    
    with WAB11SyncClient(
        host=args.host,
        port=args.port,
        timeout=args.timeout,
        require_write_confirmation=True,
        enable_rate_limiting=False,
    ) as client:
        print("Reading sensor data...", file=sys.stderr)
        run_single_collection(client, args)


def run_continuous(args):
    """Run continuous data collection at specified intervals."""
    interval_seconds = args.interval * 60
    collection_count = 0
    error_count = 0
    max_consecutive_errors = 5
    
    print(f"Starting continuous monitoring of WAB11 at {args.host}:{args.port}", file=sys.stderr)
    print(f"Interval: {args.interval} minutes ({interval_seconds:.0f} seconds)", file=sys.stderr)
    print("Press Ctrl+C to stop.", file=sys.stderr)
    print("", file=sys.stderr)
    
    while True:
        try:
            # Create a new connection for each collection to handle connection drops
            with WAB11SyncClient(
                host=args.host,
                port=args.port,
                timeout=args.timeout,
                require_write_confirmation=True,
                enable_rate_limiting=False,
            ) as client:
                data = run_single_collection(client, args)
                collection_count += 1
                error_count = 0  # Reset error count on success
                
                # Print a summary line
                sys_data = data["system"]
                outdoor_temp = sys_data.get("outdoor_temp_1")
                outdoor_str = f"{outdoor_temp:.1f}°C" if outdoor_temp is not None else "N/A"
                print(
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"#{collection_count} | "
                    f"State: {sys_data['operating_state']} | "
                    f"Outdoor: {outdoor_str} | "
                    f"Next in {args.interval:.1f} min",
                    file=sys.stderr
                )
                
        except KeyboardInterrupt:
            raise  # Re-raise to be caught by main()
            
        except Exception as e:
            error_count += 1
            print(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                f"Error ({error_count}/{max_consecutive_errors}): {e}",
                file=sys.stderr
            )
            
            if error_count >= max_consecutive_errors:
                print(
                    f"Too many consecutive errors ({max_consecutive_errors}). Stopping.",
                    file=sys.stderr
                )
                sys.exit(1)
        
        # Wait for next interval
        try:
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            raise
   


if __name__ == "__main__":
    main()

