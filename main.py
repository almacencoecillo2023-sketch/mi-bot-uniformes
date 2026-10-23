import os
import re
import pandas as pd
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "tu_llave_de_openai")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "tu_token_de_whatsapp")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "mi_token_secreto_123")

client = OpenAI(api_key=OPENAI_API_KEY)
MEMORIA_CLIENTES = {}
ESCUELAS_OFICIALES = ["COLEGIO PIO XII"]

def buscar_precio_en_excel(escuela, prenda, talla):
    try:
        if not os.path.exists("precios.xlsx"):
            return "Lo siento, no encontré el archivo de precios en el servidor."
        df = pd.read_excel("precios.xlsx", sheet_name=escuela.upper())
        return f"El costo para {escuela} ({prenda} talla {talla}) es de $110 pesos."
    except Exception as e:
        return f"Hubo un error al leer la lista de precios: {str(e)}"

def procesar_con_ia(mensaje_usuario, historial=""):
    instrucciones = f"""
    Eres el asistente virtual de una tienda de uniformes escolares.
    Tu objetivo es ayudar al cliente a cotizar, pero tienes una REGLA DE ORO:
    JAMÁS inventes un precio y JAMÁS des un costo si no conoces estos 3 datos del cliente:
    1. Escuela, 2. Prenda, 3. Talla
    Nuestra lista oficial de escuelas es: {ESCUELAS_OFICIALES}.
    Si el usuario escribe con errores (ej. 'pio doce'), mapealo a 'COLEGIO PIO XII'.
    Responde SIEMPRE en formato JSON con estas llaves:
    {{
        "escuela_detectada": "Nombre oficial o null",
        "prenda_detectada": "Nombre de la prenda o null",
        "talla_detectada": "Talla o null",
        "respuesta_al_cliente": "Mensaje amable pidiendo el dato que falte."
    }}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", content: instrucciones},
            {"role": "user", content: f"Historial: {historial}\nCliente: {mensaje_usuario}"}
        ],
        response_format={"type": "json_object"}
    )
    import json
    return json.loads(response.choices.message.content)

@app.route("/webhook", methods=["GET"])
def verificar_webhook():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Token de verificación inválido", 403

@app.route("/webhook", methods=["POST"])
def recibir_mensaje_whatsapp():
    data = request.get_json()
    try:
        entry = data["entry"]
        changes = entry["changes"]
        value = changes["value"]
        message = value["messages"]
        telefono = message["from"]
        texto_cliente = message["text"]["body"]
        if telefono not in MEMORIA_CLIENTES:
            MEMORIA_CLIENTES[telefono] = {"escuela": None, "prenda": None, "talla": None, "historial": ""}
        datos_sesion = MEMORIA_CLIENTES[telefono]
        resultado_ia = procesar_con_ia(texto_cliente, datos_sesion["historial"])
        if resultado_ia["escuela_detectada"]: datos_sesion["escuela"] = resultado_ia["escuela_detectada"]
        if resultado_ia["prenda_detectada"]: datos_sesion["prenda"] = resultado_ia["prenda_detectada"]
        if resultado_ia["talla_detectada"]: datos_sesion["talla"] = resultado_ia["talla_detectada"]
        datos_sesion["historial"] += f"\nCliente: {texto_cliente}\nBot: {resultado_ia['respuesta_al_cliente']}"
        if datos_sesion["escuela"] and datos_sesion["prenda"] and datos_sesion["talla"]:
            respuesta_final = buscar_precio_en_excel(datos_sesion["escuela"], datos_sesion["prenda"], datos_sesion["talla"])
            MEMORIA_CLIENTES[telefono] = {"escuela": None, "prenda": None, "talla": None, "historial": ""}
        else:
            respuesta_final = resultado_ia["respuesta_al_cliente"]
        print(f"Enviar a {telefono}: {respuesta_final}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        return jsonify({"status": "ignored"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
