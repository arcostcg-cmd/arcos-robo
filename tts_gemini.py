#!/usr/bin/env python3
"""Narração com a voz de IA do Google (Gemini TTS), usando a GEMINI_API_KEY do GitHub Secrets.

Lê pedidos/tts/<id>.json  {"id", "texto", "voz": "Puck", "estilo": "..."}  e grava videos/audio/<id>.wav.
Escolhe sozinho o modelo de voz (TTS) mais novo disponível na conta.
"""
import base64
import json
import os
import sys
import wave
from pathlib import Path

import requests

import seguranca  # noqa: F401 (logs sem chave)

BASE = Path(__file__).resolve().parent
API = "https://generativelanguage.googleapis.com/v1beta"


def modelos_tts(chave):
    r = requests.get(f"{API}/models", headers={"x-goog-api-key": chave}, params={"pageSize": 200}, timeout=30)
    r.raise_for_status()
    nomes = [m["name"].split("/")[-1] for m in r.json().get("models", []) if "tts" in m["name"].lower()]
    # mais nova primeiro; "pro" por último (no plano grátis costuma dar 429)
    return sorted(nomes, key=lambda n: ("pro" not in n, "lite" not in n, n), reverse=True)


def gerar(pedido, chave, modelos):
    instr = pedido.get("estilo", "")
    texto = f"{instr}\n\n{pedido['texto']}" if instr else pedido["texto"]
    corpo = {"contents": [{"parts": [{"text": texto}]}],
             "generationConfig": {"responseModalities": ["AUDIO"],
                                  "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig":
                                                                   {"voiceName": pedido.get("voz", "Puck")}}}}}
    ultimo = None
    for m in modelos:
        r = requests.post(f"{API}/models/{m}:generateContent", headers={"x-goog-api-key": chave}, json=corpo,
                          timeout=180)
        if r.status_code != 200:
            ultimo = f"{m}: HTTP {r.status_code} {r.text[:200]}"
            print("tentei", ultimo)
            continue
        parte = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
        dados = base64.b64decode(parte["data"])
        tipo = parte.get("mimeType", "")
        if "wav" in tipo or dados[:4] == b"RIFF":  # já veio como WAV
            import io
            with wave.open(io.BytesIO(dados)) as w:
                return m, w.readframes(w.getnframes()), w.getframerate()
        taxa = 24000
        if "rate=" in tipo:
            taxa = int(tipo.split("rate=")[-1].split(";")[0])
        return m, dados, taxa
    raise SystemExit(f"nenhum modelo de voz funcionou: {ultimo}")


def main():
    chave = os.environ["GEMINI_API_KEY"]
    modelos = modelos_tts(chave)
    print("modelos de voz:", modelos)
    saida = BASE / "videos" / "audio"
    saida.mkdir(parents=True, exist_ok=True)
    for arq in sorted((BASE / "pedidos" / "tts").glob("*.json")):
        p = json.loads(arq.read_text(encoding="utf-8"))
        destino = saida / f"{p['id']}.wav"
        if destino.exists() and not p.get("refazer"):
            continue
        m, pcm, taxa = gerar(p, chave, modelos)
        with wave.open(str(destino), "w") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(taxa)
            w.writeframes(pcm)
        print(f"ok {destino.name} ({len(pcm) / 2 / taxa:.1f} s) com {m}")


if __name__ == "__main__":
    sys.exit(main())
