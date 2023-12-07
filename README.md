## CODEBYGPT

![Logo Discord](https://zupimages.net/up/23/26/rumo.png)
[Rejoignez le Discord !](https://discord.gg/rSfTxaW)

[![Utilisateurs en ligne](https://img.shields.io/discord/347412941630341121?style=flat-square&logo=discord&colorB=7289DA)](https://discord.gg/347412941630341121)

# Utilisation : 
- Renseignez les infos du proxmox dans le fichier `.env `
- Renseignez les IPs dans le fichier `config.json` pour une utilisation automatique des IPs
  
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
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
---
---
# A REVOIR
### Update une VM
### Chaque paramettre est optionnel pour les modifications
```bash
curl -X POST http://localhost:5000/update_vm_config \
     -H "Content-Type: application/json" \
     -d '{
           "vm_id": "101",
           "cpu": "4",
           "ram": "2096",
           "disk_type": "sata0",
           "disk": "150"
         }'

curl -X POST http://localhost:5000/update_vm_config \
     -H "Content-Type: application/json" \
     -d '{
           "vm_id": "ID_DE_LA_VM",
           "cpu": "NB_DE_CORES_CPU",
           "ram": "TAILLE_DE_LA_RAM",
           "disk": "TYPE_ET_TAILLE_DU_DISQUE",
           "ipv4": "ADRESSE_IPV4",
           "ipv6": "ADRESSE_IPV6",
           "gateway_ipv4": "PASSERELLE_IPV4",
           "gateway_ipv6": "PASSERELLE_IPV6"
         }'
```
