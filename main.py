from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from typing import Optional
from fastapi.responses import JSONResponse
import os,logging,random,uuid,json,ipaddress,asyncio,proxmoxer

app = FastAPI()

# Configuration du journal
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

# Stockage des tâches asynchrones
tasks = {}
task_queue = asyncio.Queue()

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

def load_ip_pools(filename='config.json'):
    with open(filename, 'r') as file:
        data = json.load(file)
    return data['pools']

# Initialisation des pools d'IP
ip_pools = load_ip_pools('config.json')

# Exemple de fonction asynchrone pour Proxmox API
async def get_proxmox_api():
    host = os.getenv('PROXMOX_HOST')
    user = os.getenv('PROXMOX_USER')
    password = os.getenv('PROXMOX_PASSWORD')
    return proxmoxer.ProxmoxAPI(host, user=user, password=password, verify_ssl=True)

async def update_vm_network_config(proxmox, node, vmid, bridge, ipv4_config=None, ipv4_gateway=None, ipv6_config=None, ipv6_gateway=None):
    net_config = f"model=virtio,bridge={bridge}"
    ipconfig0 = ''

    if ipv4_config:
        ipconfig0 += f"ip={ipv4_config}"
        if ipv4_gateway:
            ipconfig0 += f",gw={ipv4_gateway}"
    if ipv6_config:
        ipconfig0 += f",ip6={ipv6_config}"
        if ipv6_gateway:
            ipconfig0 += f",gw6={ipv6_gateway}"

    config_update = {'net0': net_config}
    if ipconfig0:
        config_update['ipconfig0'] = ipconfig0

    response = proxmox.nodes(node).qemu(vmid).config.put(**config_update)
    logger.debug(f"Réponse de la mise à jour de la configuration réseau: {response}")

async def is_ip_used(proxmox, node, ip_address):
    vms = proxmox.nodes(node).qemu.get()
    for vm in vms:
        vmid = vm['vmid']
        config = proxmox.nodes(node).qemu(vmid).config.get()
        if f"ip={ip_address}" in config.get('ipconfig0', '') or f"ip6={ip_address}" in config.get('ipconfig0', ''):
            return True
    return False

async def find_free_ip(proxmox, node, ip_network):
    for ip in ipaddress.ip_network(ip_network).hosts():
        if not await is_ip_used(proxmox, node, str(ip)):
            return str(ip)
    raise RuntimeError(f"Aucune adresse IP libre trouvée dans le pool {ip_network}")

async def generate_unique_vmid(proxmox, node, min_vmid=10000, max_vmid=20000):
    while True:
        vmid = random.randint(min_vmid, max_vmid)
        try:
            # Assurez-vous que cette opération est asynchrone si nécessaire
            await proxmox.nodes(node).qemu(vmid).status.current.get()
            logger.debug(f"vmid {vmid} existe déjà, en générant un nouveau...")
        except proxmoxer.ResourceException:
            logger.debug(f"vmid {vmid} généré avec succès.")
            return vmid

# Modifiez async_task_wrapper pour utiliser asyncio.create_task
async def async_task_wrapper(task_id, func, *args, **kwargs):
    task = {
        'task_id': task_id,
        'func': func,
        'args': args,
        'kwargs': kwargs
    }
    tasks[task_id] = 'In Progress'
    asyncio.create_task(func(*args, **kwargs))


async def clone_vm_async(task_id, data, proxmox, node, ip_pools):
    executor = ThreadPoolExecutor()
    loop = asyncio.get_running_loop()

    new_vm_id = data.get('new_vm_id')
    if new_vm_id is None:
        new_vm_id = await generate_unique_vmid(proxmox, node)
    else:
        new_vm_id = int(new_vm_id)

    # Créer un nom par défaut si nécessaire
    new_vm_name = data.get('new_vm_name')
    if not new_vm_name:
        new_vm_name = f"MACHINE-{new_vm_id}"

    # Le reste du processus de clonage...
    clone_response = proxmox.nodes(node).qemu(data['source_vm_id']).clone.create(newid=new_vm_id, name=new_vm_name)
    
    # Configuration des ressources de la VM
    vm_config = {
        'cores': data.get('cpu'),
        'memory': data.get('ram')
    }
    proxmox.nodes(node).qemu(new_vm_id).config.put(**vm_config)
    
    # Gestion de la taille du disque
    if 'disk_type' in data and 'disk_size' in data:
        proxmox.nodes(node).qemu(new_vm_id).resize.put(disk=data['disk_type'], size=data['disk_size'])

    # Configuration réseau
    bridge = data.get('bridge', 'vmbr0')
    ipv4_config = data.get('ipv4')
    ipv6_config = data.get('ipv6')

    selected_pool = ip_pools[0]  # ou une logique pour sélectionner le bon pool

    bridge = selected_pool['bridge']
    ipv4_gateway = selected_pool['gateway_ipv4']
    ipv6_gateway = selected_pool['gateway_ipv6']

    if not ipv4_config:
        ipv4_config = await find_free_ip(proxmox, node, selected_pool['network_ipv4']) + '/24'

    if not ipv6_config:
        ipv6_config = await find_free_ip(proxmox, node, selected_pool['network_ipv6']) + '/64'

    await update_vm_network_config(proxmox, node, new_vm_id, bridge, ipv4_config, ipv4_gateway, ipv6_config, ipv6_gateway)
    
    if data.get('start_vm'):
        # Démarrer la VM de manière asynchrone
        await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(new_vm_id).status.start.post())

    # Récupération de l'état et de la configuration de la VM de manière asynchrone
    vm_status = await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(new_vm_id).status.current.get())
    vm_config = await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(new_vm_id).config.get())
    ipconfig0 = vm_config.get('ipconfig0', '')

    # Extraction des adresses IP
    ipv4 = 'N/A'
    ipv6 = 'N/A'
    for part in ipconfig0.split(','):
        if part.startswith('ip='):
            ipv4 = part.split('=')[1]
        elif part.startswith('ip6='):
            ipv6 = part.split('=')[1]

    tasks[task_id] = {
        'status': 'Completed',
        'vm_status': vm_status.get('status', 'N/A'),
        'vmid': new_vm_id,
        'ipv4': ipv4,
        'ipv6': ipv6
    }

