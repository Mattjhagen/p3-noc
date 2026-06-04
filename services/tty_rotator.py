#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import logging
import json

# Set up logging to stdout for systemd journal
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("tty_rotator")

# Ensure the root project directory is in the import path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(PROJECT_ROOT)

try:
    from services.db_service import DBService
    db_service = DBService()
except Exception as e:
    logger.error(f"Could not initialize DBService: {e}")
    db_service = None

# Constants
LOCK_TTY1_FILE = "/tmp/p3-lock-tty1"
LOCK_TTY2_FILE = "/tmp/p3-lock-tty2"
CRITICAL_ALARM_FILE = "/tmp/p3-critical-alarm"
STATUS_JSON_FILE = "/tmp/p3-tty-status.json"
ACTIVITY_FILE = "/tmp/p3-tty-activity"

def run_db_log(severity, event, action_taken, result):
    """Safely log rotation state transitions to the central database."""
    if db_service:
        try:
            db_service.log_operations_event(
                severity=severity,
                event=event,
                action_taken=action_taken,
                result=result,
                host="tty-rotator"
            )
            logger.info(f"DB Log: [{severity}] {event} - Result: {result}")
        except Exception as e:
            logger.error(f"Failed to write log to DB: {e}")
    else:
        logger.info(f"Mock DB Log: [{severity}] {event} - Result: {result}")

def is_service_active(service_name: str) -> bool:
    """Check if a systemd service is active."""
    if not sys.platform.startswith("linux"):
        return True
    try:
        res = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=2.0
        )
        return res.stdout.strip() == "active"
    except Exception as e:
        logger.warning(f"Error checking systemd service {service_name}: {e}")
        return False

def wait_for_gettys():
    """Wait until both getty sessions on tty1 and tty2 are active at boot."""
    if not sys.platform.startswith("linux"):
        logger.info("Non-Linux platform detected. Skipping getty activation check.")
        return

    logger.info("Waiting for getty@tty1.service and getty@tty2.service to be active...")
    first_log = True
    while True:
        tty1_ok = is_service_active("getty@tty1.service")
        tty2_ok = is_service_active("getty@tty2.service")
        
        if tty1_ok and tty2_ok:
            logger.info("Both getty@tty1 and getty@tty2 services are active.")
            break
            
        if first_log:
            logger.info(f"Waiting... getty@tty1 active: {tty1_ok}, getty@tty2 active: {tty2_ok}")
            first_log = False
            
        time.sleep(2.0)

