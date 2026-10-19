# Guia da plataforma — Páginas Novas

Este guia é para quem usa o sistema no dia a dia. Não precisa saber nada de programação.

Sumário:

1. [Para que serve](#1-para-que-serve)
2. [Como ligar o sistema](#2-como-ligar-o-sistema)
3. [Entrar e criar a sua senha](#3-entrar-e-criar-a-sua-senha)
4. [Os quatro tipos de acesso](#4-os-quatro-tipos-de-acesso)
5. [Registrar uma atividade](#5-registrar-uma-atividade)
6. [Cadastrar uma pessoa](#6-cadastrar-uma-pessoa)
7. [Encaminhamentos](#7-encaminhamentos)
8. [Pendências](#8-pendências)
9. [Os dashboards](#9-os-dashboards)
10. [Tarefas do administrador](#10-tarefas-do-administrador)
11. [Backup](#11-backup)
12. [Se algo parar de funcionar](#12-se-algo-parar-de-funcionar)
13. [Cuidados com os dados das pessoas](#13-cuidados-com-os-dados-das-pessoas)

---

## 1. Para que serve

Para registrar, pelo celular, o que a ONG faz em campo — atividades, pessoas atendidas,
abordagens de rua, itens entregues, encaminhamentos — e transformar isso, sem trabalho extra,
nos números que financiadores e parceiros pedem.

Os dashboards se atualizam sozinhos: alguém registra uma atividade na rua e, em até um minuto,
o número aparece na tela de quem está na sede. Ninguém precisa "fechar o mês" nem mexer em
planilha.

## 2. Como ligar o sistema

No servidor da ONG, um comando só:

```
docker compose up
```

Depois disso o sistema fica no ar em `http://localhost:8501` (ou no endereço que a pessoa que
instalou tiver informado). Para desligar, `Ctrl+C` na mesma janela.

O sistema sobe já com **dados de demonstração** (300 pessoas e 18 meses de atividades
inventadas), para dar para treinar a equipe sem usar informação real. Quando a ONG for começar
de verdade, peça para quem instalou:

1. rodar `python scripts/limpar_demo.py --sim`, que apaga tudo que é inventado;
2. mudar `PN_SEED_DEMO` para `0` no arquivo `docker-compose.yml`, para a demonstração não
   voltar;
3. criar o primeiro acesso de administração.

## 3. Entrar e criar a sua senha

1. Abra o endereço do sistema no celular ou no computador.
2. Digite o seu e-mail e a senha que a coordenação entregou.
3. Na primeira vez, o sistema pede para você criar uma senha sua, com pelo menos 8 letras ou
   números. A senha que a coordenação deu não funciona mais depois disso.

O botão **Sair** fica sempre no menu da esquerda. Se o celular ficar 30 minutos parado, o
sistema desconecta sozinho — é proteção, caso o aparelho fique na mão de outra pessoa.

Esqueceu a senha? Não existe recuperação por e-mail. Peça para a coordenação gerar uma senha
nova para você (item 10).

## 4. Os quatro tipos de acesso

| Acesso | Quem usa | O que vê |
|---|---|---|
| **Campo** | estagiárias, voluntários, professores | registra atividade e cadastra pessoa. **Nunca** vê nome, telefone nem encaminhamento: só o código, como PN-00012 |
| **Técnico** | assistente social | tudo do Campo, mais nome e telefone, encaminhamentos, pendências e todos os dashboards |
| **Administrador** | coordenação | tudo, mais criação de usuários, edição das listas e a trilha de quem acessou o quê |
| **Parceiro** | financiador | só o relatório de impacto, com números agregados |

Quem tem acesso de Campo não consegue abrir as telas dos outros nem digitando o endereço: o
sistema bloqueia.

## 5. Registrar uma atividade

Pelo celular, em menos de três minutos. São 6 telas curtas, e o sistema já vem preenchido com o
programa e o local da última vez:

1. **Programa** — qual projeto.
2. **Local** — sede, rua, boate ou outro.
3. **Data e horário** — a data de hoje já vem pronta.
4. **Equipe** — quantas pessoas de cada função estavam lá.
5. **Quem foi atendido** — duas opções:
   - **por código**, digitando o PN de cada pessoa; ou
   - **contagem anônima**, para abordagem de rua e boate, onde ninguém é identificado.
   Nesta tela também entram os itens entregues (preservativos, refeições, kits...).
6. **Confirmar** — você revê tudo e salva.

O sistema avisa quando algo não faz sentido: horário de término antes do início, data no futuro,
ou uma atividade igual já registrada por outra pessoa no mesmo dia, local e horário.

Se você salvar uma atividade sem participantes e sem contagem, ela aparece na tela de Pendências
até alguém completar.

## 6. Cadastrar uma pessoa

Preencha faixa etária, gênero, bairro, perfis e, se for o caso, marque **Gestante**.

O **consentimento é obrigatório**: sem a data em que a pessoa (ou o responsável, se for menor de
18) autorizou, o sistema não salva. Isso é exigência da Lei Geral de Proteção de Dados.

Ao salvar, aparece o **código da pessoa** em laranja, grande, do tipo `PN-00042`. **Anote esse
código**: é por ele que você encontra a pessoa nas próximas atividades. O nome nunca é usado
para buscar por quem tem acesso de Campo.

## 7. Encaminhamentos

Só Técnico e Administrador. Serve para acompanhar quem foi mandado para CRAS, UBS, CAPS,
Conselho Tutelar e outros serviços.

- **Criar**: código da pessoa, para onde foi e uma observação, se quiser.
- **Acompanhar**: a lista tem filtro por situação, e um toque muda a situação (enviado → em
  andamento → concluído, ou "sem retorno" quando o serviço não responde).

## 8. Pendências

A tela de Pendências é a lista do que ficou pela metade:

- atividade sem nenhuma pessoa registrada;
- atividade sem equipe informada;
- encaminhamento sem atualização há mais de 60 dias;
- pessoa sem consentimento válido;
- pessoa marcada como gestante há mais de dez meses, que talvez já tenha tido o bebê.

A ideia é simples: em vez de alguém arrumar planilha no fim do ano, o sistema aponta hoje o que
falta. Cada item tem um botão que leva à tela de correção.

## 9. Os dashboards

São sete telas. Em todas, uma linha no alto escolhe **o período** (este mês, mês passado,
últimos 3 meses, este ano ou datas específicas) e **o programa**.

| Tela | Responde a pergunta |
|---|---|
| Visão geral | quantas pessoas, quantas atividades, está crescendo ou caindo? |
| Programas | qual projeto atende mais gente, e onde as pessoas voltam mais? |
| Público atendido | que idade, que gênero, que perfil tem quem a ONG atende? |
| Território e rua | onde a equipe encontra mais pessoas, e o que foi entregue? |
| Encaminhamentos | que serviços recebem nossos encaminhamentos, e quais respondem? |
| Equipe e voluntariado | quanto trabalho voluntário sustenta a ONG? |
| Relatório para parceiros | os números que podem ser enviados para fora |

Duas coisas para saber ler:

- No alto aparece **"Atualizado às 14:32:05"** e quantos registros entraram na conta. A tela se
  atualiza sozinha a cada minuto.
- Quando o período ainda está em andamento, aparece o selo **parcial**: os números ainda vão
  crescer até o fim do mês.

Embaixo de cada gráfico tem uma frase explicando o que ele mostra. Se a frase e o gráfico
discordarem, confie na frase e avise a coordenação.

Na tela do parceiro, onde aparece **"<5"** havia menos de cinco pessoas no grupo. O número
exato é escondido de propósito: num território pequeno, "1 gestante atendida" pode identificar
a pessoa. O botão **Baixar CSV** salva exatamente os números da tela, já protegidos.

## 10. Tarefas do administrador

Tudo na tela **Admin**.

**Criar um acesso**: aba Usuários → Criar usuário → e-mail, nome e tipo de acesso. O sistema
mostra uma **senha provisória uma única vez**. Anote na hora e entregue em mãos; ela não
aparece de novo. Se perder, use **Nova senha** para gerar outra.

**Tirar o acesso de alguém**: botão **Desativar** na linha da pessoa. Nada do que ela registrou
é perdido. Para devolver o acesso, **Reativar**.

**Mudar o tipo de acesso**: troque na caixinha ao lado do nome. Você não consegue tirar o seu
próprio acesso de administrador, para o sistema não ficar sem ninguém.

**Adicionar um programa, um local ou um item**: aba Listas do sistema → escolha a lista →
escreva o nome → Adicionar. Para parar de usar algum, **Desativar**: ele sai dos formulários,
mas continua valendo em tudo que já foi registrado — os relatórios antigos não mudam.

As listas que você mantém são: programas, locais, tipos de atividade, destinos de
encaminhamento, bairros, gêneros, tipos de item, perfis e funções da equipe. Em funções da
equipe, a marca **conta como voluntariado** é o que faz a função entrar no indicador de horas
de voluntariado.

**Ver quem acessou dado pessoal**: aba Auditoria. Toda vez que alguém abre o nome, o telefone
ou um encaminhamento, fica registrado quem foi e quando. Essa lista não pode ser apagada.

## 11. Backup

Todo o sistema cabe num arquivo. Para copiá-lo com segurança, mesmo com o sistema no ar:

```
python scripts/backup.py
```

O arquivo vai para a pasta `backups`, com a data no nome, e o sistema guarda os últimos 30 dias.
Isso deve rodar **todo dia, automaticamente** — quem instalou configura isso uma vez.

Para voltar o sistema a um dia anterior:

```
python scripts/backup.py --restaurar backups/paginas_novas_2026-10-18.db
```

O estado atual é guardado antes de restaurar, então dá para voltar atrás.

**Atenção, e isto é importante:** hoje o backup fica na mesma máquina do sistema. Se essa
máquina quebrar ou for roubada, perde-se tudo. Antes de a ONG começar a usar com dado real,
decida para onde vai a cópia de fora (Drive da ONG, outro servidor, um disco guardado em outro
lugar) e peça para quem instalou configurar.

## 12. Se algo parar de funcionar

1. **Atualize a página.** O Streamlit às vezes perde a conexão; a informação não se perde.
2. **A tela diz "Faça login para continuar"?** A sessão expirou por inatividade. Entre de novo.
3. **Diz "Seu perfil de acesso não permite"?** Aquela tela não é do seu tipo de acesso. Se
   precisar dela, fale com a coordenação.
4. **O site não abre para ninguém?** Vá ao servidor e rode `docker compose up` de novo. Se ele
   já estava rodando, `docker compose restart`.
5. **Mensagem estranha, em inglês, com muitas linhas?** Tire um print, anote o que estava
   fazendo e envie para quem cuida do sistema. Não repita a operação várias vezes.
6. **Perdeu informação ou algo apagou errado?** Pare o sistema e chame ajuda **antes** de mexer
   mais. O backup do dia anterior está lá, e restaurar é melhor do que improvisar.

Nada que você faça pelas telas apaga informação de verdade: desativar esconde, mas guarda.

## 13. Cuidados com os dados das pessoas

As informações aqui são sensíveis: saúde, gestação, identidade de gênero, menores de idade e
contexto de exploração sexual. Um vazamento pode expor alguém a violência real.

O sistema já ajuda: nome e telefone ficam separados do resto, quem tem acesso de Campo nunca os
vê, todo acesso a dado pessoal fica registrado, e a tela do parceiro esconde grupos pequenos.

O que depende das pessoas:

- não compartilhe a sua senha, nem deixe a sessão aberta num aparelho de outra pessoa;
- não anote nome e telefone em caderno, grupo de WhatsApp ou planilha paralela: use o sistema;
- ao conversar sobre uma pessoa atendida, use o código (PN-00042), não o nome;
- se alguém pedir para retirar o consentimento, a Técnica faz isso no sistema: o nome e o
  telefone são apagados e o histórico continua valendo só como número.