async def update_vm_config_async(data, proxmox, node):
    vm_id = data['vm_id']
    bridge = data.get('bridge')
    ipv4_config = data.get('ipv4')
    ipv6_config = data.get('ipv6')
    cpu = data.get('cpu')
    ram = data.get('ram')
    disk_type = data.get('disk_type')
    disk_size = data.get('disk_size')

    executor = ThreadPoolExecutor()
    loop = asyncio.get_running_loop()

    # Vérifier l'état actuel de la VM
    vm_status_before = await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.current.get())
    vm_was_running_before_update = vm_status_before['status'] == 'running'

    if vm_was_running_before_update:
        # Arrêter la VM si elle est en cours d'exécution
        await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.stop.post())
        await asyncio.sleep(10)

    # Mise à jour de la configuration
    update_config = {}
    if cpu is not None:
        update_config['cores'] = cpu
    if ram is not None:
        update_config['memory'] = ram
    if disk_type is not None and disk_size is not None:
        try:
            resize_param = {"disk": disk_type, "size": disk_size}
            await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).resize.put(**resize_param))
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de la taille du disque: {e}")


    if bridge or ipv4_config or ipv6_config:
        net_config = f"model=virtio,bridge={bridge}" if bridge else ""
        ipconfig0 = ''
        if ipv4_config:
            ipconfig0 += f"ip={ipv4_config}"
        if ipv6_config:
            ipconfig0 += f",ip6={ipv6_config}"
        update_config['net0'] = net_config
        if ipconfig0:
            update_config['ipconfig0'] = ipconfig0

    if update_config:
        await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).config.put(**update_config))

    # Redémarrer la VM après la mise à jour, indépendamment de son état initial
    await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.start.post())

async def delete_vm_async(vm_id, proxmox, node):
    try:
        executor = ThreadPoolExecutor()
        loop = asyncio.get_running_loop()

        # Vérification de l'état de la VM
        vm_status_response = await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.current.get())

        if vm_status_response.get("status") in ["running", "blocked"]:
            # Arrêt de la VM
            await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.stop.post())

            # Attente que la VM soit arrêtée
            while True:
                status = await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).status.current.get())
                if status.get("status") in ["stopped", "offline"]:
                    break
                await asyncio.sleep(2)  # Ajustez ce délai au besoin

        # Suppression de la VM
        await loop.run_in_executor(executor, lambda: proxmox.nodes(node).qemu(vm_id).delete())

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/clone_vm")
async def clone_vm(request: CloneVMRequest):
    proxmox = await get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')

    if (request.ipv4 and await is_ip_used(proxmox, node, request.ipv4)) or (request.ipv6 and await is_ip_used(proxmox, node, request.ipv6)):
        raise HTTPException(status_code=400, detail="Adresse IP déjà utilisée")

    task_id = uuid.uuid4().hex
    asyncio.create_task(clone_vm_async(task_id, request.dict(), proxmox, node, ip_pools))
    return {"task_id": task_id}

@app.post("/update_vm_config")
async def update_vm_config(request: UpdateVMConfigRequest):
    proxmox = await get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')
    task_id = uuid.uuid4().hex
    asyncio.create_task(update_vm_config_async(request.dict(), proxmox, node))  # Modifier ici
    return {"task_id": task_id}


@app.delete("/delete_vm/{vm_id}")
async def delete_vm(vm_id: int):
    proxmox = await get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')
    task_id = uuid.uuid4().hex
    
    # Créez une tâche asynchrone pour effectuer la suppression de la machine virtuelle
    asyncio.create_task(delete_vm_async(vm_id, proxmox, node))
    
    return {"task_id": task_id}

@app.get("/check_status")
async def check_status(task_id: str):
    task_info = tasks.get(task_id, "Unknown Task ID")
    return {"task_id": task_id, "task_info": task_info}

@app.get("/list_vms")
async def list_vms(vmid: Optional[int] = None):
    proxmox = await get_proxmox_api()
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
