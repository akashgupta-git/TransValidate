# TransValidate

**TransValidate** is a lightweight, cloud-native validation service designed to streamline data verification workflows. Built with a modern DevOps mindset, the project demonstrates a complete CI/CD lifecycle—automating infrastructure provisioning via **Terraform**, containerization with **Docker**, and continuous deployment through a **Jenkins Declarative Pipeline** to **AWS EC2**.

---

## 🚀 Key Features

* **RESTful API:** Developed using Python/Flask to handle validation logic efficiently.
* **Infrastructure as Code (IaC):** Full AWS environment (VPC, Subnets, Security Groups, and EC2) provisioned using Terraform.
* **Automated CI/CD:** A robust Jenkins pipeline that handles code checkout, image building, and remote deployment.
* **Containerized Deployment:** Dockerized application for environment parity and simplified scaling.
* **Security First:** Configured with specific AWS Security Groups to minimize attack vectors.

---

## 🛠️ Tech Stack

| Category | Tools |
| --- | --- |
| **Backend** | Python 3.9, Flask |
| **Infrastructure** | Terraform, AWS (EC2, VPC, IGW) |
| **DevOps & CI/CD** | Jenkins (Pipeline-as-Code), Docker |
| **Environment** | Ubuntu 22.04 LTS |

---

## 📂 Project Structure

```text
.
├── app.py              # Flask application logic
├── Dockerfile          # Container configuration
├── Jenkinsfile         # Declarative CI/CD pipeline script
├── requirements.txt    # Python dependencies
└── terraform/
    ├── main.tf         # AWS resource definitions
    └── outputs.tf      # Infrastructure metadata (IPs, IDs)

```

---

## ⚙️ Setup & Deployment

### 1. Infrastructure Provisioning

Initialize and deploy the AWS environment using Terraform:

```bash
cd terraform
terraform init
terraform apply -auto-approve

```

### 2. Manual Local Execution

If you wish to run the application locally for testing:

```bash
# Build the image
docker build -t transvalidate:v1 .

# Run the container
docker run -d -p 5002:5002 transvalidate:v1

```

### 3. CI/CD Pipeline Logic

The included `Jenkinsfile` automates the following stages upon every push to the `main` branch:

1. **Stage: Checkout** - Pulls the latest source code from GitHub.
2. **Stage: Deploy to AWS** - Connects to the EC2 instance via SSH, nukes legacy containers, rebuilds the Docker image, and launches the fresh instance on Port 80.

---

## 🔧 Infrastructure Details

The Terraform configuration ensures the following environment is ready:

* **VPC:** `10.0.0.0/16` CIDR block for network isolation.
* **Security Groups:** * Port `22`: Restricted SSH access.
* Port `80`: Public web traffic (mapped to app).
* Port `5002`: Internal application port.


* **Instance:** `t2.micro` running Ubuntu 22.04.

---

## 📝 Future Roadmap

* [ ] Implement a Redis-based caching layer for validation results.
* [ ] Add Prometheus/Grafana monitoring for container health.
* [ ] Transition from a single EC2 instance to an AWS ECS/Fargate cluster for high availability.

---

## 🤝 Contact

**Akash Gupta** *Software Developer & DevOps Enthusiast* [GitHub](https://www.google.com/search?q=https://github.com/akashgupta-git) | [LinkedIn](https://www.google.com/search?q=%23)

---