# SatoTag

**L’antitaccheggio dei satoshi — un’idea da verificare, non una promessa.**

Prototipo di ricerca offline che fa seguire un marchio di provenienza ai fondi
in un registro di transazioni **inventate**. Include un motore Python senza
dipendenze runtime, una demo interattiva e test automatici.

> **Stato: proof of concept, v0.2.0.** Non modifica Bitcoin, non congela fondi,
> non verifica furti reali e non rende obbligatorio uno sconto. Nessun wallet,
> chiave privata, servizio esterno o indirizzo reale è coinvolto.

## Nuovo registro firmato v0.2

La demo live include anche un registro con firme Ed25519 e quorum, contestazioni,
revoche e ricevute del controllo legate al pagamento. Il motore originale
`analyze` continua a usare stati dichiarati: il percorso firmato usa
`satotag.registry.replay`. Le chiavi della demo sono pubbliche e non hanno
alcuna autorità. Le firme non dimostrano che un furto sia realmente avvenuto.

Per il registro, i nuovi test e la rigenerazione della demo installa il supporto
opzionale: `python -m pip install -e ".[governance]"`.

[Specifica e limiti del registro firmato](docs/GOVERNANCE.md).

## Provalo subito

Apri **[docs/index.html](docs/index.html)** in un browser dopo aver scaricato il
repository. La demo è un singolo file HTML, funziona offline e si adatta al
telefono. GitHub mostra il sorgente HTML: per interagirci occorre aprire il file
scaricato in un browser o servirlo localmente.

Per chi ha Python 3.11 o successivo, dalla cartella del progetto:

```bash
python -m satotag analyze examples/split.json
python -m satotag analyze examples/mixed.json --haircut 60 --output report.json
python -m unittest discover -s tests -v
```

Per il solo comando `analyze` non occorre installare pacchetti. Il registro firmato, i test completi e la generazione della demo richiedono il supporto opzionale indicato sopra. Su alcuni sistemi il comando è `python3`.
Per vedere la demo attraverso un piccolo server locale:

```bash
python -m http.server 8000 --bind 127.0.0.1 --directory docs
```

Apri `http://127.0.0.1:8000` sullo stesso dispositivo. Un telefono diverso non
può accedere a quell’indirizzo: la demo resta locale.

## Cosa è stato costruito

| Componente | Comportamento effettivo |
|---|---|
| Registro di casi | Prove dichiarate, output iniziali, stato `pending`, `accepted`, `revoked` |
| Motore di propagazione | Il riferimento al caso resta sui discendenti finché il caso è attivo |
| Attribuzione proporzionale | Una quota marcata piccola non trasforma l’intero saldo in refurtiva |
| Contabilità esatta | Frazioni razionali; nessun arrotondamento che cancelli piccole quote |
| Controlli | Input mancanti, doppie spese, cicli, valori non validi e origini sovrapposte rifiutati |
| Simulatore economico | Uno sconto ipotetico modifica una valutazione, **mai il saldo** |
| Demo | Quattro scenari, selezione delle destinazioni, sconto regolabile ed esportazione JSON |
| Riproducibilità | Hash del dataset, output deterministico, test e workflow GitHub Actions |

## I quattro esperimenti

1. **Dividi e trasferisci:** il marchio sopravvive a più passaggi.
2. **Unisci due provenienze:** 1 BTC marcato più 4 BTC non marcati nel dataset
   produce un’esposizione modellata del 20%, non del 100%.
3. **Piccole somme:** 1.000 satoshi marcati non fanno diventare interamente
   sospetto un BTC unito ad essi. La presenza resta visibile, la quantità resta
   proporzionata.
4. **Correzione:** una revoca elimina l’effetto attivo al ricalcolo. Il caso
   rimane nel report per rendere visibile la decisione. Conservare i precedenti
   dataset in Git è una scelta del revisore, non un audit log garantito dal motore.

## Come funziona il marchio

Un caso accettato identifica uno o più **output interi** come origine marcata.
Ogni transazione distribuisce l’esposizione in proporzione ai valori degli
output e delle commissioni. Il riferimento al caso rimane anche con esposizione
molto piccola: non esiste una soglia che lo cancelli.

```text
E_output = E_input × valore_output / valore_totale_input
E_fee    = E_input × commissione / valore_totale_input
```

`E` è l’esposizione contabile attribuita, non una probabilità di colpa.
Le frazioni di satoshi sono solo stime di esposizione; gli importi delle
transazioni restano numeri interi di satoshi. Non assumiamo di identificare
ogni singolo satoshi originale: in un’unione non esiste un abbinamento univoco
imposto da Bitcoin tra ogni input e ogni output.

