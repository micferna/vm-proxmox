# Fichier ip_manager.py

import asyncio
import json
import ipaddress
import logging

class IPManager:
    def __init__(self, ip_pools):
        self.ip_pools = ip_pools
        self.locked_ips = set()
        self.lock = asyncio.Lock()
        self.logger = logging.getLogger(__name__)

    @classmethod
    def load_ip_pools(cls, filename='config.json'):
        try:
            with open(filename, 'r') as file:
                data = json.load(file)
            return data['pools']
        except FileNotFoundError:
            cls.logger.error(f"Fichier {filename} non trouvé.")
            raise
        except json.JSONDecodeError as e:
            cls.logger.error(f"Erreur lors de l'analyse du JSON : {e}")
            raise
        except KeyError:
            cls.logger.error("La clé 'pools' est manquante dans le fichier de configuration.")
            raise

    async def is_ip_used(self, proxmox, node, ip_address):
        vms = proxmox.nodes(node).qemu.get()
        for vm in vms:
            vmid = vm['vmid']
            config = proxmox.nodes(node).qemu(vmid).config.get()
            ipconfig = config.get('ipconfig0', '')
            if f"ip={ip_address}" in ipconfig or f"ip6={ip_address}" in ipconfig:
                #logger.debug(f"Adresse IP {ip_address} déjà utilisée par VM {vmid} (ipconfig0: {ipconfig})")
                return True
        #logger.debug(f"Adresse IP {ip_address} libre")
        return False
    
    async def find_free_ip(self, proxmox, node, ip_network, gateway_ip):
        async with self.lock:
            network = ipaddress.ip_network(ip_network)
            gateway_ip_obj = ipaddress.ip_address(gateway_ip)

        for ip in network.hosts():
            if ip == gateway_ip_obj or ip in self.locked_ips:
                continue
            ip_str = str(ip)
            if not await self.is_ip_used(proxmox, node, ip_str):
                self.locked_ips.add(ip_str)
                self.logger.debug(f"Adresse IP {ip_str} attribuée.")
                return ip_str

        self.logger.warning(f"Aucune adresse IP libre trouvée dans le pool {ip_network}")
        raise RuntimeError(f"Aucune adresse IP libre trouvée dans le pool {ip_network}")


    def unlock_ip(self, ip_address):
        self.locked_ips.discard(ip_address)  # Déverrouiller l'adresse IP
 
 