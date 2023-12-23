#!/bin/bash

# Vérifiez si la clé de chiffrement est fournie
if [ -z "$ENCRYPTION_KEY" ]; then
    echo "La clé de chiffrement est manquante"
    exit 1
fi

# Chemin du fichier .env à chiffrer
ENV_FILE=".env"

# Vérifiez si le fichier .env existe
if [ ! -f "$ENV_FILE" ]; then
    echo "Le fichier $ENV_FILE n'existe pas"
    exit 1
fi

# Chiffrement du fichier .env
openssl enc -aes-256-cbc -salt -in "$ENV_FILE" -out "${ENV_FILE}.enc" -pass pass:"$ENCRYPTION_KEY"

echo "Le fichier $ENV_FILE a été chiffré en ${ENV_FILE}.enc"
