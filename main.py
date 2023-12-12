# Fichier main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from typing import Optional
from fastapi.responses import JSONResponse
from function_class import (
    ProxmoxVMManager, IPManager, ProxmoxAPIManager,
    CloneVMRequest, UpdateVMConfigRequest, VMIdRequest, CheckStatusRequest, ListVMsRequest
)
from task_manager import task_manager

import logging,random,uuid,asyncio,os

app = FastAPI()

# Configuration du journal
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

# Stockage des tâches asynchrones
tasks = {}
task_queue = asyncio.Queue()
ticket_manager = TicketManager()

@app.post("/clone_vm")
async def clone_vm(request: CloneVMRequest):
    proxmox = await ProxmoxAPIManager.get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')
    
    ip_pools = IPManager.load_ip_pools()
    ip_manager = IPManager(ip_pools=ip_pools)
    api_manager = ProxmoxAPIManager()
    vm_manager = ProxmoxVMManager(ip_manager, api_manager)

    task_id = uuid.uuid4().hex
    tasks[task_id] = "In Progress"
    
    # Lancement de la tâche de clonage en arrière-plan
    asyncio.create_task(vm_manager.clone_vm_async(task_id, request.dict(), node, ip_pools, tasks))

    return {"task_id": task_id}

@app.post("/update_vm_config")
async def update_vm_config(request: UpdateVMConfigRequest):
    proxmox = await ProxmoxAPIManager.get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')

    ip_pools = IPManager.load_ip_pools()
    ip_manager = IPManager(ip_pools=ip_pools)
    api_manager = ProxmoxAPIManager()
    vm_manager = ProxmoxVMManager(ip_manager, api_manager)

    task_id = uuid.uuid4().hex
    tasks[task_id] = "In Progress"

    # Utilisation de l'instance vm_manager pour appeler la méthode
    asyncio.create_task(vm_manager.update_vm_config_async(request.dict(), node))

    return {"task_id": task_id}

@app.delete("/delete_vm/{vm_id}")
async def delete_vm(vm_id: int):
    proxmox = await ProxmoxAPIManager.get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')

    ip_pools = IPManager.load_ip_pools()
    ip_manager = IPManager(ip_pools=ip_pools)
    api_manager = ProxmoxAPIManager()
    vm_manager = ProxmoxVMManager(ip_manager, api_manager)

    task_id = uuid.uuid4().hex
    tasks[task_id] = "In Progress"

    asyncio.create_task(vm_manager.delete_vm_async(vm_id, node, task_id, tasks))
    return {"task_id": task_id}

@app.get("/check_status")
async def check_status(task_id: str):
    task_info = tasks.get(task_id, "Unknown Task ID")
    return {"task_id": task_id, "task_info": task_info}

@app.get("/list_vms")
async def list_vms(vmid: Optional[int] = None):
    proxmox = await ProxmoxAPIManager.get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')
    executor = ThreadPoolExecutor()

    try:
        if vmid:
            detailed_vm_info = await asyncio.get_event_loop().run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vmid).config.get())
            return detailed_vm_info
        else:
            vms = await asyncio.get_event_loop().run_in_executor(executor, lambda: proxmox.nodes(node).qemu.get())
            vm_details = []
            for vm in vms:
                vm_info = await asyncio.get_event_loop().run_in_executor(executor, lambda vm=vm: proxmox.nodes(node).qemu(vm['vmid']).config.get())
                vm_details.append({
                    'vmid': vm['vmid'],
                    'name': vm.get('name', 'N/A'),
                    'status': vm.get('status', 'N/A'),
                    'cores': vm_info.get('cores', 'N/A'),
                    'memory': vm_info.get('memory', 'N/A'),
                    'ipconfig0': vm_info.get('ipconfig0', 'N/A'),
                })
            return vm_details
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des informations des VMs: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

# Exécution de l'application avec Uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

