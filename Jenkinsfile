pipeline {

    agent any

    tools {
        jdk 'JDK-17'
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

        // Google Cloud SDK
        GCLOUD_HOME = 'C:\\Users\\prajw_626z6xf\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk'
        CLOUDSDK_PYTHON = 'C:\\Users\\prajw_626z6xf\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk\\platform\\bundledpython\\python.exe'
    }

    stages {

        // ============================================================
        // CHECKOUT
        // ============================================================
        stage('Checkout') {
            steps {
                deleteDir()

                bat '''
                    echo ================================
                    echo CHECKOUT SOURCE CODE
                    echo ================================

                    git init
                    if errorlevel 1 exit /b 1

                    git remote add origin https://github.com/Manjunathamanjuu/Employment-Management.git
                    if errorlevel 1 exit /b 1

                    git fetch origin feature/Employment-Management
                    if errorlevel 1 exit /b 1

                    git checkout -B feature/Employment-Management FETCH_HEAD
                    if errorlevel 1 exit /b 1

                    echo.
                    echo Checkout completed successfully.
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

                    echo.
                    echo JAVA VERSION:
                    java -version
                    if errorlevel 1 exit /b 1

                    echo.
                    echo MAVEN VERSION:
                    mvn -version
                    if errorlevel 1 exit /b 1

                    echo.
                    echo DOCKER VERSION:
                    docker --version
                    if errorlevel 1 exit /b 1

                    echo.
                    echo KUBECTL VERSION:
                    kubectl version --client
                    if errorlevel 1 exit /b 1

                    echo.
                    echo GCLOUD VERSION:
                    "%GCLOUD_HOME%\\bin\\gcloud.cmd" --version
                    if errorlevel 1 exit /b 1

                    echo.
                    echo HELM VERSION:
                    helm version
                    if errorlevel 1 exit /b 1

                    echo.
                    echo Environment verification completed successfully.
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
                    if errorlevel 1 exit /b 1

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
                    if errorlevel 1 exit /b 1

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
                    if errorlevel 1 exit /b 1

                    echo.
                    echo Docker verification completed successfully.
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
                    if errorlevel 1 exit /b 1

                    docker tag %IMAGE_NAME%:%IMAGE_TAG% %IMAGE_NAME%:latest
                    if errorlevel 1 exit /b 1

                    echo.
                    echo Docker image built successfully.

                    echo.
                    echo DOCKER IMAGES:
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

                    echo.
                    echo ================================
                    echo GCLOUD VERSION
                    echo ================================

                    "%GCLOUD_HOME%\\bin\\gcloud.cmd" --version
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo GOOGLE CLOUD AUTHENTICATION
                    echo ================================

                    "%GCLOUD_HOME%\\bin\\gcloud.cmd" auth list
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo CONFIGURING GAR AUTHENTICATION
                    echo ================================

                    "%GCLOUD_HOME%\\bin\\gcloud.cmd" auth configure-docker %GCP_REGION%-docker.pkg.dev --quiet
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo PUSHING BUILD IMAGE
                    echo ================================

                    docker push %IMAGE_NAME%:%IMAGE_TAG%
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo PUSHING LATEST IMAGE
                    echo ================================

                    docker push %IMAGE_NAME%:latest
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo DOCKER PUSH SUCCESSFUL
                    echo ================================
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

                    "%GCLOUD_HOME%\\bin\\gcloud.cmd" container clusters get-credentials %GKE_CLUSTER% --region %GCP_REGION% --project %GCP_PROJECT%
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo KUBERNETES CLUSTER
                    echo ================================

                    kubectl get nodes
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo APPLYING NAMESPACE
                    echo ================================

                    kubectl apply -f Kubernetes-manifests/namespace.yaml
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo APPLYING POSTGRES CONFIGMAP
                    echo ================================

                    kubectl apply -f Kubernetes-manifests/postgres-configmap.yaml
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo APPLYING POSTGRES SECRET
                    echo ================================

                    kubectl apply -f Kubernetes-manifests/postgres-secret.yaml
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo APPLYING SERVICE
                    echo ================================

                    kubectl apply -f Kubernetes-manifests/service.yaml
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo APPLYING DEPLOYMENT
                    echo ================================

                    kubectl apply -f Kubernetes-manifests/deployment.yaml
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo KUBERNETES DEPLOYMENT APPLIED
                    echo ================================
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

                    echo.
                    echo PODS:
                    kubectl get pods -n %K8S_NAMESPACE%
                    if errorlevel 1 exit /b 1


                    echo.
                    echo SERVICES:
                    kubectl get svc -n %K8S_NAMESPACE%
                    if errorlevel 1 exit /b 1


                    echo.
                    echo DEPLOYMENT:
                    kubectl get deployment %K8S_DEPLOYMENT% -n %K8S_NAMESPACE%
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo ROLLOUT STATUS
                    echo ================================

                    kubectl rollout status deployment/%K8S_DEPLOYMENT% -n %K8S_NAMESPACE% --timeout=180s
                    if errorlevel 1 exit /b 1


                    echo.
                    echo ================================
                    echo KUBERNETES DEPLOYMENT VERIFIED
                    echo ================================
                '''
            }
        }
    }


    // ================================================================
    // POST ACTIONS
    // ================================================================
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

