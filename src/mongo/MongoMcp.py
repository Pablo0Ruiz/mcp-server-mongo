"""
Servidor MCP para gestionar MongoDB
Requiere: uv pip install fastmcp pymongo python-dotenv
"""

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier, RSAKeyPair
from pymongo import MongoClient
from dotenv import load_dotenv
from typing import List, Dict, Any
from pydantic import SecretStr
import os
import json
import jwt
import time



load_dotenv()
uri = os.getenv("MONGO_URI")

client = MongoClient(uri)
db = client['test']
collection = db['ecommerce']


def get_or_create_keypair():
    """Obtiene o crea el par de claves RSA"""
    private_key_env = os.environ.get('MCP_PRIVATE_KEY')
    public_key_env = os.environ.get('MCP_PUBLIC_KEY')
    
    if private_key_env and public_key_env:
        return RSAKeyPair(
            private_key=SecretStr(private_key_env),
            public_key=public_key_env
        )
    
    keypair_file = "mcp_keypair.json"

    if os.path.exists(keypair_file):
        
        with open(keypair_file, 'r') as f:
            data = json.load(f)
            return RSAKeyPair(
                private_key=SecretStr(data['private_key']),
                public_key=data['public_key']
            )
    else:
        keypair = RSAKeyPair.generate()

        private_key_str = keypair.private_key.get_secret_value()
        public_key_str = keypair.public_key

        with open(keypair_file, 'w') as f:
            json.dump({
                'private_key': private_key_str,
                'public_key': public_key_str
            }, f, indent=2)
        return keypair
    
keypair = get_or_create_keypair()
def create_long_lived_token(keypair, subject, issuer, audience, expiration_days=365):
    """Crea un token JWT con expiración personalizada"""
    now = int(time.time())
    payload = {
        "sub": subject,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + (expiration_days * 24 * 60 * 60)  
    }
    private_key = keypair.private_key.get_secret_value()
    return jwt.encode(payload, private_key, algorithm="RS256")

client_token = create_long_lived_token(
    keypair=keypair,
    subject="mongo-client",
    issuer="mongo-mcp-server",
    audience="mongo-mcp",
    expiration_days=365
)

if not os.environ.get('MCP_PRIVATE_KEY'):
    with open('client_token.txt', 'w') as f:
        f.write(client_token)
    print(f"🔑 Token guardado en client_token.txt")
    print(f"Token: {client_token}")


public_key_str = keypair.public_key

auth = JWTVerifier(
    public_key=public_key_str,
    issuer="mongo-mcp-server",
    audience="mongo-mcp"
)

mcp = FastMCP("MongoDB Manager", auth=auth)

@mcp.tool()
def list_content() -> List[Dict[str, Any]]:
    """
    Herramienta para listar todo el contenido de la colección.
    
    Returns:
        Lista de todos los documentos en la colección (convertidos a JSON serializable)
    """
    products = []
    for doc in collection.find():
        doc['_id'] = str(doc['_id'])
        products.append(doc)
    return products


@mcp.tool()
def filter_product(filtro: dict) -> Dict[str, Any]:
    """
    Busca un producto en la colección según el filtro proporcionado.
    
    Args:
        filtro: Diccionario con los criterios de búsqueda (ej: {"idProducto": 1})
        
    Returns:
        Documento encontrado o mensaje de error si no existe
    """
    doc = collection.find_one(filtro)
    
    if doc:
        doc['_id'] = str(doc['_id'])
        return doc
    else:
        return {"error": "Producto no encontrado", "filtro": filtro}


@mcp.tool()
def insert_product(producto: dict) -> str:
    """
    Inserta un nuevo producto en la colección.
    
    Args:
        producto: Diccionario con los datos del producto a insertar
        
    Returns:
        Mensaje de confirmación con el ID del producto insertado
    """
    result = collection.insert_one(producto)
    return f'Producto insertado con ID: {str(result.inserted_id)}'


@mcp.tool()
def delete_product(filtro: dict) -> str:
    """
    Elimina un producto de la colección.
    
    Args:
        filtro: Diccionario con los criterios para identificar el producto a eliminar
        
    Returns:
        Mensaje de confirmación
    """
    result = collection.delete_one(filtro)
    
    if result.deleted_count > 0:
        return f'Producto eliminado: {filtro}'
    else:
        return f'No se encontró ningún producto con el filtro: {filtro}'


@mcp.tool()
def update_product(filtro: dict, actualizacion: dict) -> str:
    """
    Actualiza un producto en la colección.
    
    Args:
        filtro: Diccionario con los criterios para identificar el producto
        actualizacion: Diccionario con los campos a actualizar (sin $set, se añade automáticamente)
        
    Returns:
        Mensaje de confirmación
        
    Ejemplo:
        filtro = {"idProducto": 1}
        actualizacion = {"precioUnitarioUSD": 50, "nombre": "Nuevo Nombre"}
    """
    result = collection.update_one(
        filtro,
        {"$set": actualizacion}
    )
    
    if result.matched_count > 0:
        return f'Producto actualizado. Modificados: {result.modified_count} campo(s)'
    else:
        return f'No se encontró ningún producto con el filtro: {filtro}'


@mcp.tool()
def count_products(filtro: dict = None) -> int:
    """
    Cuenta los productos en la colección.
    
    Args:
        filtro: Diccionario opcional con criterios de filtrado
        
    Returns:
        Número de productos que coinciden con el filtro
    """
    if filtro is None:
        filtro = {}
    
    return collection.count_documents(filtro)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    
    mcp.run(transport="http", host=host, port=port, path="/mcp")
