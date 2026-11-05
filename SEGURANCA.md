# Segurança da Montop TCG

## O que o robô faz sozinho
- **Trava de link (anti-golpe):** promoção só é postada com link HTTPS de loja aprovada (domínios do config + encurtadores oficiais de afiliado). Link estranho, domínio disfarçado (xn--), usuário/senha no link ou arquivo .apk/.exe = descartado e registrado.
- **IA blindada:** o texto que o Gemini escreve passa por limpeza: sem links, sem @everyone, sem HTML, sem comandos. O link de cada notícia é sempre o da fonte, nunca o da IA (proteção contra notícia "envenenada").
- **Imagens seguras:** só HTTPS, só arquivo de imagem de verdade (conferido), no máximo 15 MB e 60 milhões de pixels (contra arquivo-bomba).
- **XML seguro:** os feeds de notícia são lidos com defusedxml (bloqueia XML malicioso).
- **Varredura diária (workflow "Segurança - varredura"):** procura token/senha vazados nos arquivos e em todo o histórico do git, workflows perigosos, pacotes com falha conhecida (pip-audit) e código perigoso (bandit). Se falhar, avisa o admin no Telegram.
- **Pacotes e ações travados:** versões fixas em requirements.txt e ações do GitHub fixadas por SHA (ninguém troca o código delas por baixo). Dependabot avisa quando sair correção.
- **Permissões mínimas:** cada workflow só tem a permissão que precisa; nenhum roda código de estranhos com os segredos (sem pull_request_target).
- **Segredos só no GitHub Secrets**, nunca no código. O GitHub já bloqueia push com token (secret scanning + push protection ligados).

## O que só o Marcos pode fazer (contas)
1. Verificação em 2 etapas (app autenticador, não SMS) em: Instagram, os 2 Gmails, GitHub, Meta, Mercado Livre, Amazon, Shopee, AliExpress.
2. Telegram: Configurações → Privacidade → Verificação em duas etapas (senha na nuvem).
3. Guardar os códigos de recuperação fora do celular (papel ou cofre de senhas).
4. Gerenciador de senhas com senha diferente em cada conta.
5. Nunca clicar em DM/e-mail de "violação de direitos autorais", "selo azul" ou "conta será desativada": é o golpe nº 1 contra perfis do Instagram. A Meta só avisa dentro do app (Configurações → Central de contas → E-mails da Meta).
6. Canal do Telegram: só você e o bot como admins; o bot sem permissão de adicionar admins.
7. GitHub → Settings → Code security: ligar Dependabot alerts e security updates.
8. Mandar seu ID pessoal do Telegram para `telegram.admin_chat` (recebe os alertas).
9. Se um token vazar: troque na hora (BotFather /revoke, Meta, Google AI Studio) e atualize o Secret.
