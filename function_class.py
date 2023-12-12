# Fichier function_class.py

from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional
from concurrent.futures import ThreadPoolExecutor
from task_manager import task_manager
from vm_manager import ProxmoxVMManager
from ip_manager import IPManager
import os
import proxmoxer

class ProxmoxAPIManager:
    def __init__(self):
        pass

    @classmethod
    async def get_proxmox_api(cls):
        host = os.getenv('PROXMOX_HOST')
        user = os.getenv('PROXMOX_USER')
        password = os.getenv('PROXMOX_PASSWORD')
        return proxmoxer.ProxmoxAPI(host, user=user, password=password, verify_ssl=True)

class CloneVMRequest(BaseModel):
    source_vm_id: int
    new_vm_id: int = None
    new_vm_name: str = None
    cpu: int = None
    ram: int = None
    disk_type: str = None
    disk_size: str = None
    bridge: str = None
    ipv4: str = None
    ipv6: str = None
    start_vm: bool = False

class UpdateVMConfigRequest(BaseModel):
    vm_id: int
    bridge: Optional[str] = None
    ipv4: Optional[str] = None
    ipv6: Optional[str] = None
    cpu: Optional[int] = None
    ram: Optional[int] = None
    disk_type: Optional[str] = None
    disk_size: Optional[str] = None

class VMIdRequest(BaseModel):
    vm_id: int

class CheckStatusRequest(BaseModel):
    task_id: str

class ListVMsRequest(BaseModel):
    vmid: int = None

