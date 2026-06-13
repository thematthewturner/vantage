# Deploying vantage to a DigitalOcean droplet

This runs the **terminal** (Streamlit web app) and a **scheduler** that refreshes
the data once a day, both from one Docker image, sharing a persistent data volume.

```
web        Streamlit dashboard, served on port 80
scheduler  runs `vantage.pipeline.refresh` daily (and once on first boot)
vantage-data   named volume holding data/ (DuckDB store + raw Parquet)
```

## 1. Create the droplet

- A basic **Ubuntu 22.04+** droplet is plenty (1–2 GB RAM). The DuckDB store is small.
- Choose the **Docker** Marketplace image, or install Docker yourself:

  ```bash
  curl -fsSL https://get.docker.com | sh
  ```

## 2. Get the code and configure

```bash
git clone https://github.com/thematthewturner/vantage.git
cd vantage
cp deploy/.env.example deploy/.env
nano deploy/.env          # set FRED_API_KEY (and a password, if you want one)
```

Get a free FRED key at <https://fredaccount.stlouisfed.org/apikey>. Without it the
equity index still builds; indicators are simply skipped.

## 3. Launch

```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

On first boot the scheduler runs an initial refresh (a few minutes: it fetches
FRED series and yfinance prices, then builds the indices). Watch progress:

```bash
docker compose -f deploy/docker-compose.yml logs -f scheduler
```

Then open `http://<droplet-ip>/` — that's your terminal.

## 4. Firewall

Open HTTP and SSH only:

```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw enable
```

## Day-2 operations

```bash
# Update to the latest code
git pull && docker compose -f deploy/docker-compose.yml up -d --build

# Force a refresh right now (don't wait for the scheduled hour)
docker compose -f deploy/docker-compose.yml run --rm scheduler \
  python -m vantage.pipeline.refresh

# Tail logs / check status
docker compose -f deploy/docker-compose.yml logs -f
docker compose -f deploy/docker-compose.yml ps
```

The data lives in the `vantage-data` volume and survives rebuilds. Because the
whole store is rebuildable from the raw Parquet landing, a backup is just a copy
of that volume.

## HTTPS (optional)

To serve over TLS with your own domain, put a reverse proxy in front. The
simplest is [Caddy](https://caddyserver.com) (automatic Let's Encrypt):

1. Point an A record at the droplet IP.
2. Set `WEB_PORT=8501` in `.env` so Streamlit isn't on port 80.
3. Run Caddy with a one-line `Caddyfile`:

   ```
   your.domain.com {
       reverse_proxy localhost:8501
   }
   ```

## Notes

- DuckDB allows a single writer, so the terminal reads are made resilient to the
  brief lock during the nightly refresh (it retries, then serves cached data).
- Set `VANTAGE_DASHBOARD_PASSWORD` in `.env` to gate the dashboard behind a
  single password. For anything more than personal use, also put it behind a
  proxy with real auth and TLS.
