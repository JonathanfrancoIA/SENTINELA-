#!/usr/bin/env python3
"""
SENTINELA — Módulo de Notificação Automática
============================================
Fecha o ciclo do sistema: ao detectar um alerta CRÍTICO (satélite/áudio)
ou uma fusão CONFIRMADO (olho + ouvido concordam), dispara notificação
para os órgãos responsáveis (IBAMA / brigada local) por:

    • E-mail (SMTP, ex. Gmail)
    • Telegram (bot)

Credenciais são lidas do .env — NUNCA são gravadas em código.

Variáveis de ambiente esperadas (.env):
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=seu_email@gmail.com
    SMTP_PASS=senha_de_app          # use "App Password" do Gmail, não a senha normal
    SMTP_DEST=destino@ibama.gov.br   # pode ser lista separada por vírgula
    TELEGRAM_TOKEN=123456:ABC-DEF...
    TELEGRAM_CHAT_ID=-1001234567890

Uso programático:
    from notificacao.notificar import notificar_alerta
    notificar_alerta({
        "tipo": "FUSAO",
        "status": "CONFIRMADO",
        "municipio": "Apuí",
        "estado": "AM",
        "area_ha": 126.8,
        "confianca": 0.91,
        "lat": -3.456, "lon": -62.164,
        "fonte": "Satélite (NDVI) + Áudio (ESP32)",
    })

Uso CLI (teste rápido — só envia se houver credenciais no .env):
    python src/notificacao/notificar.py --teste
    python src/notificacao/notificar.py --teste --dry-run   # não envia, só mostra
"""

import os
import sys
import json
import argparse
import smtplib
import ssl
import urllib.request
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Carrega .env se python-dotenv estiver disponível (opcional)
try:
    from dotenv import load_dotenv
    from pathlib import Path
    # .env na raiz do projeto (3 níveis acima deste arquivo)
    raiz = Path(__file__).resolve().parent.parent.parent
    load_dotenv(raiz / ".env")
except Exception:
    pass


# ─────────────────────────────────────────────────────────────
# Critério de disparo
# ─────────────────────────────────────────────────────────────
def deve_notificar(alerta: dict) -> bool:
    """Regra de negócio: só notifica eventos de alta gravidade."""
    sev = str(alerta.get("severidade", "")).upper()
    status = str(alerta.get("status", "")).upper()
    conf = float(alerta.get("confianca", 0) or 0)
    return (
        sev == "CRITICO"
        or status == "CONFIRMADO"
        or conf >= float(os.getenv("CONF_ALTA", 0.85))
    )


# ─────────────────────────────────────────────────────────────
# Formatação da mensagem
# ─────────────────────────────────────────────────────────────
def _formatar_texto(alerta: dict) -> str:
    lat, lon = alerta.get("lat"), alerta.get("lon")
    maps = (f"https://www.google.com/maps?q={lat},{lon}"
            if lat is not None and lon is not None else "—")
    return (
        "🚨 SENTINELA — ALERTA DE DESMATAMENTO\n"
        "────────────────────────────────────\n"
        f"Tipo:       {alerta.get('tipo', '—')}\n"
        f"Status:     {alerta.get('status', alerta.get('severidade', '—'))}\n"
        f"Local:      {alerta.get('municipio', '—')} / {alerta.get('estado', '—')}\n"
        f"Área:       {alerta.get('area_ha', '—')} ha\n"
        f"Confiança:  {float(alerta.get('confianca', 0) or 0):.0%}\n"
        f"Fonte:      {alerta.get('fonte', '—')}\n"
        f"Coordenada: {lat}, {lon}\n"
        f"Mapa:       {maps}\n"
        f"Detectado:  {datetime.now().strftime('%d/%m/%Y %H:%M')}\n"
        "────────────────────────────────────\n"
        "Ação recomendada: verificação e fiscalização prioritária."
    )


