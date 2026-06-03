#!/usr/bin/env python3
"""
Script to automatically allow permission dialogs on macOS.
Checks every 0.1 seconds for permission dialogs and clicks "Allow" button.
"""

import subprocess
import time
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_applescript(script):
    """Execute an AppleScript and return the result."""
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        logger.error("AppleScript execution timed out")
        return None, "Timeout", 1
    except Exception as e:
        logger.error(f"Error running AppleScript: {e}")
        return None, str(e), 1


def check_and_click_allow():
    """
    Check for permission dialogs and click the Allow button.
    Returns True if a button was clicked, False otherwise.
    """
    applescript = '''
    tell application "System Events"
    repeat with proc in application processes
        try
            tell proc
                repeat with win in windows
                    try
                        repeat with b in buttons of win
                            set bName to name of b
                            if bName is "Allow" or bName is "OK" or bName is "Always Allow" then
                                click b
                                return "Clicked " & bName & " in " & (name of proc)
                            end if
                        end repeat
                    end try
                end repeat
            end tell
        end try
    end repeat

    return "No permission dialog found"
    end tell
    '''
    
    stdout, stderr, returncode = run_applescript(applescript)
    
    if returncode == 0 and stdout:
        if "Clicked" in stdout:
            logger.info(f"✓ {stdout}")
            return True
        elif "No permission dialog found" not in stdout:
            logger.debug(stdout)
    elif stderr:
        # Only log errors that aren't accessibility-related (common when script starts)
        if "not allowed assistive access" not in stderr.lower():
            logger.error(f"AppleScript error: {stderr}")
    
    return False


def monitor_permissions(check_interval=0.1):
    """
    Continuously monitor for permission dialogs.
    
    Args:
        check_interval: Time in seconds between checks (default: 0.1)
    """
    logger.info(f"Starting permission monitor (checking every {check_interval}s)")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)
    
    # Check if we have accessibility permissions
    check_script = '''
    tell application "System Events"
        return "ready"
    end tell
    '''
    
    stdout, stderr, returncode = run_applescript(check_script)
    if returncode != 0 and "not allowed assistive access" in stderr.lower():
        logger.error("")
        logger.error("⚠️  IMPORTANT: This script needs Accessibility permissions!")
        logger.error("Please go to: System Preferences → Security & Privacy → Privacy → Accessibility")
        logger.error("Add Terminal (or your Python IDE) to the list and enable it.")
        logger.error("")
    
    try:
        click_count = 0
        check_count = 0
        
        while True:
            check_count += 1
            
            if check_and_click_allow():
                click_count += 1
            
            # Log status every 100 checks (every 10 seconds at 0.1s interval)
            if check_count % 100 == 0:
                logger.debug(f"Status: {check_count} checks, {click_count} permissions allowed")
            
            time.sleep(check_interval)
            
    except KeyboardInterrupt:
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"Stopped after {check_count} checks")
        logger.info(f"Total permissions allowed: {click_count}")
        logger.info("Permission monitor stopped by user")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Automatically click Allow on macOS permission dialogs"
    )
    parser.add_argument(
        '-i', '--interval',
        type=float,
        default=0.1,
        help='Check interval in seconds (default: 0.1)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    monitor_permissions(check_interval=args.interval)
