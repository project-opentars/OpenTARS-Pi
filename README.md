<p align="center"><img src="logo.svg" width="96" alt="openTARS"></p>

<h1 align="center">openTARS Pi</h1>

<p align="center"><b>A local AI assistant for small boards. No cloud, no GPU, no account.</b><br>
Talk to your Raspberry Pi or Orange Pi in plain words: it runs commands, drives the pins and remembers what you tell it.</p>

```bash
curl -fsSL https://github.com/project-opentars/OpenTARS-Pi/releases/latest/download/install.sh | bash
```

One line, no sudo, about a minute. Everything lands in one folder and one command removes it.

## What it looks like

Real session on an Orange Pi Zero 2W (4x Cortex-A53, 1 GB of RAM):

```text
$ opentars-pi
openTARS Pi 1.0 · Gargantua Pi 270M · OrangePi Zero 2W · 796 MB free

you how much free memory is there?
gp  796 MB of memory free, out of 969 MB.

you list the files in /etc/ssl
  ⎿ ls -la /etc/ssl
    drwxr-xr-x   2 root root 16384 Nov  1 14:56 certs
    -rw-r--r--   1 root root 12509 Apr  7  2026 openssl.cnf

you remember that the relay is on pin PI13
gp  Noted: the relay is on pin PI13.

you turn the relay on
Change a pin?
  PI13 on
Allow [y/N] y
gp  PI13 is on.
```

## What it does

- **Your board, in plain words.** Memory, disk, temperature, address, files, folders, processes. In English and Portuguese.
- **The pins.** Read and switch GPIO by name (`PC5`, `GPIO17`), or teach it your own names: "the relay is on pin PC5". Works through the kernel, with nothing else to install.
- **Memory.** "Remember that the backup runs at 3." It stays on the board.
- **Answers with a source.** Questions about the world go to Wikipedia, or to your own SearXNG, and come back with the site they came from, so a small model does not have to guess. Without a connection it says so instead of making something up.
- **A service for the house.** Keep the model loaded and ask from other devices, with a token.
- **A small window** on boards with a desktop. On a board without one it stays in the terminal.

## Built for a small board

Most requests never reach the model: common commands, board status, memory and pins are answered by code, so they come back right away and with the exact path you typed. The model, **[Gargantua Pi](https://huggingface.co/OpenTARS/Gargantua-Pi)** (270M, 300 MB), takes the conversation and everything else.

Measured on the Orange Pi Zero 2W:

| | |
|---|---|
| Installed size | 316 MB, model included |
| Status, files, memory, pins | 0.6 s |
| First answer from the model, cold | 25 s |
| Next runs (the prompt is cached on disk) | about 11 s |

## Nothing changes without your yes

The model is small, so the rule is strict: **only commands that just read run on their own.** Anything that writes asks first and shows you the exact command. Commands that can destroy data ask you to type the whole word. Writing to a pin always asks. Requests that arrive over the network are approved on the board itself, never by the device that sent them.

## Local by default

The model, your memory and your commands stay on the board. The one thing that leaves is the text of a search: it goes to Wikipedia. For the whole web, point it at your own [SearXNG](https://docs.searxng.org/) with `opentars-pi search http://your-server:8888`. To keep everything on the board, use `opentars-pi search off`.

## Commands

| | |
|---|---|
| `opentars-pi` | Chat |
| `opentars-pi "how hot is the board?"` | One question |
| `opentars-pi --auto` | Run changes without asking (dangerous ones still ask) |
| `opentars-pi gpio list`, `read PC5`, `on PC5`, `off PC5`, `release PC5` | The pins by hand |
| `opentars-pi service on`, `off`, `status` | Keep it running in the background (off by default) |
| `opentars-pi --approvals` | Answer what is waiting from the network |
| `opentars-pi search on`, `off`, `URL` | Web search on, off, or through your SearXNG |
| `opentars-pi --window` | The small window (needs `python3-tk`) |
| `opentars-pi --doctor` | Check the installation |
| `opentars-pi --test` | Run the built-in test with the real model |
| `opentars-pi --update` | Install the latest release |
| `opentars-pi --uninstall` | Remove everything |

## Use it from other devices

The service listens only on the board until you say otherwise:

```bash
opentars-pi service on --network
opentars-pi --token
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
