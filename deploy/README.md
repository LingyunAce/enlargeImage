# Deployment Guide / 部署指南

This directory contains production deployment artifacts for the EnlargeImage backend.
本目录包含 EnlargeImage 后端的生产部署文件。

The backend is a FastAPI app that loads SwinIR model weights and exposes a job-based
upscaling API. See [`../FOLLOWUPS.md`](../FOLLOWUPS.md) for the operational context.

后端是一个 FastAPI 应用，负责加载 SwinIR 模型权重并提供基于任务的超分 API。

---

## 1. Prerequisites / 前置条件

### Hardware
- CPU: 4+ cores recommended (SwinIR is CPU-bound unless you have a GPU build)
- RAM: 4 GB minimum; 8 GB+ recommended
- Disk: 5 GB for code + venv + models + storage

### Software
- **Python 3.11** (3.10/3.12 may work but 3.11 is tested)
- A virtualenv at `/opt/enlargeimage/backend/.venv`
- `git` for source checkout
- **One of:** `supervisor` (Debian/Ubuntu: `apt install supervisor`) **or** `systemd` (most modern Linux distros)

### Model Weights
Download the official SwinIR Real-World Image SR x4 weights and place them in
`/opt/enlargeimage/backend/models/`. Filenames must match the pattern
`SwinIR_REALSR_X{scale}.pth` so the scanner picks them up.

```bash
sudo mkdir -p /opt/enlargeimage/backend/models
cd /opt/enlargeimage/backend/models
# Example: X4 weights (download from the official SwinIR repo / Google Drive)
sudo curl -L -o SwinIR_REALSR_X4.pth https://example.com/SwinIR_REALSR_X4.pth
```

> Add `SwinIR_REALSR_X2.pth` and `SwinIR_REALSR_X8.pth` if you have them. The app
> automatically detects which scales are available and routes requests accordingly.

### Required Service User
A dedicated, unprivileged user is required. Both the supervisord and systemd
configs run as `enlargeimage`:

```bash
sudo useradd --system --shell /bin/false --home /opt/enlargeimage enlargeimage
```

---

## 2. Initial Deployment / 初次部署

```bash
# 1. Place source
sudo mkdir -p /opt/enlargeimage
sudo chown enlargeimage:enlargeimage /opt/enlargeimage
git clone <your-repo-url> /opt/enlargeimage
# (or: rsync -av /local/path/ /opt/enlargeimage/)

# 2. Create venv
cd /opt/enlargeimage/backend
sudo -u enlargeimage python3.11 -m venv .venv
sudo -u enlargeimage .venv/bin/pip install --upgrade pip
sudo -u enlargeimage .venv/bin/pip install -r requirements.txt

# 3. Create runtime directories
sudo mkdir -p /opt/enlargeimage/backend/storage
sudo mkdir -p /opt/enlargeimage/backend/models
sudo mkdir -p /var/log/enlargeimage
sudo chown -R enlargeimage:enlargeimage /opt/enlargeimage /var/log/enlargeimage

# 4. Drop model weights into the models/ dir (see Prerequisite #3)
```

---

## 3. supervisor Setup / supervisor 部署

Use this option on **Debian/Ubuntu** systems where supervisor is in the package
manager. systemd-based distros should use **Option 4** below.

```bash
# Install supervisor
sudo apt update
sudo apt install -y supervisor

# Enable and start the supervisor daemon
sudo systemctl enable --now supervisor
# (On older systems: sudo service supervisor start)

# Drop the config
sudo cp deploy/supervisord.conf /etc/supervisor/conf.d/enlargeimage.conf

# Install the log rotation config
sudo cp deploy/logrotate.conf /etc/logrotate.d/enlargeimage

# Reload supervisor and start the service
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status enlargeimage
# Expected: enlargeimage                       RUNNING   pid 1234, uptime 0:00:05
```

### Verify

```bash
curl -s http://localhost:8000/api/health
# Expected: {"ok": true}
```

---

## 4. systemd Setup / systemd 部署

Use this option on **RHEL/CentOS/Ubuntu 16.04+** and other systemd-based distros.

```bash
# 1. Copy the unit file
sudo cp deploy/enlargeimage.service /etc/systemd/system/enlargeimage.service
sudo chmod 644 /etc/systemd/system/enlargeimage.service

# 2. Optional: drop a custom env file
sudo mkdir -p /etc/enlargeimage
sudo cp deploy/enlargeimage.env.example /etc/enlargeimage/enlargeimage.env
sudo chown -R root:enlargeimage /etc/enlargeimage
sudo chmod 640 /etc/enlargeimage/enlargeimage.env
# Then edit the file to uncomment / set the variables you want to override.

# 3. Reload systemd, enable + start the service
sudo systemctl daemon-reload
sudo systemctl enable enlargeimage
sudo systemctl start enlargeimage
sudo systemctl status enlargeimage
# Expected: Active: active (running)
```

### Verify

```bash
curl -s http://localhost:8000/api/health
# Expected: {"ok": true}
```

---

## 5. Log Management / 日志管理

### supervisor
- Live: `tail -f /var/log/enlargeimage/enlargeimage.out.log`
- Errors: `tail -f /var/log/enlargeimage/enlargeimage.err.log`
- Rotation: `deploy/logrotate.conf` — daily, 14 days, compressed
- After rotation, supervisord reopens log files automatically.

### systemd
- Live: `journalctl -u enlargeimage -f`
- Last hour: `journalctl -u enlargeimage --since "1 hour ago"`
- Since boot: `journalctl -u enlargeimage -b`
- journald rotates by configuration in `/etc/systemd/journald.conf` (default: weekly, 4 weeks)

