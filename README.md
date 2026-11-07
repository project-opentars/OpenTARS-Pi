<p align="center"><img src="logo.svg" width="96" alt="openTARS"></p>

<h1 align="center">openTARS Pi</h1>

<p align="center"><b>A local AI assistant for small boards. No cloud, no GPU, no account.</b><br>
Talk to your Raspberry Pi or Orange Pi in plain words: it runs commands, drives the pins and remembers what you tell it.</p>

```bash
curl -fsSL https://github.com/project-opentars/OpenTARS-Pi/releases/latest/download/install.sh | bash
```

One line, no sudo, about a minute. Then just type `opentars`. Everything lands in one folder and one command removes it.

## What it looks like

Real session on an Orange Pi Zero 2W (4x Cortex-A53, 1 GB of RAM), openTARS Pi 1.1:

```text
$ opentars
openTARS Pi 1.1 · Gargantua Pi · OrangePi Zero 2W · 817 MB free
you is the sd card full?
Gargantua  9.5 GB used on the disk, 182.2 GB free, out of 191.7 GB. Plenty of room.
you how many lines does oled_status.py have?
  ⎿ wc -l ~/oled_status.py
    157 /home/enzo/oled_status.py
Gargantua  ~/oled_status.py has 157 lines.
you make a folder demo-backup and copy oled_teste.py into it
Run this command?
  mkdir -p ~/demo-backup
Allow [y/N] y
Run this command?
  cp -r ~/oled_teste.py ~/demo-backup/
Allow [y/N] y
Gargantua  Done.
you what is the biggest file in my home?
  ⎿ ls -lhS ~ | grep -v '^[dt]' | head -n 1
    -rw-rw-r-- 1 enzo enzo 103K Nov  1 15:03 pihole-basic-install.sh
Gargantua  The biggest file in ~ is pihole-basic-install.sh (103K).
you who painted guernica?
  ⎿ who painted guernica
Gargantua  From en.wikipedia.org: Guernica is a large 1937 oil painting by Spanish artist Pablo Picasso.
Also: en.wikipedia.org (Guernica)
Also: en.wikipedia.org (Pablo Picasso)
```

## What it does

- **Your board, in plain words.** Memory, disk, temperature, address, files, folders, processes, in English and Portuguese. It reads the numbers for you: "is the SD card full?" gets an answer, not just a table.
- **It finds what you mean.** "Open the report" opens `Documents/relatorio-2026.txt`. Wrong case, missing extension, a typo, a folder called by its everyday name: the path is fixed before anything runs, and it tells you which file it used. Deleting never guesses: it asks.
- **Tasks with several steps.** "Create a folder backup and copy notas.txt into it." "Find WARN in the log and save those lines to avisos.txt." Each step runs in order, and it stops at the first one that fails or that you decline.
- **Answers in words.** "ERROR appears 5 times in ~/logs/app.log." "The biggest file in Downloads is filme.mp4 (2.9M)." "Yes: the disk has 416 GB free, so 2 GB fits."
- **The pins.** Read and switch GPIO by name (`PC5`, `GPIO17`), or teach it your own names: "the relay is on pin PC5". Works through the kernel, with nothing else to install.
- **Memory.** "Remember that the backup runs at 3." It stays on the board.
- **Answers with a source.** Questions about the world go to Wikipedia, or to your own SearXNG. It looks for the sentence that holds the kind of answer you asked for (a name, a year, a height, a place) and gives you the site it came from, so a small model does not have to guess. Without a connection it says so instead of making something up.
- **Pick the brain.** Gargantua Pi (270M) runs on any board. `opentars brain lite` switches to Gargantua Lite (0.8B) on boards with more memory. `opentars brain http://your-pc:11434` uses the Gargantua on your computer, over your own network.
- **Updates in place.** `opentars update` downloads only what changed (app, engine or model), checks each file by SHA-256 and keeps the previous version: `opentars update undo` goes back.
- **A service for the house.** Keep the model loaded and ask from other devices, with a token.
- **A small window** on boards with a desktop. On a board without one it stays in the terminal.

## Built for a small board

