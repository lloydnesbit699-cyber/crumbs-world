# One-click launchers

The scripts are portable relative to this folder; the project can live
anywhere. The Crumbs server launcher binds through the app's loopback default
and does not expose the server to the LAN or internet.

## Windows 10/11

Double-click `crumbs-boot.bat` to start or verify Crumbs World. Use
`crumbs-boot.bat --stop` to request a graceful save and shutdown.
Double-click `tailscale-autobot.bat` for the safe default (install and connect).
For optional exposure, run from PowerShell:

```powershell
.\tailscale-autobot.ps1 -SSH
.\tailscale-autobot.ps1 -Funnel 8778
```

Each requested exposure prints a warning and requires typing `YES`.

## macOS

Double-click the `.command` file for the task. If macOS blocks it, open
Terminal, run `chmod +x` on the `.command` and `.sh` files once, then
Control-click the `.command` file and choose Open.

`tailscale-autobot.sh` uses an existing Tailscale CLI or installs the
open-source CLI service with Homebrew. Without Homebrew, install the official
Tailscale macOS app and its CLI integration, then rerun. Tailscale SSH requires
the open-source macOS client variant.

## Linux desktops

Run `./crumbs-boot.sh` or `./tailscale-autobot.sh` from a terminal. File
managers may need "Allow Launching" enabled for the bundled `.desktop` files;
they start a terminal so the status and login prompts remain visible. Tailscale
SSH and Funnel are not enabled by the desktop launcher.

The Linux Tailscale installer downloads only from Tailscale's HTTPS endpoint
and uses `sudo` to install the distribution package. Review your distribution's
package manager prompt before approving it.

## Tailscale exposure controls

The default Tailscale setup explicitly sets `--ssh=false`; it does not create a
Funnel. Existing Funnel configuration is not removed automatically, because
that could disrupt a service configured outside these scripts. The script
prints its current Funnel status when possible.

- `--ssh` / `-SSH`: asks separately before enabling tailnet SSH access.
- `--funnel PORT` / `-Funnel PORT`: asks separately before publishing a local
  HTTP service to the public internet. It requires an HTTP response from that
  loopback port before enabling Funnel.
- `--auth-key-file PATH` / `-AuthKeyFile PATH`: optionally use a private auth
  key file. The scripts validate restrictive file permissions and pass a file
  reference to Tailscale, not the key value on the command line.

Each confirmation must be typed as `YES`; non-interactive runs cannot enable
either exposure. Declining one does not cancel the safe install/connect steps.
