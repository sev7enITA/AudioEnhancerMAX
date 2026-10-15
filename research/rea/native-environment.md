# Ambiente REA e Ghidra

Configurazione verificata il 15 ottobre 2026 su macOS arm64. REA resta uno strumento di ricerca separato dalle dipendenze di AudioEnhancer.

| Componente | Verifica |
| --- | --- |
| REA | `rea-agents@6.5.0`, invocazione npm con versione fissa |
| Ghidra | [release ufficiale 12.1.4](https://github.com/NationalSecurityAgency/ghidra/releases/tag/Ghidra_12.1.4_build) |
| Archivio ufficiale | 569.649.598 byte; SHA-256 `ddac49f903da9d5bac833e5cc79395098b9c33cfd3279be5f31bd00387d2d4db`, coincidente con quello pubblicato |
| Java | JDK 21.0.9 a 64 bit già presente |
| Compilazione | Gradle 9.4.1 già presente; `buildNatives`, 14 task, esito positivo |
| Decompilatore | Mach-O arm64 in `Ghidra/Features/Decompiler/build/os/mac_arm_64/decompile` |
| REA doctor | Provider Ghidra `configured: true`, `available: true`, otto controlli positivi |

Il tool è installato in `/Users/fabriziodegni/.rea/tools/ghidra_12.1.4_PUBLIC`. Il log di compilazione, il risultato completo di doctor, la provenienza e la ricevuta della configurazione sono in `/Users/fabriziodegni/.rea/tools/`. Non sono stati installati nuovi JDK né modificati i percorsi globali della shell. Il tentativo alternativo di fetch Homebrew è stato interrotto; non è stato installato un secondo Ghidra.

## Codex e CLI

La sezione `mcp_servers.rea.env` in `/Users/fabriziodegni/.codex/config.toml` contiene solo i percorsi Ghidra e Java richiesti dal provider. Prima della modifica è stato creato il backup `config.toml.rea-ghidra-20261015T040350Z.backup`; il confronto dei TOML parsificati conferma che tutte le impostazioni esterne a quella sezione sono rimaste identiche.

La registrazione MCP è persistente. Questa chat ha usato la CLI; una sessione già aperta può richiedere una riconnessione per caricare i nuovi tool. L'app Codex non è stata riavviata durante le altre attività in corso.

Per usare lo stesso provider da una shell, impostare l'ambiente nel solo comando:

```bash
GHIDRA_INSTALL_DIR='/Users/fabriziodegni/.rea/tools/ghidra_12.1.4_PUBLIC' \
JAVA_HOME='/opt/homebrew/Cellar/openjdk@21/21.0.9/libexec/openjdk.jdk/Contents/Home' \
python3 scripts/rea_research.py inspect \
  --target antinode-clear --kind decompile --provider ghidra \
  --procedure 0xb0ec10 --raw-architecture arm64 --entry-point 0xb0ec10 \
  --artifact research/rea/private/clear-1.1.6-2026-10-15/latency-arm64.bin \
  --version-label '1.1.6 selected latency function, incomplete external context' \
  --timeout 120
```

Questi percorsi descrivono questa macchina. Un'altra installazione deve usare i propri percorsi e superare `rea doctor`; un provider disponibile non prova automaticamente che l'analisi di ogni binario riesca o sia completa. L'esito dell'operazione reale è registrato nel [dossier Clear](clear-native-analysis.md), insieme ai suoi limiti.

## Verifiche del progetto

Gli undici test dell'integrazione Python sono passati, inclusa la conservazione dei warning di decompilazione come evidenza parziale. La verifica MCP con il nuovo ambiente è positiva: inizializzazione, identità del server, 207 tool, 6 prompt e richiesta `binary_session` senza target; non equivale a testare ogni tool. L'operazione reale sul frammento Clear è riuscita, con i limiti descritti nel dossier. Sono stati controllati JSON, collegamenti locali dei documenti e hash degli artefatti citati; i pacchetti dei concorrenti risultano esclusi da Git. Le letture di alcuni file preesistenti e `git diff --check` si sono bloccate e sono state terminate con timeout: non è dichiarata una validazione completa del repository. Nessun commit, push, deploy o benchmark audio è stato eseguito.
