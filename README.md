# Sato-tag
English

SatoTag started with a question I still can’t get my head around.

Someone steals, moves, splits, mixes. A trail remains. Then what? Who accepts that money? How do they spend it?

That’s where the idea came from: let’s try “stamping” the origin of the funds and see what happens as they move.

We’ve built a demo using made-up data. You can split funds, combine them with others, see how much of the total is flagged, and what changes when a report is revoked. You can also simulate a discount on that flagged portion.

For now, it’s a laboratory. It doesn’t freeze bitcoin or decide what it’s actually worth.

But the tricky part comes straight away: who applies the stamp? Based on what evidence? And what if they get it wrong?

I want to understand whether this idea can work without giving someone the power to decide which bitcoin has value and which doesn’t. Otherwise, we’re back to fiat money.

That’s what the code is for: putting the idea on the table and trying to break it.

Let’s see where it holds up.

⸻

Italiano

SatoTag nasce da una domanda che ancora non mi torna.

Uno ruba, sposta, divide, mescola. Rimane una traccia. E poi? Chi accetta quei soldi? Come li spendi?

Da lì l’idea: proviamo a “timbrare” la provenienza e vediamo cosa succede nei passaggi successivi.

Abbiamo preparato una demo con dati inventati. Puoi dividere i fondi, unirli ad altri, vedere quanto pesa la quota segnalata e cosa cambia quando una segnalazione viene revocata. Puoi anche simulare uno sconto su quella quota.

Per adesso è un laboratorio. Non blocca bitcoin e non decide quanto valgono davvero.

Ma il punto delicato arriva subito: chi mette il timbro? Con quali prove? E se sbaglia?

Perché voglio capire se questa idea può funzionare senza dare a qualcuno il potere di decidere quali bitcoin valgono e quali no. Se no è come carta Fiat.

Il codice serve a questo: mettere l’idea sul tavolo e provare a romperla.

Vediamo dove regge.

---

## Try it / Provalo

**[Open the live demo / Apri la demo interattiva](https://ummagumma1974.github.io/Sato-tag/)**

Works in your browser, including on a phone. No downloads or wallet connection required. All scenarios use fictional data.

Funziona nel browser, anche dal telefono. Nessun download o collegamento a wallet. Tutti gli scenari usano dati inventati.

- [Usage guide / Guida e istruzioni](GUIDE.md)
- [Downloadable offline demo / Demo offline scaricabile](docs/index.html)
- [Python source / Codice Python](satotag/engine.py)


## v0.2 — Signed registry / Registro firmato

The prototype now verifies Ed25519 attestations, a reviewer quorum, hash-linked
case history and signed payment-check receipts. Late signals trigger manual
review; an earlier receipt never removes a tag or grants automatic immunity.
Verifier-selected trust keys and an independently obtained latest checkpoint
are required. The public demo uses deliberately public test keys and fictional
evidence. Signatures do not prove theft or reviewer independence.

Il prototipo ora verifica firme Ed25519, quorum dei revisori, cronologia collegata
tramite hash e ricevute firmate del controllo. Le segnalazioni tardive richiedono
una revisione manuale: una vecchia ricevuta non cancella il tag e non garantisce
immunità. Servono chiavi scelte dal verificatore e un checkpoint aggiornato ottenuto
indipendentemente. Nella demo tutte le chiavi sono pubbliche e i casi inventati.

[Protocol, limitations and adversarial tests / Protocollo, limiti e test](docs/GOVERNANCE.md)

```bash
python -m pip install -e ".[governance]"
python -m unittest discover -s tests -v
python tools/build_demo.py --check
```

## v0.2.1 — Key authorization / Autorizzazione delle chiavi

Root-signed key lifetimes, irreversible revocation checks and replacement by a
pre-enrolled reserve are now available through `satotag.keyring` and the
`authorized-screen` / `authorized-verify` commands. They require an independently
pinned root public key and current manifest hash, in addition to the registry
checkpoint. Legacy APIs do not enforce key lifecycles.

La chiave principale autorizza le chiavi operative: ogni chiave ha una durata
e un ruolo. Una chiave revocata viene rifiutata anche se la ricevuta era stata
firmata prima. L'esempio mostra anche il passaggio a una chiave di riserva già
autorizzata. Le chiavi dell'esempio sono pubbliche; non usarle per fondi reali.

[Protocol, integration and reproducible example / Protocollo ed esempio](docs/KEY_AUTHORITY.md).
