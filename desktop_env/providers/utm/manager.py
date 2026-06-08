import logging
import os
import platform
import shutil
import subprocess
import threading
import time
import zipfile

import psutil
import requests
from filelock import FileLock
from tqdm import tqdm
from dotenv import load_dotenv


from desktop_env.providers.base import VMManager

from huggingface_hub import hf_hub_download

logger = logging.getLogger("desktopenv.providers.local.UTMManager")
logger.setLevel(logging.INFO)

MAX_RETRY_TIMES = 10
RETRY_INTERVAL = 5


VMS_DIR = os.path.expanduser("~/Library/Containers/com.utmapp.UTM/Data/Documents")
DOWNLOADED_FILE_NAME = "macOS_SNAPSHOT.utm.zip"

load_dotenv()
access_token = os.getenv("HF_TOKEN") 

def _download_vm(vms_dir: str):
    global DOWNLOADED_FILE_NAME
    if not os.path.exists(vms_dir):
        os.makedirs(vms_dir)

    if not os.path.exists(os.path.join(vms_dir, DOWNLOADED_FILE_NAME)):
        hf_hub_download(
            repo_id="...", 
            filename=DOWNLOADED_FILE_NAME, 
            local_dir=vms_dir,
            token=access_token,
            repo_type="dataset"
        )

    logger.info("Unzipping the downloaded file...☕️")
    with zipfile.ZipFile(os.path.join(vms_dir, DOWNLOADED_FILE_NAME), 'r') as zip_ref:
        zip_ref.extractall(vms_dir)


class UTMVMManager(VMManager):
    def __init__(self, registry_path=None):
        self.registry_path = registry_path

    def initialize_registry(self, **kwargs):
        """
        Initialize registry.
        """
        pass

    def add_vm(self, vm_path, *args, **kwargs):
        """
        Add the path of new VM to the registration.
        """
        pass

    def delete_vm(self, vm_path, *args, **kwargs):
        """
        Delete the registration of VM by path.
        """
        pass

    def occupy_vm(self, vm_path, pid, *args, **kwargs):
        """
        Mark the path of VM occupied by the pid.
        """
        pass

    def list_free_vms(self, *args, **kwargs):
        """
        List the paths of VM that are free to use allocated.
        """
        pass

    def check_and_clean(self, *args, **kwargs):
        """
        Check the registration list, and remove the paths of VM that are not in use.
        """
        pass

    def get_vm_path(self, *args, **kwargs):
        """
        Get a virtual machine that is not occupied, generate a new one if no free VM.
        """
        exists = os.path.exists(VMS_DIR) and os.path.exists(os.path.join(VMS_DIR, DOWNLOADED_FILE_NAME.replace(".zip", "")))
        
        if not exists:
            logger.info(f"Downloading VM from Hugging Face...")
            _download_vm(VMS_DIR)

        vm_name = DOWNLOADED_FILE_NAME.replace(".zip", "")
        vm_path = os.path.join(VMS_DIR, vm_name)

        return "macOS"