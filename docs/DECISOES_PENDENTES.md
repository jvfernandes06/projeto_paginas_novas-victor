# Decisões pendentes

Tudo que foi adiado de propósito ou nunca respondido. Atualizado em 19/10/2026, ao fim da etapa 2.

A coluna **Trava** diz o que não pode ser feito antes da resposta. Pendência sem trava não
atrasa nada agora, mas vira problema antes de a ONG usar o sistema com dado real.

## Bloqueiam o uso com dado real

| # | Pendência | Situação | Trava |
|---|---|---|---|
| 1 | **Cópia do backup fora do servidor** | Decidido em 19/10: por enquanto não. O backup diário fica na mesma máquina | Se a máquina quebrar ou for roubada, perde-se tudo. Precisa de destino (Drive da ONG, outro servidor, disco guardado em outro lugar) |
| 2 | **Cifragem do arquivo e do backup** | Não decidido. Quem gera a chave e onde ela fica guardada | O `.db` tem dado sensível em texto claro. Obrigatório antes de dado real |
| 3 | **Hospedagem** | Não decidido. Sugestão: Fly.io com volume ou VPS pequena, em nome da ONG, **um processo só** | Duas réplicas escrevendo no mesmo arquivo SQLite corrompem o banco |
| 4 | **Recuperação de senha** | Hoje o Admin gera senha provisória pela tela Admin, mostrada uma única vez. Não há e-mail | Se a coordenação toda perder a senha ao mesmo tempo, só se resolve por script no servidor (`scripts/criar_admin.py`) |
| 5 | **Rodar o backup todo dia** | `scripts/backup.py` está pronto, mas o agendamento (Agendador de Tarefas ou cron) ainda não foi configurado | Backup que ninguém dispara não existe |

## Afetam o relatório ao financiador

| # | Pendência | Situação |
|---|---|---|
| 6 | **Relatório em PDF e snapshot `relatorio_emitido`** | Fora do escopo da etapa 2, por decisão sua. Quando entrar: o PDF congela os números enviados, para um valor já entregue a financiador nunca mudar depois de alguém corrigir um registro antigo |
| 7 | **PDF só para período fechado** | Decisão minha, não confirmada: bloquear emissão quando o período inclui o mês corrente. A coordenação pode precisar de um PDF parcial para uso interno |
| 8 | **Forma da supressão < 5** | Implementado assim: o número vira vazio com a etiqueta `<5` e a linha continua aparecendo; a tela do parceiro não cruza gênero com faixa etária. Alternativa seria omitir a linha inteira |
| 9 | **Logo e identidade** | `assets/logo.png` é um logo provisório que eu gerei. Basta substituir o arquivo pelo oficial da ONG |
| 10 | **Exportação CSV geral** | Hoje só a tela do parceiro exporta, com os números agregados que estão na tela. Uma exportação ampla das visões não identificadas (para a coordenação) não foi feita |

## Conteúdo que depende da ONG

| # | Pendência | Situação |
|---|---|---|
| 11 | **Responsável legal para 12–17** | Decisão minha, não confirmada: as três faixas de menor de idade exigem consentimento do responsável legal, inclusive 12–17 |
| 12 | **Bairros** | O seed traz só "Jardim Itatinga" e "Outro". A lista real precisa vir da coordenação, ou ser preenchida pelo Admin no uso |
| 13 | **Locais reais** | O seed traz sede, rua e boate genéricos, mais alguns nomes fictícios na demonstração. Nomes reais de boates e pontos de abordagem só a ONG pode informar — e é informação sensível, vale decidir antes se entra no sistema |
| 14 | **Faixas por perfil** | As combinações do seed (`perfil.faixas_permitidas`) são a minha leitura; a coordenação precisa conferir, porque o sistema vai recusar o que ficar fora |
| 15 | **Funções que contam como voluntariado** | No seed, só "Voluntário". Se estagiária ou professor também contam para o indicador de horas, o Admin marca na tela |
| 16 | **Gestante sem data de parto** | Decidido em 19/10: só a checkbox, sem DPP. Consequência: o relatório não pode afirmar acompanhamento pré e pós-parto, só quantas gestantes foram atendidas. E a marca não tem história — a tela de Pendências lista quem está marcada há mais de dez meses, para a Técnica revisar |

## Técnicas, para depois

| # | Pendência | Situação |
|---|---|---|
| 17 | **Migração para Supabase/Postgres** | Desenho pronto em `DESTINO_SUPABASE.md`. Volta a ter RLS no banco, e aí as três invariantes de código passam a ser políticas do banco. As senhas não migram |
| 18 | **Teste dos 3 minutos em campo** | O fluxo tem 6 etapas curtas e foi medido só por aqui. Precisa de celular real e de uma pessoa da equipe cronometrando |
| 19 | **Fuso horário** | Timestamps gravados em UTC. As datas de atividade (que é o que aparece nos gráficos) são data pura, sem fuso, então os indicadores estão certos; o que ainda mostra UTC é a hora na trilha de auditoria |
| 20 | **Verificar `docker compose up` nesta máquina** | O Docker Desktop estava parado quando a etapa 2 foi concluída, então o `docker compose up` não foi executado aqui. O app foi validado subindo o Streamlit direto, com os mesmos passos do entrypoint |
