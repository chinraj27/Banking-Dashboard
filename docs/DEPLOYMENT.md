# Cloud deployment guide

Both options run the same two images (`backend`, `frontend`). In the cloud, the managed load balancer replaces
the local Nginx container: it sends `/api/*` to the backend and everything else to the frontend.

## Environment variables (backend)

| Variable | Example | Notes |
|---|---|---|
| `DATABASE_URL` | `postgresql://user:pass@host:5432/banking` | RDS / Azure Database for PostgreSQL |
| `MONGO_URL` | `mongodb+srv://user:pass@cluster.mongodb.net/` | See "MongoDB" below |
| `REDIS_URL` | `rediss://:pass@host:6379/0` | Use `rediss://` when TLS is on |
| `JWT_SECRET` | 48+ random characters | Keep in a secret store, not in the task definition text |
| `ACCESS_TOKEN_MINUTES` | `60` | |
| `CORS_ORIGINS` | `https://bank.example.com` | Your public site URL |
| `SEED_DEMO_DATA` | `false` | Use `true` once for a demo environment, then `false` |

Always run with `SEED_DEMO_DATA=false` in any environment that is not a throwaway demo, because the seed creates known demo passwords.

## MongoDB

Neither cloud has a native MongoDB service. Use **MongoDB Atlas** (available on both AWS and Azure; recommended),
or **Amazon DocumentDB** / **Azure Cosmos DB for MongoDB**, which are MongoDB-compatible but not identical.
Test the activity-log and metadata features against whichever you choose. The app keeps working if Mongo is
unreachable (logs are held in memory), but logs are then lost on restart.

---

## Option A: AWS (ECS Fargate)

Components: ECR (images), ECS Fargate (containers), RDS PostgreSQL, ElastiCache Redis, an Application Load Balancer,
Secrets Manager, and optionally S3 + CloudFront for the static site.

1. **Network.** Use a VPC with two public subnets (ALB) and two private subnets (tasks, RDS, ElastiCache).
2. **Image registries.**
   ```powershell
   aws ecr create-repository --repository-name banking-backend
   aws ecr create-repository --repository-name banking-frontend
   ```
3. **Database.** Create an RDS PostgreSQL 16 instance in the private subnets (Multi-AZ for production, encrypted storage).
   Run `backend/sql/schema.sql` against it once (the API also creates missing tables on startup).
4. **Redis.** Create an ElastiCache for Redis replication group with in-transit encryption and an auth token.
5. **Security groups.** ALB accepts 443 from the internet; tasks accept 8000 and 80 only from the ALB; RDS accepts 5432
   and ElastiCache accepts 6379 only from the tasks.
6. **Secrets.** Store `JWT_SECRET`, `DATABASE_URL`, `MONGO_URL`, `REDIS_URL` in Secrets Manager and reference them from the task definition's `secrets` block.
7. **ECS.** Create a cluster `banking-cluster` and one service `banking-service` whose task definition has two containers:
   `backend` (port 8000) and `frontend` (port 80). Create two ALB target groups and listener rules:
   - path `/api/*` to the backend target group (health check `/api/health`)
   - default rule to the frontend target group (health check `/`)
   Use one service per container if you want to scale them separately; then update the workflow to roll out both.
8. **HTTPS.** Request an ACM certificate, attach it to the ALB 443 listener, and redirect 80 to 443.
9. **CI/CD.** In GitHub, create an IAM role trusted for GitHub OIDC with permission to push to ECR and update the
   ECS service, and add its ARN as the repository secret `AWS_DEPLOY_ROLE_ARN`. Adjust the `env:` block at the top of
   `.github/workflows/ci-cd.yml` (region, repository names, cluster, service). Pushes to `main` then deploy automatically.

**S3 for static assets (optional).** Instead of the `frontend` container, build with `npm run build`, upload `dist/`
to an S3 bucket (block public access), and serve it through CloudFront with the ALB as a second origin for `/api/*`.
Add a CloudFront error rule that returns `/index.html` for 403/404 so React Router paths work.

## Option B: Azure (Container Apps)

Components: Azure Container Registry, Container Apps, Azure Database for PostgreSQL Flexible Server,
Azure Cache for Redis, Key Vault, and optionally Blob Storage static website hosting.

```powershell
$rg = "banking-rg"; $loc = "centralindia"; $acr = "bankingacr$(Get-Random -Maximum 9999)"

az group create -n $rg -l $loc
az acr create -n $acr -g $rg --sku Basic
az acr build -r $acr -t banking-backend:latest  ./backend
az acr build -r $acr -t banking-frontend:latest ./frontend

# Managed services
az postgres flexible-server create -g $rg -n banking-pg --version 16 --admin-user bankadmin --admin-password "<strong-password>" --database-name banking
az redis create -g $rg -n banking-redis --location $loc --sku Basic --vm-size c0

# Container Apps environment and apps
az containerapp env create -g $rg -n banking-env -l $loc
az containerapp create -g $rg -n frontend --environment banking-env `
  --image "$acr.azurecr.io/banking-frontend:latest" --registry-server "$acr.azurecr.io" `
  --target-port 80 --ingress external --min-replicas 1
az containerapp create -g $rg -n backend --environment banking-env `
  --image "$acr.azurecr.io/banking-backend:latest" --registry-server "$acr.azurecr.io" `
  --target-port 8000 --ingress external --min-replicas 1 `
  --secrets jwt=<value> dburl="<DATABASE_URL>" mongourl="<MONGO_URL>" redisurl="<REDIS_URL>" `
  --env-vars JWT_SECRET=secretref:jwt DATABASE_URL=secretref:dburl MONGO_URL=secretref:mongourl `
             REDIS_URL=secretref:redisurl CORS_ORIGINS=https://<frontend-fqdn> SEED_DEMO_DATA=false
```

Routing: the browser calls `/api` on the same origin as the page. The simplest way to get that on Azure is to put
**Azure Front Door** (or Application Gateway) in front, with `/api/*` routed to the backend app and `/*` to the frontend app.
Alternatively build the frontend with `VITE_API_URL=https://<backend-fqdn>/api` and add the frontend URL to `CORS_ORIGINS`.

Allow the Container Apps environment to reach PostgreSQL and Redis (private endpoints or firewall rules), and require TLS.
For CI/CD on Azure, replace the `deploy` job in the workflow with `azure/login` (OIDC) plus `az containerapp update --image ...`.

**Blob Storage for static assets (optional).** Enable static website hosting on a storage account, upload `dist/`,
and put Front Door in front with `/api/*` going to the backend.

## Production checklist

- Generate a new `JWT_SECRET`; set `SEED_DEMO_DATA=false`.
- HTTPS only; restrict `CORS_ORIGINS` to the real site.
- Enable database backups and encryption at rest.
- Add login rate limiting (for example at the load balancer or WAF) and consider an HttpOnly-cookie session.
- Replace `create_all` with Alembic migrations.
- Send container logs to CloudWatch or Azure Monitor and alert on `/api/health` failures.
