from flask import Flask, request, jsonify
import proxmoxer
import os
from dotenv import load_dotenv
import logging
import random
import threading
import time
import uuid

from queue import Queue
from threading import Thread

# Configuration du journal
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)

# Stockage des tâches asynchrones
tasks = {}
task_queue = Queue()

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

def is_ip_used(proxmox, node, ip_address):
    vms = proxmox.nodes(node).qemu.get()
    for vm in vms:
        vmid = vm['vmid']
        config = proxmox.nodes(node).qemu(vmid).config.get()
        ipconfig0 = config.get('ipconfig0', '')
        if ip_address in ipconfig0:
            return True
    return False

def generate_unique_vmid(proxmox, node, min_vmid=10000, max_vmid=20000):
    while True:
        vmid = random.randint(min_vmid, max_vmid)
        try:
            proxmox.nodes(node).qemu(vmid).status.current.get()
            logger.debug(f"vmid {vmid} existe déjà, en générant un nouveau...")
        except proxmoxer.ResourceException:
            logger.debug(f"vmid {vmid} généré avec succès.")
            return vmid

def process_task_queue():
    while True:
        task = task_queue.get()
        try:
            task['func'](*task['args'], **task['kwargs'])
            tasks[task['task_id']] = 'Completed'
        except Exception as e:
            logger.error(f"Erreur lors de l'exécution de la tâche {task['task_id']}: {e}")
            tasks[task['task_id']] = f'Error: {str(e)}'
        finally:
            task_queue.task_done()

def async_task_wrapper(task_id, func, *args, **kwargs):
    task = {
        'task_id': task_id,
        'func': func,
        'args': args,
        'kwargs': kwargs
    }
    tasks[task_id] = 'In Progress'
    task_queue.put(task)

def clone_vm_async(data, proxmox, node):
    new_vm_id = data.get('new_vm_id', generate_unique_vmid(proxmox, node))
    new_vm_name = data.get('new_vm_name', f"MACHINE-{new_vm_id}")
    bridge = data.get('bridge')

    clone_response = proxmox.nodes(node).qemu(data['source_vm_id']).clone.create(newid=new_vm_id, name=new_vm_name)

    vm_config = {
        'cores': data.get('cpu'),
        'memory': data.get('ram')
    }
    proxmox.nodes(node).qemu(new_vm_id).config.put(**vm_config)

    if 'disk_type' in data and 'disk_size' in data:
        proxmox.nodes(node).qemu(new_vm_id).resize.put(disk=data['disk_type'], size=data['disk_size'])

    # Récupérer la configuration complète de la VM
    full_vm_config = proxmox.nodes(node).qemu(new_vm_id).config.get()

    if bridge:
        # Mettre à jour la configuration réseau avec le bridge spécifié
        network_config = full_vm_config.get('net0', '')
        if network_config:
            new_network_config = network_config.split(',')
            new_network_config = [config if not config.startswith('bridge=') else f'bridge={bridge}' for config in new_network_config]
            proxmox.nodes(node).qemu(new_vm_id).config.put(net0=','.join(new_network_config))

    ipv4_config = f"{data['ipv4']}/24,gw={data['gateway_ipv4']}"
    ipv6_config = f"{data['ipv6']},gw6={data['gateway_ipv6']}"
    update_vm_network_config(proxmox, node, new_vm_id, ipv4_config, ipv6_config)

    if data.get('start_vm'):
        proxmox.nodes(node).qemu(new_vm_id).status.start.post()

def update_vm_network_config_async(data, proxmox, node):
    vm_id = data['vm_id']
    bridge = data.get('bridge')
    ipv4_config = data.get('ipv4')
    ipv6_config = data.get('ipv6')

    # Vérifier l'état de la VM
    vm_status = proxmox.nodes(node).qemu(vm_id).status.current.get()
    vm_was_running = vm_status['status'] == 'running'
    if vm_was_running:
        # Arrêter la VM pour modifier la configuration
        proxmox.nodes(node).qemu(vm_id).status.stop.post()
        time.sleep(10)

    # Récupérer et modifier la configuration réseau
    full_vm_config = proxmox.nodes(node).qemu(vm_id).config.get()
    network_config = full_vm_config.get('net0', '')
    if network_config:
        new_network_config = network_config.split(',')
        new_network_config = [config if not config.startswith('bridge=') else f'bridge={bridge}' for config in new_network_config]
        proxmox.nodes(node).qemu(vm_id).config.put(net0=','.join(new_network_config))

    # Mise à jour de l'adresse IP si spécifiée
    if ipv4_config or ipv6_config:
        update_vm_network_config(proxmox, node, vm_id, ipv4_config, ipv6_config)

    # Redémarrer la VM si elle était en cours d'exécution
    if vm_was_running:
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

    ipv4 = data.get('ipv4')
    ipv6 = data.get('ipv6')

    # Vérifier si les adresses IP sont déjà utilisées
    if is_ip_used(proxmox, node, ipv4) or is_ip_used(proxmox, node, ipv6):
        return jsonify({'error': 'Adresse IP déjà utilisée'}), 400

    task_id = uuid.uuid4().hex
    async_task_wrapper(task_id, clone_vm_async, data, proxmox, node)
    return jsonify({'task_id': task_id})

@app.route('/update_vm_config', methods=['POST'])
def update_vm_config():
    data = request.json
    proxmox = get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')
    task_id = uuid.uuid4().hex
    async_task_wrapper(task_id, update_vm_config_async, data, proxmox, node)
    return jsonify({'task_id': task_id})

@app.route('/delete_vm', methods=['DELETE'])
def delete_vm():
    vm_id = request.args.get('vm_id')
    proxmox = get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')
    task_id = uuid.uuid4().hex
    async_task_wrapper(task_id, delete_vm_async, vm_id, proxmox, node)
    return jsonify({'task_id': task_id})

@app.route('/check_status', methods=['GET'])
def check_status():
    task_id = request.args.get('task_id')
    status = tasks.get(task_id, 'Unknown Task ID')
    return jsonify({'task_id': task_id, 'status': status})

@app.route('/list_vms', methods=['GET'])
@app.route('/list_vms/<int:vmid>', methods=['GET'])  # Route pour un VMID spécifique
def list_vms(vmid=None):
    proxmox = get_proxmox_api()
    node = os.getenv('PROXMOX_NODE')

    try:
        if vmid:
            # Récupérer les informations brutes pour une VM spécifique
            detailed_vm_info = proxmox.nodes(node).qemu(vmid).config.get()
            return jsonify(detailed_vm_info)
        else:
            # Récupérer la liste de toutes les VMs avec des informations détaillées
            vms = proxmox.nodes(node).qemu.get()
            vm_details = []

            for vm in vms:
                vmid = vm['vmid']
                vm_info = proxmox.nodes(node).qemu(vmid).config.get()

                vm_details.append({
                    'vmid': vmid,
                    'name': vm.get('name', 'N/A'),
                    'status': vm.get('status', 'N/A'),
                    'cores': vm_info.get('cores', 'N/A'),
                    'memory': vm_info.get('memory', 'N/A'),
                    'ipconfig0': vm_info.get('ipconfig0', 'N/A'),
                    # Ajoutez d'autres champs selon vos besoins
                })

            return jsonify(vm_details)

    except Exception as e:
        logger.error(f"Erreur lors de la récupération des informations des VMs: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    task_processor_thread = Thread(target=process_task_queue, daemon=True)
    task_processor_thread.start()
    app.run(debug=True, host="0.0.0.0")
