#!/bin/bash

API_URL="http://127.0.0.1:8000"
DEFAULT_VM_ID=1000000  # ID par défaut de la VM

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
LIGHT_BLUE='\033[1;34m'
NC='\033[0m' # Pas de couleur

print_color() {
    local color=$1
    local text=$2
    echo -e "${color}${text}${NC}"
}

show_help() {
    print_color "$GREEN" "Utilisation : $0 [OPTION]"
    print_color "$YELLOW" "--help       Afficher ce message d'aide"
    print_color "$YELLOW" "--vm [1|2|3] Cloner une VM avec la configuration spécifiée"
    print_color "$YELLOW" "--remove [ID]   Supprimer la VM avec l'ID spécifié"
    print_color "$YELLOW" "--list         Lister toutes les VMs"
    print_color "$YELLOW" "--dns [NOM]   Spécifier le nom DNS de la VM à cloner (facultatif)"
}

# Fonction pour cloner une VM
clone_vm() {
    local config=""
    local vm_id=$DEFAULT_VM_ID
    local new_vm_name=""
    local dns_name=""

    while [[ $# -gt 0 ]]; do
        key="$1"

        case $key in
            --dns)
                dns_name="$2"
                shift
                shift
                ;;
            *)
                case $config in
                    "") config="$1" ;;
                    *) shift ;;
                esac
                shift
                ;;
        esac
    done

    if [ -z "$config" ]; then
        echo "Configuration manquante"
        exit 1
    fi

    case $config in
        1) cpu=1; ram=1024; disk_size="25G" ;;
        2) cpu=2; ram=2048; disk_size="40G" ;;
        3) cpu=4; ram=8096; disk_size="50G" ;;
        *) echo "Configuration invalide"; exit 1 ;;
    esac

    if [ -n "$dns_name" ]; then
        new_vm_name="$dns_name"
    fi

    json_data="{\"source_vm_id\": $vm_id, \"new_vm_name\": \"$new_vm_name\", \"cpu\": $cpu, \"ram\": $ram, \"disk_type\": \"sata0\", \"disk_size\": \"$disk_size\", \"start_vm\": true}"

    response=$(curl -s -X POST "$API_URL/clone_vm" \
        -H "Content-Type: application/json" \
        -d "$json_data")

    task_id=$(echo $response | jq -r '.task_id')

    if [ "$task_id" == "null" ]; then
        print_color "$RED" "Erreur lors du clonage de la VM. Task ID est null."
        return 1
    fi

    print_color "$GREEN" "VM clonée. Task ID: $task_id"
    print_color "$YELLOW" "En attente des informations de la VM..."

    while :; do
        if [ -z "$task_id" ]; then
            print_color "$RED" "Erreur lors du clonage de la VM. Task ID est vide."
            break
        fi

        vm_info=$(curl -s "$API_URL/check_status?task_id=$task_id")

        task_info_type=$(echo $vm_info | jq -r '.task_info | type')

        if [[ $task_info_type == "object" ]]; then
            status=$(echo $vm_info | jq -r '.task_info.status')

            if [[ $status == "Completed" ]]; then
                ipv4=$(echo $vm_info | jq -r '.task_info.ipv4')
                ipv6=$(echo $vm_info | jq -r '.task_info.ipv6')
                print_color "$GREEN" "Informations de la VM reçues :"
                echo -e "${PURPLE}IPv4: ${LIGHT_BLUE}$ipv4${NC}"
                echo -e "${PURPLE}IPv6: ${LIGHT_BLUE}$ipv6${NC}"
                break
            else
                print_color "$RED" "En attente... (Statut: $status)"
            fi
        else
            print_color "$RED" "En attente... (Statut: $(echo $vm_info | jq -r '.task_info'))"
        fi
        sleep 5
    done

}

list_vms() {
    local response=$(curl -s -X GET "$API_URL/list_vms")
    echo "$response" | jq -r '.[] | [.vmid, .name, .status, .cores, .memory, .ipconfig0] | @tsv' | 
    awk -v RED="\033[0;31m" -v GREEN="\033[0;32m" -v YELLOW="\033[1;33m" -v LIGHT_BLUE="\033[1;34m" -v NC="\033[0m" '
    BEGIN {
        print YELLOW "VMID\tNAME\t\tSTATUS\tCORES\tMEMORY\tIP CONFIG" NC;
    }
    {
        printf("%s%-5s\t%-15s\t%-7s\t%-5s\t%-6s\t%s%s\n", (index($3, "running") ? GREEN : RED), $1, $2, $3, $4, $5, LIGHT_BLUE, $6);
    }'
}

# Fonction pour supprimer une ou plusieurs VMs
delete_vm() {
    for vm_id in "$@"; do
        local response=$(curl -s -X DELETE "${API_URL}/delete_vm/$vm_id")
        local task_id=$(echo $response | jq -r '.task_id')

        if [ -n "$task_id" ]; then
            echo "Suppression de la VM $vm_id initiée. Task ID: $task_id"
        else
            echo "Erreur lors de la tentative de suppression de la VM $vm_id."
        fi
    done
}

# Analyse des arguments
if [ $# -eq 0 ]; then
    show_help
    exit 1
fi

case $1 in
    --help)
        show_help
        ;;
    --vm)
        clone_vm $2 "${@:3}"
        ;;
    --remove)
        echo "Option --remove détectée"  # Débogage
        shift
        delete_vm "$@"
        ;;
    --list)
        list_vms
        ;;
    *)
        echo "Option inconnue: $1"  # Débogage
        show_help
        exit 1
        ;;
esac



#curl -X POST http://127.0.0.1:8000/clone_vm \
#     -H "Content-Type: application/json" \
#     -d '{"source_vm_id": 1000000, "new_vm_name": "VMTESTFASTAPI", "cpu": 8, "ram": 8096, "disk_type": "sata0", "disk_size": "50G", "start_vm": true}'