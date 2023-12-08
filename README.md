## CODEBYGPT

![Logo Discord](https://zupimages.net/up/23/26/rumo.png)
[Rejoignez le Discord !](https://discord.gg/rSfTxaW)

[![Utilisateurs en ligne](https://img.shields.io/discord/347412941630341121?style=flat-square&logo=discord&colorB=7289DA)](https://discord.gg/347412941630341121)

# Utilisation : 
- Renseignez les infos du proxmox dans le fichier `.env `
- Renseignez les IPs dans le fichier `config.json` pour une utilisation automatique des IPs
  
```bash
git clone https://github.com/micferna/vm-proxmox.git
cd vm-proxmox
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
uvicorn main:app --reload
```

---
### Cloner une VM
```bash
curl -X POST http://127.0.0.1:8000/clone_vm \
     -H "Content-Type: application/json" \
     -d '{"source_vm_id": 100000, "new_vm_id": 101, "new_vm_name": "VMTESTFASTAPI", "cpu": 8, "ram": 8096, "disk_type": "sata0", "disk_size": "50G", "bridge": "vmbr0", "ipv4": "192.168.1.10/24", "ipv6": "fd00::10/64", "start_vm": false}'
```
### Avec le minimum
```bash
curl -X POST http://127.0.0.1:8000/clone_vm \
     -H "Content-Type: application/json" \
     -d '{"source_vm_id": 100000, "cpu": 8, "ram": 8096, "disk_type": "sata0", "disk_size": "50G", "start_vm": true}'
```

---
### Suprimer une VM
```bash
curl -X DELETE http://127.0.0.1:8000/delete_vm/IDVM
```
---

### Vérifier l'état d'une tâche
```bash
curl -X GET http://127.0.0.1:8000/check_status?task_id=<task_id>
```
---
### Affiche toute les VMs présent sur le proxmox
```bash
curl -X GET "http://127.0.0.1:8000/list_vms"
```
### Info détailler sur une VM
```bash
curl -X GET "http://127.0.0.1:8000/list_vms?vmid=100"
```
---
### Update une VM
### Chaque paramettre est optionnel pour les modifications
```bash
curl -X POST -H "Content-Type: application/json" -d '{
  "vm_id": 14954,
  "cpu": 4,
  "ram": 4096,
}' http://127.0.0.1:8000/update_vm_config

# Modifier uniquement le type de disque et la taille du disque
curl -X POST -H "Content-Type: application/json" -d '{
  "vm_id": 17785,
  "disk_type": "sata0",
  "disk_size": "+200G"
}' http://127.0.0.1:8000/update_vm_config

```
---
---
# A REVOIR

```bash
# Modifier uniquement les adresses IP IPv4 et IPv6
curl -X POST -H "Content-Type: application/json" -d '{
  "vm_id": 19075,
  "ipv4": "NOUVELLE_IP_IPV4",
  "ipv6": "NOUVELLE_IP_IPV6"
}' http://127.0.0.1:8000/update_vm_config
```