Most requests never reach the model: files, folders, several-step tasks, board status, memory, pins and questions about the world are answered by code and search, so they come back right away, with the real path or the source they came from. The model, **[Gargantua Pi](https://huggingface.co/OpenTARS/Gargantua-Pi)** (270M, 300 MB), takes the conversation and everything else. It is honest about its size: ask it to write a program and it will point you to the full openTARS instead of handing you broken code.

Measured on the Orange Pi Zero 2W (the capability test runs the same app and model in a clean container; the tasks are in `tools/prova`):

| | |
|---|---|
| Installed size | 316 MB, model included |
| Status, files, memory, pins | 0.6 s |
| First answer from the model, cold | 25 s |
| Next runs (the prompt is cached on disk) | about 11 s |
| Conversation, once the model is loaded | 2 to 4 s |
| Capability test: 40 everyday tasks it had never seen | 30 of 40 (1.0: 19 of 40) |

## Nothing changes without your yes

The model is small, so the rule is strict: **only commands that just read run on their own.** Anything that writes asks first and shows you the exact command. Commands that can destroy data ask you to type the whole word. Writing to a pin always asks. Requests that arrive over the network are approved on the board itself, never by the device that sent them.

## Local by default

The model, your memory and your commands stay on the board. The text of a search leaves: it goes to Wikipedia. For the whole web, point it at your own [SearXNG](https://docs.searxng.org/) with `opentars search http://your-server:8888`. Once a day it also downloads a small file from GitHub that lists the latest version (`opentars update auto off` stops that). If you choose a Gargantua on your network with `opentars brain`, what the rules cannot answer goes to that address and nowhere else. To keep everything on the board, use `opentars search off` and `opentars update auto off`.

## Commands

| | |
|---|---|
| `opentars` | Chat |
| `opentars "how hot is the board?"` | One question |
| `opentars --auto` | Run changes without asking (dangerous ones still ask) |
| `opentars gpio list`, `read PC5`, `on PC5`, `off PC5`, `release PC5` | The pins by hand |
| `opentars service on`, `off`, `status` | Keep it running in the background (off by default) |
| `opentars --approvals` | Answer what is waiting from the network |
| `opentars search on`, `off`, `URL` | Web search on, off, or through your SearXNG |
| `opentars --window` | The small window (needs `python3-tk`) |
| `opentars brain`, `brain lite`, `brain http://your-pc:11434`, `brain pi` | Who thinks: the model on the board, a bigger one, or one on your network |
| `opentars --doctor` | Check the installation |
| `opentars --test` | Run the built-in test with the real model |
| `opentars update` | Get what is new: app, engine or model, only the parts that changed, each checked by SHA-256 |
| `opentars update check`, `undo`, `auto off` | See what is new, go back to the previous version, stop the daily check |
| `opentars --uninstall` | Remove everything |

## Use it from other devices

The service listens only on the board until you say otherwise:

```bash
opentars service on --network
opentars --token
```

```bash
curl -X POST http://BOARD:18100/v1/conversa \
  -H "Authorization: Bearer YOUR_TOKEN" -d '{"mensagem": "how hot is the board?"}'
```

The traffic is plain HTTP: keep it on a network you trust, such as your home network or Tailscale.

## Requirements

- A 64-bit Linux board with 1 GB of RAM and 600 MB free on disk
- Python 3.9 or newer, and glibc 2.35 or newer (Debian 12, Ubuntu 22.04, Raspberry Pi OS Bookworm, Armbian, or newer)
- For the pins: your user in the `gpio` group

Tested on the Orange Pi Zero 2W with Armbian. Other 64-bit boards should work the same way; if yours gives you trouble, [open an issue](https://github.com/project-opentars/OpenTARS-Pi/issues).

## Part of openTARS

[openTARS](https://project-opentars.github.io/OpenTARS/) is the full assistant for Linux, Windows and macOS, with vision, voice and photo tools. openTARS Pi is its small sibling, made from scratch for boards.

## License

The app is MIT. The engine is [llama.cpp](https://github.com/ggml-org/llama.cpp) (MIT). Gargantua Pi is built on FunctionGemma and is provided under and subject to the [Gemma Terms of Use](https://ai.google.dev/gemma/terms).
