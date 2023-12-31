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

    # Définir les couleurs et les styles
    local RED="\033[0;31m"
    local GREEN="\033[0;32m"
    local YELLOW="\033[1;33m"  # Texte jaune en gras
    local DARK_BLUE="\033[0;34m"  # Bleu foncé pour le nom
    local BLUE="\033[0;36m"  # Bleu clair
    local LIGHT_BLUE="\033[1;34m"  # Texte bleu clair en gras
    local BOLD="\033[1m"  # Pour le texte en gras
    local NC="\033[0m"  # Pas de couleur, réinitialiser le style

    # Ligne de séparation pour encadrer l'en-tête
    echo "--------------------------------------------------------------------------------"

    # En-tête avec couleurs
    echo -e "${YELLOW}VMID${NC}\t${DARK_BLUE}NAME${NC}\t\t${GREEN}STATUS${NC}\t\t${BLUE}CORES${NC}\t${RED}MEMORY${NC}\t${LIGHT_BLUE}IP CONFIG${NC}"

    # Ligne de séparation après l'en-tête
    echo "--------------------------------------------------------------------------------"

    # Afficher d'abord les VMs "running"
    echo "$response" | jq -r '.[] | select(.status=="running") | [.vmid, .name, .status, .cores, .memory, .ipconfig0] | @tsv' |
    awk -v RED="$RED" -v GREEN="$GREEN" -v YELLOW="$YELLOW" -v DARK_BLUE="$DARK_BLUE" -v BLUE="$BLUE" -v LIGHT_BLUE="$LIGHT_BLUE" -v BOLD="$BOLD" -v NC="$NC" '
    {
        printf("%s%s%-5s%s%s\t%s%-15s%s\t%s%-10s%s\t%s%-5s%s\t%s%-6s%s\t%s%s%s%s\n", BOLD, YELLOW, $1, NC, BOLD, DARK_BLUE, $2, NC, GREEN, $3, NC, BLUE, $4, NC, RED, $5, NC, BOLD, LIGHT_BLUE, $6, NC, BOLD);
    }'

    # Ensuite, afficher les autres VMs
    echo "$response" | jq -r '.[] | select(.status!="running") | [.vmid, .name, .status, .cores, .memory, .ipconfig0] | @tsv' |
    awk -v RED="$RED" -v GREEN="$GREEN" -v YELLOW="$YELLOW" -v DARK_BLUE="$DARK_BLUE" -v BLUE="$BLUE" -v LIGHT_BLUE="$LIGHT_BLUE" -v BOLD="$BOLD" -v NC="$NC" '
    {
        printf("%s%s%-5s%s%s\t%s%-15s%s\t%s%-10s%s\t%s%-5s%s\t%s%-6s%s\t%s%s%s%s\n", BOLD, YELLOW, $1, NC, BOLD, DARK_BLUE, $2, NC, RED, $3, NC, BLUE, $4, NC, RED, $5, NC, BOLD, LIGHT_BLUE, $6, NC, BOLD);
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
        shift
        delete_vm "$@"
        ;;
    --list)
        list_vms
        ;;
    *)
        show_help
        exit 1
        ;;
esac