def get_active_tty():
    """Query currently active virtual console via fgconsole."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        res = subprocess.run(["fgconsole"], capture_output=True, text=True, timeout=1.5)
        if res.returncode == 0:
            return int(res.stdout.strip())
    except Exception as e:
        logger.debug(f"Failed to query active TTY: {e}")
    return None

def switch_to_tty(target_tty: int) -> bool:
    """Execute chvt to switch virtual terminal."""
    active_tty = get_active_tty()
    if active_tty == target_tty:
        return True

    logger.info(f"Console switch requested: TTY {active_tty} -> TTY {target_tty}")
    if not sys.platform.startswith("linux"):
        logger.info(f"[SIMULATION] Switched to TTY {target_tty}")
        return True

    try:
        res = subprocess.run(["chvt", str(target_tty)], capture_output=True, text=True, timeout=2.0)
        if res.returncode == 0:
            logger.info(f"Successfully switched to TTY {target_tty}")
            return True
        else:
            logger.error(f"chvt {target_tty} failed (code {res.returncode}): {res.stderr.strip()}")
            return False
    except Exception as e:
        logger.error(f"Exception executing chvt {target_tty}: {e}")
        return False

def load_config() -> tuple:
    """Read ROTATION_INTERVAL and IDLE_RESUME_TIMEOUT from config, enforce constraints. Return (interval, timeout)."""
    config_file = "/etc/p3/tty-rotator.conf"
    interval = 60
    timeout = 1800
    if os.path.exists(config_file):
        try:
            with open(config_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ROTATION_INTERVAL="):
                        val = line.split("=")[1].strip()
                        interval = int(val)
                        interval = max(15, min(300, interval))
                    elif line.startswith("IDLE_RESUME_TIMEOUT="):
                        val = line.split("=")[1].strip()
                        timeout = int(val)
                        timeout = max(10, min(86400, timeout))
        except Exception as e:
            logger.debug(f"Could not load config: {e}")
    return interval, timeout

def write_status(status: str, current_tty: int, interval: int, last_switch_time: str, next_switch_seconds: int,
                 pause_reason: str = "None", inactivity_seconds_remaining: int = 0, next_auto_resume_str: str = "N/A"):
    """Write rotator status object atomically to /tmp/p3-tty-status.json."""
    try:
        mins = next_switch_seconds // 60
        secs = next_switch_seconds % 60
        next_switch_str = f"{mins:02d}:{secs:02d}"
        
        if inactivity_seconds_remaining > 0:
            i_mins = inactivity_seconds_remaining // 60
            i_secs = inactivity_seconds_remaining % 60
            inactivity_timer_str = f"{i_mins}m {i_secs}s"
        else:
            inactivity_timer_str = "0m 00s" if status == "PAUSED" and pause_reason != "None" else "N/A"

        status_data = {
            "status": status,
            "current_tty": current_tty,
            "rotation_interval": interval,
            "last_switch_time": last_switch_time,
            "next_switch_seconds": next_switch_seconds,
            "next_switch_str": next_switch_str,
            "pause_reason": pause_reason,
            "inactivity_seconds_remaining": inactivity_seconds_remaining,
            "inactivity_timer_str": inactivity_timer_str,
            "next_auto_resume_str": next_auto_resume_str
        }
        
        temp_file = STATUS_JSON_FILE + ".tmp"
        with open(temp_file, "w") as f:
            json.dump(status_data, f)
        os.replace(temp_file, STATUS_JSON_FILE)
    except Exception as e:
        logger.error(f"Failed to write status JSON: {e}")

def main():
    logger.info("Starting P3 NOC TTY Rotator Service...")
    
    # 1. Wait for getty sessions to initialize
    wait_for_gettys()

    # 2. Main rotation loop
    current_target = 1
    seconds_elapsed = 0
    
    # Track states for change logging and timer resets
    in_manual_override = False
    last_manual_change_time = 0.0
    last_observed_tty = None
    
    last_locked_state = None  # Can be None, 'tty1', 'tty2', or 'unlocked'
    last_alarm_state = False
    last_switch_time = time.strftime("%H:%M:%S")

    # Perform initial switch to start on TTY1
    switch_to_tty(1)

    while True:
        try:
            # Load config values dynamically
            interval, timeout = load_config()
            
            # Check override files
            lock_tty1 = os.path.exists(LOCK_TTY1_FILE)
            lock_tty2 = os.path.exists(LOCK_TTY2_FILE)
            critical_active = os.path.exists(CRITICAL_ALARM_FILE)

            # Get actual active TTY
            active_tty = get_active_tty()
            if active_tty is None:
                active_tty = current_target

            # Check dashboard activity file
            last_activity_time = 0.0
            if os.path.exists(ACTIVITY_FILE):
                try:
                    last_activity_time = os.path.getmtime(ACTIVITY_FILE)
                except Exception:
                    pass

            now_time = time.time()
            has_operator_activity = (now_time - last_activity_time < timeout)

            # Detect manual console override
            if active_tty != current_target:
                # If we were not already in manual override, or active TTY changed again
                if not in_manual_override or active_tty != last_observed_tty:
                    if not in_manual_override:
                        logger.info("Operator manually changed console. Rotation paused.")
                        run_db_log("INFO", "Operator manually changed console. Rotation paused.", "Detected manual TTY switch", "ROTATION_PAUSED")
                    else:
                        logger.info("Additional manual TTY change detected. Resetting inactivity timer.")
                    
                    in_manual_override = True
                    last_manual_change_time = now_time
                    last_observed_tty = active_tty

            # Resolve lock states logging
            current_locked = 'unlocked'
            if lock_tty1:
                current_locked = 'tty1'
            elif lock_tty2:
                current_locked = 'tty2'

            if last_locked_state is not None and last_locked_state != current_locked:
                if current_locked == 'tty1':
                    run_db_log("INFO", "Operator override active: Display locked to TTY1", "touch /tmp/p3-lock-tty1", "LOCKED_TTY1")
                elif current_locked == 'tty2':
                    run_db_log("INFO", "Operator override active: Display locked to TTY2", "touch /tmp/p3-lock-tty2", "LOCKED_TTY2")
                else:
                    run_db_log("INFO", "Operator overrides cleared. Resuming automatic rotation.", "rm /tmp/p3-lock-tty*", "ROTATION_RESUMED")
            last_locked_state = current_locked

            # Resolve critical alarm state logging
            if last_alarm_state != critical_active:
                if critical_active:
                    alarm_info = "Unknown"
                    try:
                        with open(CRITICAL_ALARM_FILE, "r") as f:
                            alarm_info = f.read().strip()
                    except Exception:
                        pass
                    run_db_log("CRITICAL", f"Critical Alarm Override: Rotation paused, locked on TTY1 ({alarm_info})", "Paused tty rotation", "ALARM_LOCKED")
                else:
                    run_db_log("INFO", "Critical alarm cleared. Resuming TTY rotation.", "Resumed tty rotation", "ROTATION_RESUMED")
            last_alarm_state = critical_active

            # Resolve rotation state
            status = "ACTIVE"
            pause_reason = "None"
            inactivity_seconds_remaining = 0
            next_auto_resume_str = "N/A"

            if critical_active:
                status = "PAUSED"
                pause_reason = "None"
                switch_to_tty(1)
                current_target = 1
                seconds_elapsed = 0
                in_manual_override = False  # Ignore manual overrides under safety alarm
            elif has_operator_activity:
                status = "PAUSED"
                pause_reason = "Operator Activity"
                inactivity_seconds_remaining = int(max(0.0, timeout - (now_time - last_activity_time)))
                seconds_elapsed = 0
            elif in_manual_override:
                # Check if override has timed out
                time_since_manual = now_time - last_manual_change_time
                if time_since_manual >= timeout:
                    logger.info("Operator inactivity timeout reached. Rotation resumed.")
                    run_db_log("INFO", "Operator inactivity timeout reached. Rotation resumed.", "Idle timeout expired", "ROTATION_RESUMED")
                    in_manual_override = False
                    status = "ACTIVE"
                    pause_reason = "None"
                    if active_tty in (1, 2):
                        current_target = active_tty
                    else:
                        current_target = 1
                    seconds_elapsed = 0
                else:
                    status = "PAUSED"
                    pause_reason = "Manual Console Override"
                    inactivity_seconds_remaining = int(max(0.0, timeout - time_since_manual))
                    seconds_elapsed = 0
            elif lock_tty1:
                status = "PAUSED"
                pause_reason = "None"
                switch_to_tty(1)
                current_target = 1
                seconds_elapsed = 0
            elif lock_tty2:
                status = "PAUSED"
                pause_reason = "None"
                switch_to_tty(2)
                current_target = 2
                seconds_elapsed = 0
            else:
                # Normal automatic rotation
                status = "ACTIVE"
                pause_reason = "None"
                
                if active_tty not in (1, 2):
                    # Pause but no alarm or manual override timer
                    write_status(
                        status="PAUSED",
                        current_tty=active_tty,
                        interval=interval,
                        last_switch_time=last_switch_time,
                        next_switch_seconds=0,
                        pause_reason="None",
                        inactivity_seconds_remaining=0,
                        next_auto_resume_str="N/A"
                    )
                    time.sleep(1.0)
                    continue

                if seconds_elapsed >= interval:
                    next_target = 2 if current_target == 1 else 1
                    if switch_to_tty(next_target):
                        current_target = next_target
                        last_switch_time = time.strftime("%H:%M:%S")
                    seconds_elapsed = 0
                else:
                    switch_to_tty(current_target)
                    seconds_elapsed += 1

            # Format next resume UTC timestamp
            if status == "PAUSED" and pause_reason in ("Operator Activity", "Manual Console Override"):
                resume_time_epoch = now_time + inactivity_seconds_remaining
                next_auto_resume_str = time.strftime("%H:%M UTC", time.gmtime(resume_time_epoch))

            # Format next switch seconds
            next_switch_seconds = max(0, interval - seconds_elapsed) if status == "ACTIVE" else 0

            # Write status block to JSON
            write_status(
                status=status,
                current_tty=active_tty,
                interval=interval,
                last_switch_time=last_switch_time,
                next_switch_seconds=next_switch_seconds,
                pause_reason=pause_reason,
                inactivity_seconds_remaining=inactivity_seconds_remaining,
                next_auto_resume_str=next_auto_resume_str
            )

        except Exception as e:
            logger.error(f"Error in rotator main loop: {e}", exc_info=True)

        time.sleep(1.0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("TTY Rotator stopped by keyboard interrupt.")
        sys.exit(0)
