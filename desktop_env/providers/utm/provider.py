from datetime import datetime, timedelta
import os
import re
import time
import uuid
import random
import logging
import plistlib
import subprocess

from desktop_env.providers.base import Provider

logger = logging.getLogger("desktopenv.providers.local.UTMProvider")
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Timing constants
# ---------------------------------------------------------------------------
SHUTDOWN_POLL_INTERVAL = 2
SHUTDOWN_MAX_RETRIES = 15
START_MAX_RETRIES = 10

# SSH / SCP helpers
_SSH_OPTS = [
    "-o", "StrictHostKeyChecking=no",
    "-o", "PreferredAuthentications=password",
    "-o", "PubkeyAuthentication=no",
    "-o", "IdentitiesOnly=yes",
    "-o", "BatchMode=no",
    "-o", "ConnectTimeout=5",
]

class IPAddressResolutionError(Exception):
    """Raised when the guest IP address cannot be determined."""


class UTMProvider(Provider):
    LOGIN = "admin"
    PASSWORD = "admin"

    def __init__(self, region: str = None):
        self.region = region
        self.running_name: str | None = None
        self.snapshot_name: str | None = None
        self._mac_address: str | None = None

    # ------------------------------------------------------------------
    # Low-level utmctl wrapper
    # ------------------------------------------------------------------

    @staticmethod
    def _run_utmctl(
        command: list[str],
        *,
        check_return_code: bool = True,
        hide_utm: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a utmctl command and return the completed process.

        Args:
            command: utmctl sub-command and arguments (e.g. ``["start", "my-vm"]``).
            check_return_code: Raise on non-zero exit code when ``True``.
            hide_utm: Inject ``--hide`` so the UTM window stays hidden.
        """
        full_cmd = ["utmctl"] + command

        if hide_utm:
            full_cmd.append("--hide")

        logger.debug(f"Running: {' '.join(full_cmd)}",)

        result = subprocess.run(full_cmd, capture_output=True, text=True)

        if check_return_code and result.returncode != 0:
            raise Exception(f"utmctl failed: {result.stderr.strip()}")

        return result

    # ------------------------------------------------------------------
    # MAC address helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_random_mac() -> str:
        """Return a random locally-administered unicast MAC address."""
        first_byte = (random.randint(0x00, 0xFF) | 0x02) & 0xFE  # LAA + unicast
        rest = [random.randint(0x00, 0xFF) for _ in range(5)]
        return ":".join(f"{b:02x}" for b in [first_byte, *rest])

    @property
    def _config_plist_path(self) -> str:
        return os.path.expanduser(
            f"~/Library/Containers/com.utmapp.UTM/Data/Documents"
            f"/{self.snapshot_name}.utm/config.plist"
        )

    @property
    def mac_address(self) -> str | None:
        if self._mac_address is not None and self._mac_address[0] == self.running_name:
            return self._mac_address[1]

        logger.warning(
            "MAC address not set for '%s'. Reading from config.plist.", self.running_name
        )
        path = self._config_plist_path
        if not os.path.exists(path):
            logger.error("Config file not found: %s", path)
            return None

        with open(path, "rb") as fh:
            plist = plistlib.load(fh)

        try:
            self._mac_address = (
                self.self.running_name,
                plist["Network"][0]["MacAddress"]
            )
            logger.info("Read MAC %s from config.plist.", self._mac_address[1])
        except KeyError:
            logger.error("MAC address key missing in config.plist for '%s'.", self.running_name)
            return None

        return self._mac_address[1]

    @mac_address.setter
    def mac_address(self, value: str | None) -> None:
        self._mac_address = (self.running_name, value) if value is not None else None

        if value is None:
            return

        path = self._config_plist_path
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")

        with open(path, "rb") as fh:
            plist = plistlib.load(fh)

        plist["Network"][0]["MacAddress"] = value

        with open(path, "wb") as fh:
            plistlib.dump(plist, fh)

    # ------------------------------------------------------------------
    # VM lifecycle
    # ------------------------------------------------------------------

    def clone_vm(self, *, assign_random_mac: bool = True) -> str:
        """Clone ``self.snapshot_name`` into a fresh VM and return its name.

        If a running VM already exists it is deleted first.
        """
        if self.running_name is not None:
            logger.info("VM '%s' already exists – deleting before clone.", self.running_name)
            self.delete_vm(self.running_name)

        self.running_name = uuid.uuid4().hex

        if assign_random_mac:
            self.mac_address = self._generate_random_mac()
            logger.info("Assigned MAC %s to '%s'.", self.mac_address, self.snapshot_name)

        self._run_utmctl(["clone", self.snapshot_name, "--name", self.running_name])
        return self.running_name

    def start_emulator(self, path_to_vm: str, headless: bool, os_type: str) -> None:
        """Clone, boot, and set up the VM identified by *path_to_vm*."""
        if not self.snapshot_name:
            self.snapshot_name = path_to_vm

        if self.running_name is not None and self._is_running(self.running_name):
            logger.info("VM '%s' is already running.", self.running_name)
            return

        self.clone_vm()
        self._run_utmctl(["start", self.running_name], hide_utm=False)
        logger.info("Boot command sent")

        self._setup_emulator()
        self._wait_for_status(self.running_name, expected={"started", "running"}, retries=START_MAX_RETRIES)

    def stop_emulator(self, path_to_vm: str = None, *, delete: bool = True) -> None:
        """Stop (and optionally delete) the running VM."""
        if not self._is_running(self.running_name):
            logger.info("VM '%s' is already stopped.", self.running_name)
            return

        self._run_utmctl(["stop", self.running_name])
        logger.info("Stop command sent to '%s'.", self.running_name)
        self._wait_for_status(
            self.running_name,
            expected={"stopped"},
            retries=SHUTDOWN_MAX_RETRIES,
            interval=SHUTDOWN_POLL_INTERVAL,
        )

        if delete and self.running_name:
            self.delete_vm(self.running_name)
            self.running_name = None

    def revert_to_snapshot(self, path_to_vm: str, snapshot_name: str) -> str:
        """Revert by stopping the VM and restarting from its base disk state.

        UTM does not support traditional snapshots, so this is the closest
        equivalent.
        """
        self.stop_emulator()
        time.sleep(SHUTDOWN_POLL_INTERVAL)
        self.start_emulator(path_to_vm, headless=False, os_type="")
        logger.info(f"Reverted '{self.running_name}' via stop-and-restart.")
        return self.running_name

    def save_state(self, path_to_vm: str, snapshot_name: str) -> None:
        raise NotImplementedError("UTM provider does not support traditional snapshots.")

    @classmethod
    def delete_vm(cls, vm_name: str, region: str = None) -> None:
        cls._run_utmctl(["delete", vm_name])

    # ------------------------------------------------------------------
    # IP address resolution  (tried in order: utmctl → DHCP → ARP)
    # ------------------------------------------------------------------

    def get_ip_address(self, path_to_vm: str) -> str:
        """Return the guest IP address, trying three resolution strategies."""
        vm_name = self.running_name

        if not self._is_running(vm_name):
            raise RuntimeError(f"VM '{vm_name}' is not running.")

        strategies = [
            ("utmctl",      self._get_utmctl_ip_address),
            ("DHCP leases", self._get_dhcp_ip_address),
            ("ARP table",   self._get_arp_ip_address),
        ]
        for label, strategy in strategies:
            try:
                return strategy(vm_name)
            except Exception as exc:
                logger.warning("IP lookup via %s failed: %s", label, exc)

        raise IPAddressResolutionError(f"Could not determine IP address for VM '{vm_name}' using any strategy.")

    def _get_utmctl_ip_address(self, vm_name: str) -> str:
        result = self._run_utmctl(["ip-address", vm_name])
        lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]

        if not lines:
            raise IPAddressResolutionError("utmctl ip-address returned no output.")
        
        logger.info("utmctl IP for '%s': %s", vm_name, lines[0])
        return lines[0]

    def _get_dhcp_ip_address(self, vm_name: str, seconds_to_wait: int = 30) -> str:
        """Look up the guest IP in macOS's DHCP lease database."""
        mac = self._require_mac()
        normalize_mac = lambda x: ":".join([i.lstrip("0") if i.lstrip("0") else "0" for i in x.split(":")])
        normalize_mac_address = normalize_mac(mac)

        wait_until = datetime.now() + timedelta(seconds=seconds_to_wait)
        
        while datetime.now() < wait_until:
            with open("/var/db/dhcpd_leases") as fh:
                leases = fh.read()


            # Find the freshest lease matching our MAC
            best_ip = None
            best_ts = 0

            for block in leases.split("{"):
                if f"hw_address=1,{normalize_mac_address}" not in block:
                    continue

                ip_m = re.search(r"ip_address=(\S+)", block)
                ts_m = re.search(r"lease=(0x[0-9a-fA-F]+)", block)
                if not ip_m:
                    continue

                ts = int(ts_m.group(1), 16) if ts_m else 0
                if ts > best_ts:
                    best_ts = ts
                    best_ip = ip_m.group(1)

            if best_ip:
                logger.info(f"DHCP IP for '{vm_name}': {best_ip} (lease=0x{best_ts:x})")
                return best_ip

            logger.debug(f"No lease for MAC {normalize_mac_address} yet, retrying...")
            time.sleep(1)
                
        raise IPAddressResolutionError(f"No DHCP lease found for MAC {mac}.")

    def _get_arp_ip_address(self, vm_name: str) -> str:
        """Look up the guest IP in the host ARP table."""
        mac = self._require_mac()

        result = subprocess.run(["arp", "-a"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            ip_m = re.search(r"\((.+?)\)", line)
            mac_m = re.search(r"at ([0-9a-f:]+)", line)
            if ip_m and mac_m and mac_m.group(1).lower() == mac.lower():
                ip = ip_m.group(1)
                logger.info(f"ARP IP for '{vm_name}': {ip}")
                return ip

        raise IPAddressResolutionError(f"MAC {mac} not found in ARP table.")

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------
    @staticmethod
    def ssh_with_retry(cmd, max_retries=5, delay=3):
        for attempt in range(max_retries):
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result

            if "Permission denied" in result.stderr:
                time.sleep(delay)
                continue

            # Some other error — fail immediately
            raise RuntimeError(f"SSH failed: {result.stderr}")
        raise RuntimeError(f"SSH failed after {max_retries} retries: {result.stderr}")

    def _setup_emulator(self) -> None:
        """SCP server files into the guest and run the install script."""
        ip = self.get_ip_address(self.running_name)

        self._scp_server_files(ip)
        self._run_permission_bg_script(ip)
        self._run_install_script(ip)

    def _scp_server_files(self, ip: str) -> None:
        cmd = [
            "sshpass", "-p", self.PASSWORD,
            "scp", *_SSH_OPTS, "-r",
            "./vm_files", f"{self.LOGIN}@{ip}:/Users/{self.LOGIN}/",
        ]
        logger.info(f"Copying server files to {ip}...")
        result = self.ssh_with_retry(cmd)
        if result.returncode != 0:
            raise RuntimeError(f"scp failed: {result.stderr.strip()}")
        logger.info("Server files copied successfully.")

    def _run_install_script(self, ip: str) -> None:
        install_path = f"/Users/{self.LOGIN}/vm_files/install.sh"
        cmd = [
            "sshpass", "-p", self.PASSWORD,
            "ssh", *_SSH_OPTS,
            f"{self.LOGIN}@{ip}",
            f"bash -l -c 'chmod +x {install_path} && {install_path}'",
        ]
        logger.info(f"Running install.sh on guest at {ip}...")
        sentinel = "=== Activating Conda environment and running main script ==="

        end = False
        process = None

        for attempt in range(5):
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1  # line-buffered
            )

            for line in process.stdout:
                line = line.strip()
                logger.info(f"[VM {self.running_name}] {line.rstrip()}")

                if sentinel in line:
                    logger.info(f"Server start reached on '{self.running_name}'.")
                    end = True
                    break

                if "Permission denied" in line:
                    logger.warning(f"SSH permission denied on attempt {attempt + 1}, retrying...")
                    process.terminate()
                    break  # retry the whole SSH command
            
            if end:
                break

        process.stdout.close()
        logger.info("Continuing after install sentinel.")

    def _run_permission_bg_script(self, ip: str) -> None:
        bg_script_path = f"/Users/{self.LOGIN}/vm_files/allow_permission.sh"

        cmd = [
            "sshpass", "-p", self.PASSWORD,
            "ssh", *_SSH_OPTS,
            f"{self.LOGIN}@{ip}",
            f"nohup bash -l -c 'chmod +x {bg_script_path} && {bg_script_path}' > allow.log 2>&1 &",
        ]
        logger.info(f"Starting allow_permission.sh on guest at {ip}...")

        process = None
        end = False

        for attempt in range(5):
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1  # line-buffered
            )

            for line in process.stdout:
                line = line.strip()
                logger.info(f"[VM {self.running_name}] {line.rstrip()}")

                if "Permission denied" in line:
                    logger.warning(f"SSH permission denied on attempt {attempt + 1}, retrying...")
                    process.terminate()
                else:
                    end = True

                break  # command started successfully, no need to retry
            
            if end:
                break

        process.stdout.close()
        logger.info("allow_permission.sh started.")

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    @classmethod
    def get_vm_status(cls, vm_name: str) -> str:
        try:
            result = cls._run_utmctl(["status", vm_name])
            return result.stdout.strip()
        except Exception as exc:
            logger.error(f"Could not get status for '{vm_name}': {exc}")
            return "unknown"

    @classmethod
    def _is_running(cls, vm_name: str | None) -> bool:
        if not vm_name:
            return False
        status = cls.get_vm_status(vm_name).lower()
        return "started" in status or "running" in status

    @classmethod
    def _wait_for_status(
        cls,
        vm_name: str,
        expected: set[str],
        retries: int,
        interval: int = 2,
    ) -> None:
        """Poll until the VM status contains one of *expected* tokens."""
        for attempt in range(retries):
            status = cls.get_vm_status(vm_name).lower()
            if any(s in status for s in expected):
                return

            if attempt < retries - 1:
                time.sleep(interval)

        logger.warning(
            "VM '%s' did not reach status %s after %d retries.",
            vm_name, expected, retries,
        )

    def _require_mac(self) -> str:
        """Return the MAC address or raise if it is not set."""
        mac = self.mac_address

        if not mac:
            raise RuntimeError(f"MAC address is not set for the VM '{self.running_name}'.")
        
        return mac
