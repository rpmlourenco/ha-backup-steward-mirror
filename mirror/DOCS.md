# Data Steward Mirror

Abre a interface da app para configurar o disco, importar as chaves públicas de
Alicante e exportar a identidade do recetor. A receção começa desativada.

1. Escolhe armazenamento interno/NVMe ou disco dedicado e confirma o UUID do volume.
   No modo interno, usa uma pasta como `/media/mirror`; é criada quando ativares
   e reiniciares a app, depois de validar a identidade do volume.
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

## Registos e atividade

O fuso horário dos registos é configurável na interface. Os logs incluem data, hora
e offset; a atividade por origem mostra comparação/receção, início, duração e eventos
recentes. Os contadores de bytes, ritmo e ETA estão no Steward emissor. O histórico
da interface é limitado e volátil; os logs da app ficam no Supervisor.
