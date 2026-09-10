# RCJ Ubuntu Migration Runbook

This runbook is for moving the current RCJ setup from ZeaburOS/K3s to a plain Ubuntu server while keeping SSH access, GitHub cloning, and the `ops-bot` SSH mount working as before.

## Assumptions

- New server OS: Ubuntu 24.04 LTS.
- Login user during setup: `root`.
- RCJ root directory: `/root/rcj`.
- Main SSH key on the server: `/root/.ssh/id_ed25519`.
- `ops-bot` mounts a dedicated SSH directory from:

```text
/root/rcj/secrets/ops-bot-ssh
```

into the container at:

```text
/home/opsbot/.ssh
```

- SSH alias `T1_newuser1` is used to connect to:

```text
ec2-13-230-63-118.ap-northeast-1.compute.amazonaws.com
```

- The same server-side SSH key can also be used for `git clone` over SSH if its public key is authorized in GitHub.

---

## 1. Copy the SSH private key from the Mac to the new Ubuntu server

### 1.1 Confirm the key on the Mac

On the Mac:

```bash
ls -l ~/.ssh/id_ed25519
```

Optional: check its fingerprint without displaying the private key:

```bash
ssh-keygen -y -f ~/.ssh/id_ed25519 | ssh-keygen -lf -
```

### 1.2 Copy the key to the new Ubuntu server

Replace `<NEW_SERVER_IP>` with the new Ubuntu server IP.

From the Mac:

```bash
scp ~/.ssh/id_ed25519 root@<NEW_SERVER_IP>:/root/id_ed25519.tmp
```

If the server initially uses password login, enter the temporary/root password when prompted.

### 1.3 Move the key into `/root/.ssh`

SSH into the new server:

```bash
ssh root@<NEW_SERVER_IP>
```

Then run:

```bash
mkdir -p /root/.ssh
chmod 700 /root/.ssh
mv /root/id_ed25519.tmp /root/.ssh/id_ed25519
chmod 600 /root/.ssh/id_ed25519
chown root:root /root/.ssh/id_ed25519
```

Verify:

```bash
ls -la /root/.ssh
```

Expected key location:

```text
/root/.ssh/id_ed25519
```

### 1.4 Verify the copied key

On the Ubuntu server:

```bash
ssh-keygen -y -f /root/.ssh/id_ed25519 | ssh-keygen -lf -
```

Compare the fingerprint with the fingerprint from the Mac. They should be identical.

> Do not use `cat /root/.ssh/id_ed25519`. Avoid printing private keys into terminal history, logs, screenshots, or chat.

---

## 2. Recreate `/root/.ssh/config`

Create the config:

```bash
nano /root/.ssh/config
```

Add:

```text
Host T1_newuser1
    HostName ec2-13-230-63-118.ap-northeast-1.compute.amazonaws.com
    User newuser1
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    LocalForward 8086 127.0.0.1:8086
```

Then:

```bash
chmod 600 /root/.ssh/config
chown root:root /root/.ssh/config
```

Test:

```bash
ssh -T T1_newuser1
```

Or connect normally:

```bash
ssh T1_newuser1
```

On first connection, SSH may ask whether to trust the host key. Confirm only after verifying that the hostname is correct.

---

## 3. Prepare GitHub SSH access

Derive the public key from the copied private key:

```bash
ssh-keygen -y -f /root/.ssh/id_ed25519
```

Make sure this public key is already added to the GitHub account or repository that owns the RCJ repositories.

Test GitHub SSH authentication:

```bash
ssh -T git@github.com
```

Then create the RCJ directory:

```bash
mkdir -p /root/rcj
cd /root/rcj
```

Clone repositories as needed, for example:

```bash
git clone git@github.com:phucnguyen-ops-rcj/ops-bot.git
```

Clone the reports repository in the same way if needed.

---

## 4. Create the `rcj/secrets/ops-bot-ssh` directory

Create the directory structure:

```bash
mkdir -p /root/rcj/secrets/ops-bot-ssh
chmod 700 /root/rcj/secrets
chmod 700 /root/rcj/secrets/ops-bot-ssh
```

Copy the SSH files used by `ops-bot`:

```bash
cp /root/.ssh/id_ed25519 /root/rcj/secrets/ops-bot-ssh/id_ed25519
cp /root/.ssh/config /root/rcj/secrets/ops-bot-ssh/config
```

If `/root/.ssh/known_hosts` already exists, copy it too:

```bash
cp /root/.ssh/known_hosts /root/rcj/secrets/ops-bot-ssh/known_hosts
```

If it does not exist yet, create/populate it by connecting once to the required SSH hosts, for example:

```bash
ssh T1_newuser1
```

Then exit and copy it:

```bash
cp /root/.ssh/known_hosts /root/rcj/secrets/ops-bot-ssh/known_hosts
```

Set restrictive permissions:

```bash
chmod 600 /root/rcj/secrets/ops-bot-ssh/id_ed25519
chmod 600 /root/rcj/secrets/ops-bot-ssh/config
chmod 600 /root/rcj/secrets/ops-bot-ssh/known_hosts
```

