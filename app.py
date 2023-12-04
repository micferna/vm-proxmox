from flask import Flask, request, jsonify
import proxmoxer
import os
from dotenv import load_dotenv
import logging
import random
import threading
import time
import uuid

# Configuration du journal
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)

# Stockage des tâches asynchrones
tasks = {}

def get_proxmox_api():
    host = os.getenv('PROXMOX_HOST')
    user = os.getenv('PROXMOX_USER')
    password = os.getenv('PROXMOX_PASSWORD')
    return proxmoxer.ProxmoxAPI(host, user=user, password=password, verify_ssl=True)

def update_vm_network_config(proxmox, node, vmid, ipv4_config, ipv6_config):
    try:
        ipconfig0 = f"ip={ipv4_config}"
        if ipv6_config:
            ipconfig0 += f",ip6={ipv6_config}"
        response = proxmox.nodes(node).qemu(vmid).config.put(ipconfig0=ipconfig0)
        logger.debug(f"Réponse de la mise à jour de la configuration réseau: {response}")
        return response
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la configuration réseau: {e}")
        raise

def generate_unique_vmid(proxmox, node, min_vmid=10000, max_vmid=20000):
    while True:
        vmid = random.randint(min_vmid, max_vmid)
        try:
            proxmox.nodes(node).qemu(vmid).status.current.get()
            logger.debug(f"vmid {vmid} existe déjà, en générant un nouveau...")
        except proxmoxer.ResourceException:
            logger.debug(f"vmid {vmid} généré avec succès.")
            return vmid

def async_task_wrapper(task_id, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
        tasks[task_id] = 'Completed'
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de la tâche {task_id}: {e}")
        tasks[task_id] = f'Error: {str(e)}'

def clone_vm_async(data, proxmox, node):
    new_vm_id = data.get('new_vm_id', generate_unique_vmid(proxmox, node))
    new_vm_name = data.get('new_vm_name', f"MACHINE-{new_vm_id}")

    clone_response = proxmox.nodes(node).qemu(data['source_vm_id']).clone.create(newid=new_vm_id, name=new_vm_name)

    vm_config = {
        'cores': data.get('cpu'),
        'memory': data.get('ram')
    }
    proxmox.nodes(node).qemu(new_vm_id).config.put(**vm_config)

    if 'disk_type' in data and 'disk_size' in data:
        proxmox.nodes(node).qemu(new_vm_id).resize.put(disk=data['disk_type'], size=data['disk_size'])

    ipv4_config = f"{data['ipv4']}/24,gw={data['gateway_ipv4']}"
    ipv6_config = f"{data['ipv6']},gw6={data['gateway_ipv6']}"
    update_vm_network_config(proxmox, node, new_vm_id, ipv4_config, ipv6_config)

    if data.get('start_vm'):
        proxmox.nodes(node).qemu(new_vm_id).status.start.post()


def update_vm_config_async(data, proxmox, node):
    vm_id = data['vm_id']
    logger.debug(f"Mise à jour de la configuration de la VM {vm_id}")

    # Vérifier l'état actuel de la VM
    vm_status = proxmox.nodes(node).qemu(vm_id).status.current.get()
    vm_was_running = vm_status['status'] == 'running'
    logger.debug(f"État initial de la VM {vm_id}: {'en cours d’exécution' if vm_was_running else 'arrêtée'}")

    # Arrêter la VM si elle est en cours d'exécution
    if vm_was_running:
        logger.debug(f"Arrêt de la VM {vm_id}")
        proxmox.nodes(node).qemu(vm_id).status.stop.post()
        time.sleep(10)  # Attendre l'arrêt complet de la VM

    # Mise à jour de la configuration CPU et RAM
    vm_config = {
        'cores': data.get('cpu'),
        'memory': data.get('ram')
    }
    proxmox.nodes(node).qemu(vm_id).config.put(**vm_config)
    logger.debug(f"Configuration CPU et RAM mise à jour pour la VM {vm_id}")

    # Gestion du redimensionnement du disque
    if 'disk_type' in data and 'disk' in data:
        disk_size = data['disk']
        if not disk_size.endswith('G'):
            disk_size += 'G'  # Assurez-vous que la taille du disque est en gigaoctets
        proxmox.nodes(node).qemu(vm_id).resize.put(disk=data['disk_type'], size=disk_size)
        logger.debug(f"Disque redimensionné pour la VM {vm_id}")

    # Redémarrer la VM si elle était en cours d'exécution
    if vm_was_running:
        logger.debug(f"Redémarrage de la VM {vm_id}")
        proxmox.nodes(node).qemu(vm_id).status.start.post()


def delete_vm_async(vm_id, proxmox, node):
    vm_status = proxmox.nodes(node).qemu(vm_id).status.current.get()
    if vm_status.get('status') == 'running':
        proxmox.nodes(node).qemu(vm_id).status.stop.post()
        time.sleep(10)  # Attendre l'arrêt de la VM
    proxmox.nodes(node).qemu(vm_id).delete()

# Endpoints
@app.route('/clone_vm', methods=['POST'])
def clone_vm():
    data = request.json
    proxmox = get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')
    task_id = uuid.uuid4().hex
    tasks[task_id] = 'In Progress'
    threading.Thread(target=async_task_wrapper, args=(task_id, clone_vm_async, data, proxmox, node)).start()
    return jsonify({'task_id': task_id})

@app.route('/update_vm_config', methods=['POST'])
def update_vm_config():
    data = request.json
    proxmox = get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')
    task_id = uuid.uuid4().hex
    tasks[task_id] = 'In Progress'
    threading.Thread(target=async_task_wrapper, args=(task_id, update_vm_config_async, data, proxmox, node)).start()
    return jsonify({'task_id': task_id})

@app.route('/delete_vm', methods=['DELETE'])
def delete_vm():
    vm_id = request.args.get('vm_id')
    proxmox = get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')
    task_id = uuid.uuid4().hex
    tasks[task_id] = 'In Progress'
    threading.Thread(target=async_task_wrapper, args=(task_id, delete_vm_async, vm_id, proxmox, node)).start()
    return jsonify({'task_id': task_id})

@app.route('/check_status', methods=['GET'])
def check_status():
    task_id = request.args.get('task_id')
    status = tasks.get(task_id, 'Unknown Task ID')
    return jsonify({'task_id': task_id, 'status': status})

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0")