def _formatar_html(alerta: dict) -> str:
    lat, lon = alerta.get("lat"), alerta.get("lon")
    maps = (f"https://www.google.com/maps?q={lat},{lon}"
            if lat is not None and lon is not None else "#")
    cor = "#ff2020"
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:560px;border:1px solid {cor};
                border-radius:10px;overflow:hidden">
      <div style="background:{cor};color:#fff;padding:14px 18px;font-size:18px;font-weight:bold">
        🚨 SENTINELA — Alerta de Desmatamento
      </div>
      <div style="padding:18px;color:#222">
        <table style="width:100%;border-collapse:collapse;font-size:14px">
          <tr><td><b>Tipo</b></td><td>{alerta.get('tipo','—')}</td></tr>
          <tr><td><b>Status</b></td><td style="color:{cor}"><b>{alerta.get('status', alerta.get('severidade','—'))}</b></td></tr>
          <tr><td><b>Local</b></td><td>{alerta.get('municipio','—')} / {alerta.get('estado','—')}</td></tr>
          <tr><td><b>Área</b></td><td>{alerta.get('area_ha','—')} ha</td></tr>
          <tr><td><b>Confiança</b></td><td>{float(alerta.get('confianca',0) or 0):.0%}</td></tr>
          <tr><td><b>Fonte</b></td><td>{alerta.get('fonte','—')}</td></tr>
          <tr><td><b>Coordenada</b></td><td>{lat}, {lon}</td></tr>
        </table>
        <p style="margin-top:16px">
          <a href="{maps}" style="background:{cor};color:#fff;padding:10px 16px;
             text-decoration:none;border-radius:6px">📍 Ver no mapa</a>
        </p>
        <p style="color:#888;font-size:12px">
          Detectado em {datetime.now().strftime('%d/%m/%Y %H:%M')} ·
          Ação recomendada: fiscalização prioritária.
        </p>
      </div>
    </div>
    """


# ─────────────────────────────────────────────────────────────
# Canais de envio
# ─────────────────────────────────────────────────────────────
def enviar_email(alerta: dict, dry_run: bool = False) -> bool:
    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USER")
    senha = os.getenv("SMTP_PASS")
    destino = os.getenv("SMTP_DEST", user)

    if not (user and senha and destino):
        print("  [e-mail] credenciais ausentes no .env (SMTP_USER/SMTP_PASS/SMTP_DEST) — pulando")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🚨 SENTINELA — Alerta {alerta.get('status', alerta.get('severidade','')).upper()} em {alerta.get('municipio','?')}"
    msg["From"] = user
    msg["To"] = destino
    msg.attach(MIMEText(_formatar_texto(alerta), "plain", "utf-8"))
    msg.attach(MIMEText(_formatar_html(alerta), "html", "utf-8"))

    if dry_run:
        print(f"  [e-mail] DRY-RUN → enviaria para {destino}")
        return True

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port) as srv:
            srv.starttls(context=ctx)
            srv.login(user, senha)
            srv.sendmail(user, [d.strip() for d in destino.split(",")], msg.as_string())
        print(f"  [e-mail] ✅ enviado para {destino}")
        return True
    except Exception as e:
        print(f"  [e-mail] ❌ falha: {e}")
        return False


def enviar_telegram(alerta: dict, dry_run: bool = False) -> bool:
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        print("  [telegram] TELEGRAM_TOKEN/TELEGRAM_CHAT_ID ausentes no .env — pulando")
        return False

    texto = _formatar_texto(alerta)
    if dry_run:
        print(f"  [telegram] DRY-RUN → enviaria para chat {chat_id}")
        return True

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        dados = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": texto,
            "disable_web_page_preview": "false",
        }).encode()
        with urllib.request.urlopen(url, data=dados, timeout=15) as resp:
            ok = resp.status == 200
        print(f"  [telegram] {'✅ enviado' if ok else '❌ status ' + str(resp.status)} (chat {chat_id})")
        return ok
    except Exception as e:
        print(f"  [telegram] ❌ falha: {e}")
        return False


# ─────────────────────────────────────────────────────────────
# Orquestrador
# ─────────────────────────────────────────────────────────────
def notificar_alerta(alerta: dict, forcar: bool = False, dry_run: bool = False) -> dict:
    """
    Avalia o alerta e dispara notificações pelos canais configurados.

    Args:
        alerta:  dict com chaves tipo/status/severidade/municipio/estado/
                 area_ha/confianca/lat/lon/fonte
        forcar:  ignora o critério deve_notificar() e envia mesmo assim
        dry_run: não envia de fato — só simula (útil para testes/demo)

    Returns:
        dict {"notificado": bool, "email": bool, "telegram": bool}
    """
    if not forcar and not deve_notificar(alerta):
        print("ℹ️  Alerta abaixo do limiar de notificação — não disparado.")
        return {"notificado": False, "email": False, "telegram": False}

    print(f"🚨 Disparando notificação ({'DRY-RUN' if dry_run else 'REAL'}) …")
    ok_email = enviar_email(alerta, dry_run=dry_run)
    ok_tg = enviar_telegram(alerta, dry_run=dry_run)
    return {"notificado": ok_email or ok_tg, "email": ok_email, "telegram": ok_tg}


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="SENTINELA — notificação de alertas")
    parser.add_argument("--teste", action="store_true",
                        help="dispara um alerta de exemplo (CONFIRMADO)")
    parser.add_argument("--dry-run", action="store_true",
                        help="não envia de fato, apenas simula")
    parser.add_argument("--json", type=str,
                        help="caminho de um .json com o dict do alerta")
    args = parser.parse_args()

    if args.json:
        with open(args.json, "r", encoding="utf-8") as fh:
            alerta = json.load(fh)
    elif args.teste:
        alerta = {
            "tipo": "FUSAO",
            "status": "CONFIRMADO",
            "municipio": "Apuí",
            "estado": "AM",
            "area_ha": 126.8,
            "confianca": 0.91,
            "lat": -3.456396, "lon": -62.164257,
            "fonte": "Satélite (Sentinel-2 NDVI) + Áudio (ESP32)",
        }
    else:
        parser.print_help()
        sys.exit(0)

    resultado = notificar_alerta(alerta, forcar=True, dry_run=args.dry_run)
    print("\nResultado:", json.dumps(resultado, ensure_ascii=False))


if __name__ == "__main__":
    main()
