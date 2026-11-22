# Data Steward Mirror

<img src="icon.png" width="80" height="80" alt="Data Steward Mirror icon">

Espelho remoto direto de ficheiros, recebido do Data Steward por **rsync sobre SSH**.
Uma app HAOS dedicada ao HA2 que ficará em Lisboa, com configuração guiada por ingress.

**Experimental 0.1.0.** A receção começa desativada e a porta de dados não é publicada
por defeito. A instalação e a configuração de rede são manuais; publicar este
repositório não instala nem modifica nenhum HA.

## Arquitetura

```text
Data Steward / Alicante                  Data Steward Mirror / HA2
/media/immich       -- rsync/SSH/TCP -->   <disco>/immich
/media/filebrowser  -- rsync/SSH/TCP -->   <disco>/filebrowser
```

O HA2 está inicialmente em Alicante. Usa o IP LAN do HA2 para a primeira carga:
evita a Internet e o encaminhamento de retorno do router. Quando o mudares para
Lisboa, altera apenas endereço/porta no emissor e a rede no novo local. Mantém as
chaves privadas da app e o UUID do disco para preservar o emparelhamento.

Não há VPN, cloud intermédia, Restic, montagem remota ou API do Home Assistant no
caminho dos dados. Os ficheiros regulares ficam diretamente acessíveis no disco.
As alterações e eliminações enviadas pelo emissor refletem-se no espelho; não existe
histórico adicional. O L3 offline mantém a sua função de recuperação de versões.

## Configuração guiada

1. Adiciona `https://github.com/rpmlourenco/ha-backup-steward-mirror` em
   **Definições → Apps → Loja de apps → Repositórios**. Instala **Data Steward Mirror**.
   Inicia a app e abre a interface por ingress. Como alternativa, instala manualmente
   a pasta `mirror/` como app local.
2. Monta manualmente um disco ext4 dedicado no HA2. Escolhe o ponto de montagem
   diretamente em `/media`, por exemplo `/media/mirror`, e confirma o UUID.
   A lista de discos faz apenas deteção de leitura. Se a identidade não estiver
   visível à app, a receção bloqueia: não substituas a validação por um bypass.
3. No Data Steward original, abre **Configurar espelho**, seleciona as origens,
   deteta/confirma os respetivos UUID e guarda com L4 ainda desligado.
4. Carrega em **Preparar chaves públicas** e copia o emparelhamento para esta app.
   As chaves privadas ficam na app de origem, nunca no texto de emparelhamento.
5. Nesta app, importa as chaves, confirma a porta SSH pública e guarda. Usa
   **Preparar identidade do recetor** e copia a identidade pública para Alicante.
   Inclui a chave SSH do servidor e o UUID esperado do destino.
6. No separador **Rede** da app no HA2, publica a porta interna **2222/TCP**.
   Configura manualmente o router/firewall. A porta indicada na interface é a
   porta pública usada pelo emissor; pode ser diferente da porta interna.
7. Ativa a receção, guarda e reinicia manualmente **apenas esta app**. As alterações
   guardadas não substituem a política do processo SSH já em execução. Um aviso
   na interface distingue configuração guardada da configuração em uso.
8. Em Alicante, confirma endereço, porta, identidade SSH e UUID do destino.
   Guarda, prepara o modo de produção e usa **Testar ligação**: autentica e lê a
   identidade/espaço sem enviar ficheiros. Ativa L4 e sincroniza quando quiseres.

Depois da primeira gravação na interface, `/data/mirror/config.json` prevalece
sobre as opções de bootstrap do Supervisor. Mantém as definições pela interface.

## Rede a configurar manualmente

O acesso indicado pelo utilizador, `home2.rpmloureco.uk`, corresponde ao acesso ao
HA2 por reverse proxy no HA1. A ortografia do domínio não foi confirmada; outros
serviços existentes usam `rpmlourenco.uk`. Nenhum desses nomes é hardcoded.

Um proxy host HTTPS não transporta SSH. Usa um encaminhamento TCP dedicado até à
porta da app Mirror, ou IPv6 acessível com regra de firewall. Para o caminho mais
direto, encaminha no router diretamente para o HA2; um stream TCP no HA1 seria
uma alternativa manual com uma passagem adicional. Não se altera o proxy do HA.
Em Lisboa é necessário IPv4 público alcançável ou IPv6 utilizável. CGNAT sem IPv6
não permite este caminho de entrada direto.

## Segurança e armazenamento

- Chaves Ed25519 por origem; passwords, root login, terminal e forwarding bloqueados.
- Identidade SSH e UUID do destino fixados no emissor; não há aceitação automática
  de uma chave desconhecida ou alterada.
- Conta não privilegiada e diretório separado por origem; `rrsync -wo -munge`
  faz a validação upstream dos argumentos. Pull, comandos arbitrários e caminhos
  fora da raiz são recusados.
- Links simbólicos recebidos são neutralizados por `--munge-links`; o espelho
  destina-se a ficheiros e diretórios de dados, não a reproduzir links executáveis,
  dispositivos, proprietários, ACL ou ficheiros especiais de um sistema operativo.
- O UUID ext4, a montagem exata, o modo de escrita e o espaço livre são confirmados
  antes de cada sessão. Não há permissões para montar/desmontar/desligar discos.
- A raiz do disco deve pertencer a root, permitir travessia/leitura e impedir
  escrita de outros utilizadores. As subpastas novas são preparadas pela app;
  pastas preexistentes com outro proprietário não são adotadas nem alteradas.
- A app usa `/media` e o catálogo udev de leitura. Não pede acesso à configuração
  do HA, tokens, D-Bus do host, Docker socket, host PID ou modo privilegiado.
- Os backups da própria app incluem as suas definições e chave de servidor,
  não os dados de `/media`. Protege também os backups nativos da app.

Rsync valida as transferências pelo seu protocolo, mas uma árvore em alteração
não é uma captura transacional. O emissor deve preparar previamente os dumps de
BD e configuração de Immich/FileBrowser. Esta app não chama serviços nem pára apps.
Uma sincronização interrompida pode deixar uma árvore parcialmente atualizada;
o envio seguinte reconcilia-a. Os ficheiros são substituídos individualmente.

## Desenvolvimento e validação

```powershell
docker build -t ha-backup-steward-mirror:dev mirror
docker run --rm -v "${PWD}:/workspace:ro" -w /workspace -e PYTHONPATH=mirror ha-backup-steward-mirror:dev python -B -m unittest discover -s tests -v
```

`tests/e2e.py` executa SSH/rsync reais dentro de um único contentor efémero, com
ambos os repositórios montados apenas para leitura e sem publicar portas. Só a
identidade do filesystem é simulada; verifica autenticação, probe, dry-run, cópia,
atualização, eliminação, confinamento e rejeição de comandos/pull/chave de host
errada. Não mapeies discos, dispositivos ou configuração dos HA para este teste.

`tests/ui.py` usa Playwright/Chrome e endpoints simulados. Verifica importação de
chaves, exportação de identidade, gravação, aviso de reinício, falhas de ligação
e disposição em desktop/telemóvel. As capturas ficam em `test-artifacts/`, ignorado.

A aceitação no HAOS tem de confirmar propagação da montagem, visibilidade do UUID
como utilizador não privilegiado, permissões, porta publicada e restauro de uma
amostra. Um build ARM64 e testes de contentor não substituem essa aceitação.

MIT. OpenSSH e rsync/rrsync são dependências dos pacotes Debian e mantêm as suas
licenças upstream. O ícone e o estilo visual derivam do Data Steward original (MIT).
