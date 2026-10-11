# AntiX Cortana setup guide

This is the exact public-relay setup for your AntiX machine.

The goal is simple:
- Cortana is the public front door
- Harley is the real server authority
- the relay is strict and deny-by-default

## 1) Install Caddy on AntiX

On Debian/AntiX-style systems:

```bash
sudo apt update
sudo apt install -y curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

## 2) Replace the default Caddyfile

Create a config file at `/etc/caddy/Caddyfile` with the public-relay policy:

```caddy
play.example.com {
  encode gzip

  handle / {
    reverse_proxy harley.internal:8778
  }

  handle /classic {
    reverse_proxy harley.internal:8778
  }

  handle /manifest.webmanifest {
    reverse_proxy harley.internal:8778
  }

  handle /service-worker.js {
    reverse_proxy harley.internal:8778
  }

  handle /api/health {
    reverse_proxy harley.internal:8778
  }

  handle /api/auth/me {
    reverse_proxy harley.internal:8778
  }

  handle /api/auth/login {
    reverse_proxy harley.internal:8778
  }

  handle /api/auth/logout {
    reverse_proxy harley.internal:8778
  }

  @blocked {
    not path / /classic /manifest.webmanifest /service-worker.js /api/health /api/auth/me /api/auth/login /api/auth/logout
  }

  respond @blocked 403 {
    body "Cortana is a public relay; write or stateful requests must go to Harley."
    close
  }

  respond 403 {
    body "Cortana is read-only by policy."
    close
  }
}
```

## 3) Start Caddy

```bash
sudo caddy run --config /etc/caddy/Caddyfile
```

Or run as a service:

```bash
sudo systemctl enable --now caddy
sudo systemctl status caddy
```

## 4) DNS / TLS

Point your public domain to the AntiX host, and let Caddy handle TLS.

For example:
- `play.example.com` -> AntiX IP
- Caddy obtains TLS automatically

## 5) Firewall on AntiX

Allow only:
- 80/tcp
- 443/tcp

Keep Harley on a private network or LAN-only port.

## 6) AntiX is not the source of truth

This machine should never be doing real world authority.

It should only:
- serve the shell
- serve static public assets
- pass through the small approved public API list
- reject everything else

## 7) Keep the relay strict

The policy is simple:
- allow public bootstrap traffic
- block state-changing traffic by default
- let Harley be the single authority

That keeps the public-facing system reachable without making the relay powerful.
