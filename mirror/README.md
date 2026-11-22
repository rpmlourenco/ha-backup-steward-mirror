# Data Steward Mirror

Recebe um espelho direto de ficheiros do Data Steward por **rsync sobre SSH**.
Configuração guiada, autenticação por chaves Ed25519, origens isoladas e validação
do UUID e espaço livre do disco. Os ficheiros mantêm a estrutura original.

A receção começa desativada. Abre a interface para escolher o disco, importar as
chaves públicas de Alicante e preparar a identidade deste recetor. A instalação,
montagem do disco e configuração de rede são manuais.

Consulta o separador Documentação para os passos de configuração.