---

## 6. Common Operations / 常用操作

### supervisor

```bash
# Start / stop / restart
sudo supervisorctl start enlargeimage
sudo supervisorctl stop enlargeimage
sudo supervisorctl restart enlargeimage

# Reload after supervisord.conf change
sudo supervisorctl reread
sudo supervisorctl update

# Tail logs
sudo supervisorctl tail -f enlargeimage
```

### systemd

```bash
sudo systemctl start enlargeimage
sudo systemctl stop enlargeimage
sudo systemctl restart enlargeimage

# Reload unit file after editing
sudo systemctl daemon-reload
sudo systemctl restart enlargeimage

# Tail logs
sudo journalctl -u enlargeimage -f
```

### Update the Codebase

```bash
cd /opt/enlargeimage
sudo -u enlargeimage git pull

# Restart the service
sudo supervisorctl restart enlargeimage      # supervisor
sudo systemctl restart enlargeimage          # systemd
```

---

## 7. Health Check / 健康检查

```bash
curl -s http://localhost:8000/api/health
# {"ok": true}
```

For a deeper check, submit a tiny job and watch the status progress:

```bash
curl -s -F "file=@tiny.png" -F "scale=4" http://localhost:8000/api/jobs
# Returns: {"id": "...", "status": "queued", ...}
curl -s http://localhost:8000/api/jobs/<id>
# Eventually: {"status": "done", ...}
```

---

## 8. Security Notes / 安全提示

- **Dedicated service user**: both unit files run as `enlargeimage`. Never run as root.
  - Created with `useradd --system --shell /bin/false` — no login, no home dir perms.
- **Firewall**: expose **only** port 8000 (or a reverse-proxied 443). On a public host:
  ```bash
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw enable
  ```
  Then put nginx or Caddy in front to terminate TLS.
- **Reverse proxy recommended**: a TLS-terminating reverse proxy in front of
  `:8000` is strongly encouraged for any public deployment.
- **systemd hardening**: the `.service` file enables `ProtectSystem=strict`,
  `ProtectHome=true`, `PrivateTmp=true`, `NoNewPrivileges=true`, etc. — review
  `man systemd.exec` before loosening any of these.
- **File permissions**: ensure `/opt/enlargeimage/backend/storage` and the
  `data.db` are writable only by the service user.
  ```bash
  sudo chown -R enlargeimage:enlargeimage /opt/enlargeimage/backend/storage
  sudo chown enlargeimage:enlargeimage /opt/enlargeimage/backend/data.db
  sudo chmod 750 /opt/enlargeimage/backend/storage
  sudo chmod 640 /opt/enlargeimage/backend/data.db
  ```
- **Model weights**: anyone who can write to the `models/` directory can substitute
  the network. Restrict write access — `chown -R enlargeimage:enlargeimage`
  and `chmod 755` are the right starting point.

---

## 9. Troubleshooting / 故障排查

### `bind: address already in use` (port 8000)

```bash
# Find what's holding the port
sudo ss -ltnp 'sport = :8000'
# or
sudo lsof -iTCP:8000 -sTCP:LISTEN

# Kill the offending process, or change the port:
# supervisor: edit /etc/supervisor/conf.d/enlargeimage.conf (--port)
# systemd:   edit /etc/enlargeimage/enlargeimage.env (PORT=9000)
```

### "No model weights found in /opt/enlargeimage/backend/models"

- Confirm the file exists and matches the pattern `SwinIR_REALSR_X{2,4,8}.pth`:
  ```bash
  ls -la /opt/enlargeimage/backend/models
  # The scanner looks for files matching: SwinIR_REALSR_X*.pth
  ```
- The check is on the **filename suffix** — anything else is skipped with a warning.

### Permission denied on `storage/` or `data.db`

```bash
sudo chown -R enlargeimage:enlargeimage /opt/enlargeimage/backend
```

### "Address already in use" from uvicorn reload

Reload mode (`--reload`) requires the reloader subprocess to be able to spawn
new workers. In a hardened systemd unit, this may need `MemoryDenyWriteExecute=false`.
Don't use `--reload` in production.

### Out of memory during inference

SwinIR is large. For 2000x2000 input at x4, peak RSS can exceed 4 GB. Either:
- lower `max_input_pixels` in `app/config.py` / `.env`
- or raise the cgroup memory limit if you're under systemd:
  ```ini
  MemoryMax=8G
  ```

### Service won't start — check the journal / log

```bash
# supervisor
sudo supervisorctl tail enlargeimage
# or
sudo tail -50 /var/log/enlargeimage/enlargeimage.err.log

# systemd
sudo journalctl -u enlargeimage -n 100 --no-pager
```

### "ModuleNotFoundError: No module named 'app'"

The `WorkingDirectory` is wrong. Both configs set
`WorkingDirectory=/opt/enlargeimage/backend` and the venv has the `app/` package
installed in editable mode via `pip install -r requirements.txt` (or it lives
at `/opt/enlargeimage/backend/app/` and is importable because of the cwd).

---

## 10. File Reference / 文件清单

| File | Purpose |
| --- | --- |
| `supervisord.conf` | supervisor program definition |
| `logrotate.conf` | log rotation rules for supervisor-managed logs |
| `enlargeimage.service` | systemd unit file |
| `enlargeimage.env.example` | template for `/etc/enlargeimage/enlargeimage.env` |
| `README.md` | this document |
