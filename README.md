# CCA 2 — CI/CD Pipeline Implementation, Containerization, and Kubernetes Deployment on AWS EC2

**Institution**: Dr. Vishwanath Karad MIT World Peace University, Pune  
**Department**: Department of Computer Science & Engineering  
**Course**: TYCSE — Cloud Computing and DevOps  
**Course Coordinator**: Prof. Priya Nagargoje  
**Student Name**: Ayush Bomanwar  
**PRN**: 1262243601  
**Project Title**: Bangalore Hangout Recommender — AI-Powered Solo and Group Activity Planning Engine  
**GitHub Repository**: [https://github.com/ayushbomanwar628-cloud/AIES-Project-1](https://github.com/ayushbomanwar628-cloud/AIES-Project-1)  
**Target Infrastructure**: AWS EC2 (ap-south-1 Mumbai) · Jenkins LTS · Docker Hub · Kubernetes (Minikube/k3s) · NodePort 30007  

---

## 1. Project Overview & Architectural Summary
The **Bangalore Hangout Recommender** is an AI-based activity recommendation engine that assists individuals and friend groups in discovering engaging experiences in Bangalore based on mood, budget tier, and group size.

### Core Capabilities:
- **Comprehensive Dataset**: 219 categorized activity types mapped to 5,109 real Bangalore restaurants (Zomato) and 393 Bangalore venues (OpenStreetMap).
- **TF-IDF Semantic Vectorization**: Cosine similarity matching between user query text and activity descriptions.
- **Multi-Attribute Hard Filtering**: Enforces strict constraints on budget tiers (`free`, `low`, `medium`, `high`, `premium`), group sizes (1 to 10+), and weather/indoor-outdoor conditions.
- **Social-Choice Group Aggregation**: Evaluates 3 distinct group decision strategies head-to-head:
  - **Average**: Maximizes overall group happiness.
  - **Least Misery**: Maximizes the lowest individual member's satisfaction (protects the worst-off member).
  - **Borda Count**: Positional rank-order voting across members.
- **FastAPI Web Service & Health Probes**: Exposes REST endpoints (`/health`, `/api/version`, `/api/recommend/single`, `/api/recommend/group`) and serves an interactive web interface.

---

## 2. CI/CD Architecture & End-to-End Workflow

```
+---------------------------------------------------------------------------------------------------+
|                                      AWS EC2 (Mumbai ap-south-1)                                   |
|                                                                                                   |
|  +-------------------+       +-----------------------+       +---------------------------------+  |
|  |   GitHub Remote   | ----> |      Jenkins LTS      | ----> |       Automated Test Suite      |  |
|  |  (main branch)    |       |      (Port 8080)      |       |      8/8 Tests Passing (pytest) |  |
|  +-------------------+       +-----------------------+       +---------------------------------+  |
|                                          |                                                        |
|                                          v                                                        |
|  +-------------------+       +-----------------------+                                            |
|  |    Docker Hub     | <---- | Multi-Stage Build     |                                            |
|  |  Image Registry   |       | (python:3.11-slim)    |                                            |
|  +-------------------+       +-----------------------+                                            |
|           |                                                                                       |
|           v                                                                                       |
|  +---------------------------------------------------------------------------------------------+  |
|  |                       Kubernetes Cluster (Minikube / k3s)                                   |  |
|  |                                                                                             |  |
|  |  [NodePort Service: 30007] ---> [Pod Replica 1 (Port 8000)] <--- (/health probe: 200 OK)   |  |
|  |                                 [Pod Replica 2 (Port 8000)] <--- (/health probe: 200 OK)   |  |
|  |                                                                                             |  |
|  |  Strategy: RollingUpdate (maxSurge: 1, maxUnavailable: 0) -> Zero-Downtime Releases        |  |
|  +---------------------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------------------+
```

### Pipeline Stages (`Jenkinsfile`):
| # | Stage Name | Technical Action & Automation Logic |
|---|---|---|
| **1** | **Checkout** | Retrieves the latest source code from GitHub (`main` branch) using credentials stored securely in Jenkins. |
| **2** | **Install & Test** | Installs dependencies into a clean virtual environment and runs the 8-point automated test suite via `pytest`. |
| **3** | **Docker Build** | Compiles an optimized multi-stage container image tagged with `${BUILD_NUMBER}` and `latest`. |
| **4** | **Push to Docker Hub** | Authenticates securely with Docker Hub using encrypted Jenkins credentials and pushes both tags. |
| **5** | **Kubernetes Rollout** | Injects the newly pushed image tag into `k8s/deployment.yaml`, applies manifests, and awaits rollout. |
| **6** | **Verification** | Validates running pods (`kubectl get pods`), checks the service (`kubectl get svc`), and curls `/health`. |

---

## 3. Repository File Structure

```
.
├── app/
│   ├── vectorizer.py            # TF-IDF embedding engine and activity corpus loader
│   ├── filters.py               # Hard constraint filter (budget, group size, weather)
│   ├── single_user.py           # Single-user recommendation scoring and ranking
│   ├── group.py                 # Multi-user group decision engine (Average, Least Misery, Borda)
│   └── demo.py                  # Standalone CLI demonstration script
├── data/
│   ├── unified_activities.csv   # Unified raw venue-level dataset (5,698 rows)
│   ├── activity_types.csv       # Collapsed generic activity types (219 rows)
│   └── activity_types_tagged.csv# Tagged activities with mood labels, energy, and costs
├── k8s/
│   ├── deployment.yaml          # 2 replicas, RollingUpdate, non-root, liveness & readiness probes
│   └── service.yaml             # NodePort service exposing application externally on port 30007
├── scripts/
│   ├── merge_pipeline.py        # Merges Bored API, Zomato, and OSM datasets
│   ├── build_activity_types.py  # Collapses venues into generic activity types
│   └── tag_moods.py             # Rule-based tagging across 8 mood dimensions
├── tests/
│   └── test_recommender.py      # Comprehensive 8-point automated unit test suite (pytest)
├── web/
│   ├── hangout_finder.html      # Responsive web UI displaying cloud status and version badges
│   └── activities_embedded_reference.json
├── .dockerignore                # Build context exclusion rules
├── .gitignore                   # Version control exclusion rules
├── Dockerfile                   # Hardened multi-stage build (python:3.11-slim, non-root user)
├── Jenkinsfile                  # 6-stage enterprise declarative delivery pipeline
├── README.md                    # Project documentation, architecture, and demonstration guide
├── requirements.txt             # Production and testing Python dependencies
├── server.py                    # Production FastAPI web server & healthcheck endpoint provider
└── version.py                   # Single source of truth for application version metadata
```

---

## 4. Containerization & Dockerfile Design
The container image utilizes a **multi-stage build** based on `python:3.11-slim`:
- **Stage 1 (Builder)**: Installs temporary compilation toolchain (`build-essential`, `gcc`) and pre-installs dependencies into `/install`.
- **Stage 2 (Runner)**: Minimal runtime container copying only compiled packages from Stage 1, eliminating build tools from the final attack surface.
- **Security**: Creates an unprivileged system user (`appuser`, UID `10001`) and enforces non-root execution.
- **Health Monitoring**: Built-in `HEALTHCHECK` directive queries `http://localhost:8000/health` every 30 seconds.

---

## 5. Automated Test Suite (Pytest)
An 8-point automated unit test suite (`tests/test_recommender.py`) validates the system:
1. `test_01_load_activities_dataset`: Verifies loading 191 recommendable activities with complete schema.
2. `test_02_activity_index_tfidf`: Validates TF-IDF vector fitting and cosine similarity bounds [0.0, 1.0].
3. `test_03_filters_budget_and_group_size`: Ensures hard constraints strictly filter higher-cost activities.
4. `test_04_single_user_recommendation`: Verifies single-user recommendations are sorted descending by score.
5. `test_05_group_aggregation_average`: Tests Mean Happiness Maximization against individual scores.
6. `test_06_group_aggregation_least_misery`: Tests Worst-Off Member Protection (`min(member_scores)`).
7. `test_07_group_aggregation_borda`: Tests Positional Borda Count rank-order voting scores.
8. `test_08_fastapi_health_and_api_endpoints`: Tests FastAPI `/health`, `/api/version`, and `/api/recommend/single`.

Run locally:
```bash
pytest tests/test_recommender.py -v
```

---

## 6. Kubernetes Orchestration Manifests
- **Deployment (`k8s/deployment.yaml`)**:
  - Replicas: 2
  - Strategy: `RollingUpdate` (`maxSurge: 1`, `maxUnavailable: 0`)
  - Resource Requests: 100m CPU, 128Mi RAM; Limits: 500m CPU, 512Mi RAM
  - Probes: Liveness and Readiness HTTP probes targeting `/health` on port 8000
- **Service (`k8s/service.yaml`)**:
  - Type: `NodePort`
  - Internal Port: 8000
  - NodePort: `30007`

---

## 7. Version Upgrade Demonstration (v1.0.0 → v1.1.0)
To verify automated CI/CD continuous deployment:
1. Baseline release runs at **v1.0.0**.
2. Update `version.py` to `__version__ = "1.1.0"`.
3. Commit and push:
   ```bash
   git add version.py
   git commit -m "feat(release): upgrade application to version v1.1.0"
   git push origin main
   ```
4. Trigger **Build Now** in Jenkins.
5. Jenkins automatically checks out the update, executes all 8 tests, builds image tag `:2`, pushes to Docker Hub, applies rolling update to Kubernetes, and verifies `/health`.
6. Live application at `http://<EC2-IP>:30007/` displays the **v1.1.0** version badge with zero downtime.

---

## 8. AWS EC2 Cloud Setup Guide ($0.00 Free Tier)
1. **EC2 Instance**: Launch an Ubuntu 22.04 LTS or Amazon Linux 2023 instance (`t2.micro` or `t3.micro` for Free Tier, or `t3.large` for fast lab assessment).
2. **Security Group Inbound Rules**:
   - `SSH` (22): Restricted to your IP
   - `Jenkins` (8080): Restricted to your IP / Evaluator
   - `Kubernetes NodePort` (30007): Anywhere (0.0.0.0/0) for public evaluation
3. **Install Core Toolchain**:
   ```bash
   # Docker
   sudo apt-get update && sudo apt-get install -y docker.io git
   sudo usermod -aG docker jenkins && sudo usermod -aG docker $USER
   
   # Jenkins LTS
   sudo apt-get install -y openjdk-17-jre
   curl -fsSL https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key | sudo tee /usr/share/keyrings/jenkins-keyring.asc > /dev/null
   echo deb [signed-by=/usr/share/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/ | sudo tee /etc/apt/sources.list.d/jenkins.list > /dev/null
   sudo apt-get update && sudo apt-get install -y jenkins
   sudo systemctl enable --now jenkins
   
   # Kubernetes (k3s or Minikube)
   curl -sfL https://get.k3s.io | sh -
   mkdir -p /var/lib/jenkins/.kube
   sudo cp /etc/rancher/k3s/k3s.yaml /var/lib/jenkins/.kube/config
   sudo chown -R jenkins:jenkins /var/lib/jenkins/.kube
   ```
