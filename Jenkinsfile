pipeline {

    agent any

    tools {
        jdk 'JDK17'
        maven 'Maven-3.9.16'
    }

    environment {
        APP_NAME = 'employment-management'

        IMAGE_NAME = 'us-central1-docker.pkg.dev/project-7e1069a7-5b78-49e8-9b8/quickstart-docker-repo/employment-management'
        IMAGE_TAG = "${BUILD_NUMBER}"

        GCP_PROJECT = 'project-7e1069a7-5b78-49e8-9b8'
        GCP_REGION = 'us-central1'
        GKE_CLUSTER = 'employee-managment-cluster-1'

        K8S_NAMESPACE = 'stateful-demo'
        K8S_DEPLOYMENT = 'employment-management'
    }

    stages {

        // ============================================================
        // CHECKOUT
        // ============================================================
        stage('Checkout') {
            steps {
                deleteDir()

                bat '''
                    git init
                    git remote add origin https://github.com/Manjunathamanjuu/Employment-Management.git
                    git fetch origin feature/Employment-Management
                    git checkout -B feature/Employment-Management FETCH_HEAD
                '''
            }
        }

        // ============================================================
        // VERIFY ENVIRONMENT
        // ============================================================
        stage('Verify Environment') {
            steps {
                bat '''
                    echo ================================
                    echo VERIFY ENVIRONMENT
                    echo ================================

                    echo JAVA VERSION:
                    java -version

                    echo.
                    echo MAVEN VERSION:
                    mvn -version

                    echo.
                    echo DOCKER VERSION:
                    docker --version

                    echo.
                    echo KUBECTL VERSION:
                    kubectl version --client

                    echo.
                    echo GCLOUD VERSION:
                    gcloud --version

                    echo.
                    echo HELM VERSION:
                    helm version

                    echo.
                    echo Environment verification completed.
                '''
            }
        }

        // ============================================================
        // BUILD
        // ============================================================
        stage('Build') {
            steps {
                bat '''
                    echo ================================
                    echo MAVEN BUILD
                    echo ================================

                    mvn clean package -DskipTests

                    echo.
                    echo Maven build completed successfully.
                '''
            }
        }

        // ============================================================
        // TEST
        // ============================================================
        stage('Test') {
            steps {
                bat '''
                    echo ================================
                    echo RUNNING TESTS
                    echo ================================

                    mvn test

                    echo.
                    echo Tests completed successfully.
                '''
            }
        }

        // ============================================================
        // DOCKER VERIFY
        // ============================================================
        stage('Docker Verify') {
            steps {
                bat '''
                    echo ================================
                    echo DOCKER VERIFICATION
                    echo ================================

                    docker info

                    echo.
                    echo Docker verification completed.
                '''
            }
        }

        // ============================================================
        // DOCKER BUILD
        // ============================================================
        stage('Docker Build') {
            steps {
                bat '''
                    echo ================================
                    echo DOCKER BUILD
                    echo ================================

                    docker build -t %IMAGE_NAME%:%IMAGE_TAG% .
                    docker tag %IMAGE_NAME%:%IMAGE_TAG% %IMAGE_NAME%:latest

                    echo.
                    echo Docker image built successfully.

                    docker images | findstr employment-management
                '''
            }
        }

        // ============================================================
        // DOCKER PUSH
        // ============================================================
        stage('Docker Push') {
            steps {
                bat '''
                    echo ================================
                    echo DOCKER PUSH TO GAR
                    echo ================================

                    gcloud auth configure-docker %GCP_REGION%-docker.pkg.dev --quiet

                    docker push %IMAGE_NAME%:%IMAGE_TAG%
                    docker push %IMAGE_NAME%:latest

                    echo.
                    echo Docker images pushed successfully.
                '''
            }
        }

        // ============================================================
        // KUBERNETES DEPLOY
        // ============================================================
        stage('Kubernetes Deploy') {
            steps {
                bat '''
                    echo ================================
                    echo GKE AUTHENTICATION
                    echo ================================

                    gcloud container clusters get-credentials %GKE_CLUSTER% --region %GCP_REGION% --project %GCP_PROJECT%

                    echo.
                    echo ================================
                    echo KUBERNETES DEPLOYMENT
                    echo ================================

                    kubectl get nodes

                    kubectl apply -f Kubernetes-manifests/namespace.yaml

                    kubectl apply -f Kubernetes-manifests/postgres-configmap.yaml

                    kubectl apply -f Kubernetes-manifests/postgres-secret.yaml

                    kubectl apply -f Kubernetes-manifests/service.yaml

                    kubectl apply -f Kubernetes-manifests/deployment.yaml

                    echo.
                    echo Kubernetes deployment applied successfully.
                '''
            }
        }

        // ============================================================
        // VERIFY DEPLOYMENT
        // ============================================================
        stage('Verify Deployment') {
            steps {
                bat '''
                    echo ================================
                    echo VERIFY KUBERNETES DEPLOYMENT
                    echo ================================

                    kubectl get pods -n %K8S_NAMESPACE%

                    echo.
                    kubectl get svc -n %K8S_NAMESPACE%

                    echo.
                    kubectl get deployment %K8S_DEPLOYMENT% -n %K8S_NAMESPACE%

                    echo.
                    echo ================================
                    echo ROLLOUT STATUS
                    echo ================================

                    kubectl rollout status deployment/%K8S_DEPLOYMENT% -n %K8S_NAMESPACE% --timeout=180s

                    echo.
                    echo Kubernetes deployment verified successfully.
                '''
            }
        }
    }

    post {

        success {
            echo '================================'
            echo 'CI/CD PIPELINE SUCCESSFUL'
            echo '================================'

            echo 'Build → Test → Docker Build → Docker Push → Kubernetes Deploy → Verify'
        }

        failure {
            echo '================================'
            echo 'CI/CD PIPELINE FAILED'
            echo '================================'

            echo 'Check the console output for the failed stage.'
        }

        always {
            echo 'Pipeline execution completed.'
        }
    }
}