# Arcos TCG · robô

Robô do Arcos TCG com dois sistemas internos:

- **Sistema de Promoções:** coleta preços só em lojas aprovadas, confere, aplica cupons testados, barra golpes e posta carrosséis no Telegram e no Instagram.
- **Sistema de Notícias e Rumores:** lê fontes do mundo todo a cada 10 minutos, traduz com o Gemini e posta stories e posts (rumor sempre marcado como "Rumor").

## Ligar o robô
1. Em **Settings > Secrets and variables > Actions > Secrets**, cadastre:
   `TELEGRAM_TOKEN`, `INSTAGRAM_TOKEN`, `GEMINI_API_KEY`.
2. Em **Variables**, crie `ROBO_ATIVO` = `true`.
3. Edite `config.yaml` (canal do Telegram, conta do Instagram, lojas e produtos).

Tokens **nunca** vão no código: só nos Secrets.

Comandos: `python arcos.py ajuda`.
