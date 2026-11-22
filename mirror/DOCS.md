# Data Steward Mirror

Abre a interface da app para configurar o disco, importar as chaves públicas de
Alicante e exportar a identidade do recetor. A receção começa desativada.

1. Escolhe o disco ext4 e confirma o UUID.
2. Importa o emparelhamento público do Data Steward de origem.
3. Define a porta SSH pública e publica manualmente a porta interna 2222/TCP
   no separador Rede. Configura o router/firewall manualmente.
4. Guarda e reinicia apenas esta app para aplicar a política do recetor.
5. Exporta a identidade para Alicante e usa o teste de ligação do emissor.

O acesso HTTPS ao Home Assistant não transporta SSH. Não é necessário reiniciar
o HA nem expor o seu SSH administrativo. Nunca copies uma chave privada.

Os ficheiros eliminados em Alicante são eliminados no espelho durante a
sincronização. Não existe histórico de versões nesta app. Desativar L4 no emissor
conserva os ficheiros remotos; alterações de configuração nesta app exigem o
reinício manual indicado na interface.

Consulta o README do repositório para instalação, restrições e aceitação HAOS.
