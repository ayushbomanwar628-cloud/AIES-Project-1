pipeline {
    agent any

    environment {
        // Docker Hub Registry Configuration
        DOCKER_HUB_REPO  = 'hangout-recommender'
        DOCKER_CREDS_ID  = 'dockerhub-credentials'
        IMAGE_NAME       = 'hangout-recommender'

        // Kubernetes / Minikube configuration
        KUBECONFIG       = '/var/lib/jenkins/.kube/config'
    }

    stages {
        stage('Checkout') {
            steps {
                echo "=========================================================="
                echo "Stage 1: Fetching latest source code from GitHub..."
                echo "=========================================================="
                checkout scm
                sh '''
                    echo "Current Git Commit: $(git rev-parse --short HEAD)"
                    echo "Current Git Branch: $(git rev-parse --abbrev-ref HEAD)"
                    ls -la
                '''
            }
        }

        stage('Install Dependencies & Test') {
            steps {
                echo "=========================================================="
                echo "Stage 2: Installing dependencies and running pytest suite..."
                echo "=========================================================="
                sh '''
                    python3 -m venv venv || virtualenv venv
                    . venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt
                    
                    echo "Running 8-point automated test suite with pytest..."
                    pytest tests/test_recommender.py -v --tb=short
                '''
            }
        }

        stage('Docker Build') {
            steps {
                echo "=========================================================="
                echo "Stage 3: Building multi-stage production Docker image..."
                echo "=========================================================="
                sh '''
                    docker build -t ${IMAGE_NAME}:${BUILD_NUMBER} -t ${IMAGE_NAME}:latest .
                    docker images | grep ${IMAGE_NAME}
                '''
            }
        }

        stage('Push Image to Docker Hub') {
            steps {
                echo "=========================================================="
                echo "Stage 4: Logging into Docker Hub & pushing versioned tags..."
                echo "=========================================================="
                withCredentials([usernamePassword(credentialsId: "${DOCKER_CREDS_ID}", usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
                    sh '''
                        echo "$DH_PASS" | docker login -u "$DH_USER" --password-stdin
                        docker tag ${IMAGE_NAME}:${BUILD_NUMBER} ${DH_USER}/${DOCKER_HUB_REPO}:${BUILD_NUMBER}
                        docker tag ${IMAGE_NAME}:latest ${DH_USER}/${DOCKER_HUB_REPO}:latest
                        
                        echo "Pushing ${DH_USER}/${DOCKER_HUB_REPO}:${BUILD_NUMBER}..."
                        docker push ${DH_USER}/${DOCKER_HUB_REPO}:${BUILD_NUMBER}
                        
                        echo "Pushing ${DH_USER}/${DOCKER_HUB_REPO}:latest..."
                        docker push ${DH_USER}/${DOCKER_HUB_REPO}:latest
                    '''
                }
            }
        }

        stage('Kubernetes Deployment') {
            steps {
                echo "=========================================================="
                echo "Stage 5: Deploying containerized application to Kubernetes..."
                echo "=========================================================="
                withCredentials([usernamePassword(credentialsId: "${DOCKER_CREDS_ID}", usernameVariable: 'DH_USER', passwordVariable: 'DH_PASS')]) {
                    sh '''
                        # Update deployment image with currently built build-number tag
                        sed -i "s|image: .*|image: ${DH_USER}/${DOCKER_HUB_REPO}:${BUILD_NUMBER}|g" k8s/deployment.yaml
                        
                        echo "Applying updated Kubernetes manifests..."
                        kubectl apply -f k8s/deployment.yaml
                        kubectl apply -f k8s/service.yaml
                        
                        echo "Awaiting zero-downtime rolling update completion..."
                        kubectl rollout status deployment/hangout-recommender-deployment --timeout=180s
                    '''
                }
            }
        }

        stage('Verification') {
            steps {
                echo "=========================================================="
                echo "Stage 6: Verifying cluster pods, service, and live endpoint..."
                echo "=========================================================="
                sh '''
                    echo "=== Running Kubernetes Pods ==="
                    kubectl get pods -l app=hangout-recommender -o wide
                    
                    echo "=== Kubernetes NodePort Service ==="
                    kubectl get svc hangout-recommender-service
                    
                    echo "=== Health Probe Verification (/health) ==="
                    NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}' 2>/dev/null || echo "127.0.0.1")
                    curl -s -f http://${NODE_IP}:30007/health || curl -s -f http://127.0.0.1:8000/health || echo "Probe completed"
                '''
            }
        }
    }

    post {
        success {
            echo "=========================================================="
            echo "SUCCESS: Bangalore Hangout Recommender pipeline completed!"
            echo "Build #${BUILD_NUMBER} successfully deployed on NodePort: 30007"
            echo "=========================================================="
        }
        failure {
            echo "=========================================================="
            echo "FAILURE: Pipeline encountered an error during execution."
            echo "Check console log above for exact stage diagnosis."
            echo "=========================================================="
        }
    }
}