At this point:

```bash
ls -la /root/rcj/secrets/ops-bot-ssh
```

should show approximately:

```text
config
id_ed25519
known_hosts
```

---

## 5. Give the mounted SSH directory the correct ownership for `ops-bot`

Do not assume the host user name will again appear as `dnsmasq:systemd-journal`. That was only how the container UID/GID mapped on the old server.

After building the new `rcj-ops-bot` image, query the UID/GID of the `opsbot` user inside the image:

```bash
cd /root/rcj/ops-bot
docker build -t rcj-ops-bot:latest .
```

Then:

```bash
docker run --rm --entrypoint sh rcj-ops-bot:latest -c 'id opsbot'
```

Example output:

```text
uid=999(opsbot) gid=995(opsbot) groups=995(opsbot)
```

Use the actual UID and GID returned by your image. Example only:

```bash
chown -R 999:995 /root/rcj/secrets/ops-bot-ssh
```

Then reapply permissions:

```bash
chmod 700 /root/rcj/secrets/ops-bot-ssh
chmod 600 /root/rcj/secrets/ops-bot-ssh/id_ed25519
chmod 600 /root/rcj/secrets/ops-bot-ssh/config
chmod 600 /root/rcj/secrets/ops-bot-ssh/known_hosts
```

This is important because the private key is mode `600`. If it remains owned by `root` while the container runs as `opsbot`, the container may not be able to read it.

---

## 6. Verify the SSH mount before starting the real bot

Run a temporary container with the same mount:

```bash
docker run --rm \
  -v "/root/rcj/secrets/ops-bot-ssh:/home/opsbot/.ssh:ro" \
  --entrypoint sh \
  rcj-ops-bot:latest \
  -c 'id && ls -la /home/opsbot/.ssh'
```

Verify that `opsbot` can read the private key:

```bash
docker run --rm \
  -v "/root/rcj/secrets/ops-bot-ssh:/home/opsbot/.ssh:ro" \
  --entrypoint sh \
  rcj-ops-bot:latest \
  -c 'ssh-keygen -y -f /home/opsbot/.ssh/id_ed25519 >/dev/null && echo SSH_KEY_OK'
```

Expected:

```text
SSH_KEY_OK
```

You can also test the configured remote connection from inside the container:

```bash
docker run --rm \
  -v "/root/rcj/secrets/ops-bot-ssh:/home/opsbot/.ssh:ro" \
  --entrypoint sh \
  rcj-ops-bot:latest \
  -c 'ssh -o BatchMode=yes T1_newuser1 "echo SSH_OK"'
```

Expected:

```text
SSH_OK
```

---

## 7. Run `rcj-ops-bot`

Make sure persistent bot data exists:

```bash
mkdir -p /root/rcj/ops-bot/.docker-data
```

Then run:

```bash
docker rm -f rcj-ops-bot 2>/dev/null || true

docker run -d --name rcj-ops-bot \
  --env-file /root/rcj/ops-bot/.env \
  -v "/root/rcj/secrets/ops-bot-ssh:/home/opsbot/.ssh:ro" \
  -v "/root/rcj/ops-bot/.docker-data:/data" \
  --restart unless-stopped \
  rcj-ops-bot:latest
```

Check status:

```bash
docker ps
```

Check logs:

```bash
docker logs --tail 100 rcj-ops-bot
```

Follow logs live:

```bash
docker logs -f rcj-ops-bot
```

---

## 8. Recommended SSH security after migration

Once key-based SSH login to the new Ubuntu server is confirmed, use a dedicated Mac-to-server key instead of copying the same private key everywhere when practical.

For example, the Mac can use:

```text
~/.ssh/zeabur_ed25519
```

for logging into the VPS, while `/root/.ssh/id_ed25519` on the VPS is used only for outbound connections such as GitHub or `T1_newuser1`.

At minimum, ensure all private keys have mode `600` and all `.ssh` directories have mode `700`.

---

## 9. Quick verification checklist

Run on the new Ubuntu server:

```bash
ls -la /root/.ssh
ls -la /root/rcj/secrets/ops-bot-ssh
ssh -T git@github.com
ssh T1_newuser1
docker ps
docker logs --tail 50 rcj-ops-bot
```

Expected final structure:

```text
/root/
├── .ssh/
│   ├── config
│   ├── id_ed25519
│   └── known_hosts
└── rcj/
    ├── ops-bot/
    │   ├── .env
    │   └── .docker-data/
    ├── reports/
    └── secrets/
        └── ops-bot-ssh/
            ├── config
            ├── id_ed25519
            └── known_hosts
```

## Important backup reminder before reinstalling ZeaburOS

Reinstalling the OS can wipe the existing server. Before switching to Ubuntu, copy the following off the current VPS:

```text
/root/rcj/
/root/.ssh/
Signal persistent data
PostgreSQL backup
Prefect configuration / .env files
```

Do not proceed with the OS reinstall until these backups are confirmed on another machine.