Lo sconto della demo è **60% della sola quota attribuita** per impostazione
iniziale. Esempio: un output da 1 BTC, con esposizione pari a 0,2 BTC, ha una
valutazione ipotetica equivalente a 0,88 BTC. Il suo saldo spendibile resta
1 BTC. Chi non adotta questa politica può ignorarla: il prezzo non è imposto
dal software, né questo modello ne prevede l’andamento.

## Le cose che questa versione non risolve

- **Autorità:** `accepted` è una dichiarazione dell’input. Nessuna prova viene
  scaricata, verificata o autenticata. Un hash non certifica la verità di un’accusa.
- **Perimetro:** non ci sono nodo Bitcoin, parsing di transazioni reali, verifiche
  crittografiche delle firme, consenso, blocchi, conferme o gestione delle reorg.
- **Confini:** commissioni, coinbase, scambi tra asset, intermediari custodial e
  percorsi non ricostruibili non sono seguiti oltre il dataset. Le commissioni
  sono registrate come uscita dal perimetro, non come fondi “ripuliti”.
- **Incertezza:** dati mancanti vengono rifiutati; una transazione origine è
  un punto di partenza dichiarato, non una certificazione di provenienza lecita.
  Il motore v0.1 non stima probabilità né risolve associazioni ambigue.
- **Tutela dei terzi:** esposizione e colpevolezza sono concetti distinti.
  L’algoritmo non prende decisioni legali o automatizza sequestri.
- **Permanenza reale:** la persistenza è una regola di questa simulazione.
  Rendere un marchio obbligatorio su Bitcoin richiederebbe un cambiamento di
  protocollo e consenso; vedere [la proposta di ricerca](docs/PROTOCOL_PROPOSAL.md).

La taint analysis e il controllo di provenienza esistono già. SatoTag non
rivendica di averli inventati. Questo repository rende esplorabili le regole,
le conseguenze della marcatura e i limiti di una penalità ipotetica.

## Sviluppo e verifica

```bash
python -m unittest discover -s tests -v
python tools/build_demo.py
python tools/build_demo.py --check
```

La demo contiene report generati dallo **stesso motore Python**, non una seconda
implementazione del tracciamento. Il browser ricalcola solo lo sconto con
aritmetica razionale BigInt. I valori a schermo sono arrotondati; il JSON esportato
mantiene le frazioni esatte. Gli scenari non caricano dati dalla rete.

Il workflow `Test SatoTag` verifica Python 3.11, 3.12 e 3.13 e controlla che la
demo sia allineata al motore. Il risultato di una CI remota va verificato nel
repository: la presenza del file workflow non implica che sia già passata.

## Mappa dei file

| Percorso | Contenuto |
|---|---|
| `satotag/engine.py` | Validazione, ordinamento del grafo, esposizioni, report |
| `satotag/__main__.py` | CLI con errori leggibili e limite di input |
| `examples/*.json` | Quattro dataset dichiaratamente fittizi |
| `tests/test_engine.py` | Test di regressione e 100 grafi generati per le invarianti |
| `tools/build_demo.py` | Generazione riproducibile della demo |
| `tools/demo_template.html` | Interfaccia offline |
| `docs/index.html` | Demo pronta da aprire |
| `docs/SCHEMA.md` | Formato dei dati e contratto del report |
| `docs/THREAT_MODEL.md` | Limiti, abusi possibili e mitigazioni |
| `docs/PROTOCOL_PROPOSAL.md` | Cosa mancherebbe per un marchio imposto dalla rete |

## Prossimi esperimenti, in ordine

1. Revisione indipendente delle regole di attribuzione e dei test.
2. Attestazioni firmate da più revisori, revoche e cronologia verificabile.
3. Importatore **in sola lettura** da Bitcoin Core regtest, con gestione delle reorg.
4. Studio di un protocollo sperimentale separato: nessuna pretesa di modificare mainnet.
5. Misurazione di falsi positivi e danni ai terzi prima di qualsiasi uso su fondi reali.

## Riferimenti

- [Bitcoin — transazioni e output](https://developer.bitcoin.org/devguide/transactions.html)
- [Bitcoin — formato delle transazioni](https://developer.bitcoin.org/reference/transactions.html)
- [Chainalysis — address screening](https://www.chainalysis.com/product/address-screening/)
- [Elliptic — wallet e transaction screening](https://www.elliptic.co/products/lens/)

Ideazione: ummagumma1974. Codice prototipale sviluppato con assistenza AI; non sottoposto
ad audit indipendente. Licenza [MIT](LICENSE).

## English summary

SatoTag is an offline, synthetic-UTXO research prototype for persistent,
evidence-linked exposure marks. It uses exact proportional accounting, separates
lineage from exposure size, supports case revocation, and includes an interactive
offline demo. It is **not** a Bitcoin consensus change, an authenticated theft
registry, a production AML service, or an enforceable price haircut.

