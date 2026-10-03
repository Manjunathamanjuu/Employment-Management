pipeline {
    agent any

    tools {
        jdk 'JDK-17'
        maven 'Maven-3.9.16'
    }

    options {
        timeout(time: 60, unit: 'MINUTES')
        disableConcurrentBuilds()
        skipDefaultCheckout(true)
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    parameters {
        string(
            name: 'BRANCH',
            defaultValue: 'feature/Employment-Management',
            description: 'Git branch to build'
        )

        string(
            name: 'IMAGE_TAG',
            defaultValue: '',
            description: 'Docker image tag. Leave empty to use BUILD_NUMBER.'
        )

        booleanParam(
            name: 'RUN_TESTS',
            defaultValue: true,
            description: 'Run Maven tests'
        )

        booleanParam(
            name: 'DEPLOY_TO_GKE',
            defaultValue: true,
            description: 'Deploy application to GKE'
        )
    }

    environment {

        // =========================
        // APPLICATION
        // =========================
        APP_NAME = 'employment-management'

        // =========================
        // DOCKER HUB
        // =========================
        DOCKERHUB_USERNAME = 'YOUR_DOCKERHUB_USERNAME'
        DOCKER_IMAGE = "${DOCKERHUB_USERNAME}/employment-management"

        // =========================
        // GCP / GKE
        // =========================
        GCP_PROJECT = 'project-7e1069a7-5b78-49e8-9b8'
        GCP_REGION = 'us-central1'

        GKE_CLUSTER = 'employee-managment-cluster-1'
        GKE_LOCATION = 'us-central1'

        // =========================
        // KUBERNETES
        // =========================
        K8S_NAMESPACE = 'stateful-demo'
        K8S_DEPLOYMENT = 'employment-management'

        // =========================
        // GOOGLE CLOUD SDK
        // =========================
        GCLOUD_HOME = 'C:\\Users\\prajw_626z6xf\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk'

        CLOUDSDK_PYTHON = 'C:\\Users\\prajw_626z6xf\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk\\platform\\bundledpython\\python.exe'

        // =========================
        // DOCKER DESKTOP
        // =========================
        DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'

        // =========================
        // GKE AUTH PLUGIN
        // =========================
        USE_GKE_GCLOUD_AUTH_PLUGIN = 'True'
    }

    stages {

        // =========================================================
        // 1. ENVIRONMENT CHECK
        // =========================================================
        stage('Environment Check') {
            steps {
                bat '''
                    echo ==========================================
                    echo ENVIRONMENT CHECK
                    echo ==========================================

                    echo.
                    echo Java Version:
                    java -version

                    echo.
                    echo Maven Version:
                    mvn -version

                    echo.
                    echo Docker Version:
                    docker --version

                    echo.
                    echo Kubectl Version:
                    kubectl version --client

                    echo.
                    echo Google Cloud Version:
                    gcloud --version

                    echo.
                    echo Helm Version:
                    helm version

                    echo.
                    echo Docker Host:
                    echo %DOCKER_HOST%

                    echo.
                    echo Docker Hub Image:
                    echo %DOCKER_IMAGE%:%IMAGE_TAG%

                    echo ==========================================
                '''
            }
        }

        // =========================================================
        // 2. CHECKOUT
        // =========================================================
        stage('Checkout') {
            steps {
                deleteDir()

                checkout([
                    $class: 'GitSCM',
                    branches: [[name: "*/${params.BRANCH}"]],
                    userRemoteConfigs: [[
                        url: 'https://github.com/Manjunathamanjuu/Employment-Management.git',
                        credentialsId: 'github-pat'
                    ]]
                ])

                bat '''
                    echo.
                    echo ==========================================
                    echo GIT INFORMATION
                    echo ==========================================

                    git branch
                    git log -1 --oneline

                    echo ==========================================
                '''
            }
        }

        // =========================================================
        // 3. DOCKER VERIFY
        // =========================================================
        stage('Docker Verify') {
            steps {
                bat '''
                    echo ==========================================
                    echo DOCKER VERIFY
                    echo ==========================================

                    docker version
                    docker info

                    echo ==========================================
                '''
            }
        }

        // =========================================================
        // 4. MAVEN BUILD
        // =========================================================
        stage('Maven Build') {
            steps {
                bat '''
                    echo ==========================================
                    echo MAVEN BUILD
                    echo ==========================================

                    mvn -B -ntp clean package -DskipTests

                    echo ==========================================
                '''
            }
        }

        // =========================================================
        // 5. MAVEN TEST
        // =========================================================
        stage('Maven Test') {
            when {
                expression {
                    return params.RUN_TESTS
                }
            }

            steps {
                bat '''
                    echo ==========================================
                    echo MAVEN TEST
                    echo ==========================================

                    set TESTCONTAINERS_RYUK_DISABLED=true

                    mvn -B -ntp test

                    echo.
                    echo Cleaning Testcontainers...
                    for /f %%i in ('docker ps -aq --filter "label=org.testcontainers=true"') do docker rm -f %%i

                    echo ==========================================
                '''
            }
        }

        // =========================================================
        // 6. DOCKER BUILD
        // =========================================================
        stage('Docker Build') {
            steps {
                script {
                    env.FINAL_IMAGE_TAG = params.IMAGE_TAG?.trim()
                        ? params.IMAGE_TAG.trim()
                        : env.BUILD_NUMBER
                }

                bat '''
                    echo ==========================================
                    echo DOCKER BUILD
                    echo ==========================================

                    echo Image:
                    echo %DOCKER_IMAGE%:%FINAL_IMAGE_TAG%

                    docker build ^
                        -t %DOCKER_IMAGE%:%FINAL_IMAGE_TAG% ^
                        -t %DOCKER_IMAGE%:latest .

                    echo.
                    echo Docker Images:
                    docker images %DOCKER_IMAGE%

                    echo ==========================================
                '''
            }
        }

        // =========================================================
        // 7. DOCKER HUB PUSH
        // =========================================================
        stage('Docker Hub Push') {
            steps {

                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub-credentials',
                        usernameVariable: 'DOCKERHUB_USER',
                        passwordVariable: 'DOCKERHUB_TOKEN'
                    )
                ]) {

                    bat '''
                        echo ==========================================
                        echo DOCKER HUB LOGIN
                        echo ==========================================

                        echo Logging into Docker Hub...

                        docker login -u "%DOCKERHUB_USER%" -p "%DOCKERHUB_TOKEN%"

                        if %ERRORLEVEL% NEQ 0 (
                            echo Docker Hub login failed.
                            exit /b 1
                        )

                        echo.
                        echo Docker Hub login successful.

                        echo ==========================================
                        echo PUSHING DOCKER IMAGE
                        echo ==========================================

                        docker push %DOCKER_IMAGE%:%FINAL_IMAGE_TAG%

                        if %ERRORLEVEL% NEQ 0 (
                            echo Docker image push failed.
                            exit /b 1
                        )

                        echo.
                        echo Pushing latest tag...

                        docker push %DOCKER_IMAGE%:latest

                        if %ERRORLEVEL% NEQ 0 (
                            echo Docker latest image push failed.
                            exit /b 1
                        )

                        echo.
                        echo Docker Hub images pushed successfully.

                        echo ==========================================
                    '''
                }
            }
        }

        // =========================================================
        // 8. GKE AUTHENTICATION
        // =========================================================
        stage('GKE Authentication') {
            when {
                expression {
                    return params.DEPLOY_TO_GKE
                }
            }

            steps {

                withCredentials([
                    file(
                        credentialsId: 'gcp-jenkins-cicd',
                        variable: 'GCP_KEY_FILE'
                    )
                ]) {

                    bat '''
                        echo ==========================================
                        echo GKE AUTHENTICATION
                        echo ==========================================

                        set CLOUDSDK_CONFIG=%WORKSPACE%\\.gcloud-%BUILD_NUMBER%
                        set KUBECONFIG=%WORKSPACE%\\.kubeconfig-%BUILD_NUMBER%

                        if not exist "%CLOUDSDK_CONFIG%" mkdir "%CLOUDSDK_CONFIG%"

                        echo Activating GCP service account...

                        gcloud auth activate-service-account ^
                            --key-file="%GCP_KEY_FILE%" ^
                            --project="%GCP_PROJECT%"

                        if %ERRORLEVEL% NEQ 0 (
                            echo GCP authentication failed.
                            exit /b 1
                        )

                        echo.
                        echo Getting GKE credentials...

                        gcloud container clusters get-credentials ^
                            %GKE_CLUSTER% ^
                            --location %GKE_LOCATION% ^
                            --project %GCP_PROJECT% ^
                            --verbosity=error

                        if %ERRORLEVEL% NEQ 0 (
                            echo GKE authentication failed.
                            exit /b 1
                        )

                        echo.
                        echo Kubernetes Nodes:

                        kubectl get nodes

                        echo ==========================================
                    '''
                }
            }
        }

        // =========================================================
        // 9. KUBERNETES DEPLOY
        // =========================================================
        stage('Kubernetes Deploy') {
            when {
                expression {
                    return params.DEPLOY_TO_GKE
                }
            }

            steps {

                withCredentials([
                    file(
                        credentialsId: 'gcp-jenkins-cicd',
                        variable: 'GCP_KEY_FILE'
                    )
                ]) {

                    bat '''
                        echo ==========================================
                        echo KUBERNETES DEPLOYMENT
                        echo ==========================================

                        set CLOUDSDK_CONFIG=%WORKSPACE%\\.gcloud-%BUILD_NUMBER%
                        set KUBECONFIG=%WORKSPACE%\\.kubeconfig-%BUILD_NUMBER%

                        if not exist "%CLOUDSDK_CONFIG%" mkdir "%CLOUDSDK_CONFIG%"

                        echo.
                        echo Authenticating with GCP...

                        gcloud auth activate-service-account ^
                            --key-file="%GCP_KEY_FILE%" ^
                            --project="%GCP_PROJECT%"

                        echo.
                        echo Getting GKE credentials...

                        gcloud container clusters get-credentials ^
                            %GKE_CLUSTER% ^
                            --location %GKE_LOCATION% ^
                            --project %GCP_PROJECT% ^
                            --verbosity=error

                        echo.
                        echo Kubernetes Namespace:

                        kubectl apply -f Kubernetes-manifests/namespace.yaml

                        echo.
                        echo Service Account:

                        kubectl apply ^
                            -f Kubernetes-manifests/serviceaccount.yaml ^
                            -n %K8S_NAMESPACE%

                        echo.
                        echo Role:

                        kubectl apply ^
                            -f Kubernetes-manifests/role.yaml ^
                            -n %K8S_NAMESPACE%

                        echo.
                        echo RoleBinding:

                        kubectl apply ^
                            -f Kubernetes-manifests/rolebinding.yaml ^
                            -n %K8S_NAMESPACE%

                        echo.
                        echo ClusterRoleBinding:

                        kubectl apply ^
                            -f Kubernetes-manifests/clusterrolebinding.yaml

                        echo.
                        echo PostgreSQL ConfigMap:

                        kubectl apply ^
                            -f Kubernetes-manifests/postgres-configmap.yaml ^
                            -n %K8S_NAMESPACE%

                        echo.
                        echo PostgreSQL Secret:

                        kubectl apply ^
                            -f Kubernetes-manifests/postgres-secret.yaml ^
                            -n %K8S_NAMESPACE%

                        echo.
                        echo Persistent Volume Claim:

                        kubectl apply ^
                            -f Kubernetes-manifests/persistentvolumeclaim.yaml ^
                            -n %K8S_NAMESPACE%

                        echo.
                        echo PostgreSQL StatefulSet:

                        kubectl apply ^
                            -f Kubernetes-manifests/statefulset.yaml ^
                            -n %K8S_NAMESPACE%

                        echo.
                        echo Headless Service:

                        kubectl apply ^
                            -f Kubernetes-manifests/headless-service.yaml ^
                            -n %K8S_NAMESPACE%

                        echo.
                        echo Application Deployment:

                        kubectl apply ^
                            -f Kubernetes-manifests/deployment.yaml ^
                            -n %K8S_NAMESPACE%

                        echo.
                        echo Application Service:

                        kubectl apply ^
                            -f Kubernetes-manifests/service.yaml ^
                            -n %K8S_NAMESPACE%

                        echo.
                        echo ==========================================
                        echo UPDATING IMAGE
                        echo ==========================================

                        echo Docker Image:
                        echo %DOCKER_IMAGE%:%FINAL_IMAGE_TAG%

                        kubectl set image deployment/%K8S_DEPLOYMENT% ^
                            %APP_NAME%=%DOCKER_IMAGE%:%FINAL_IMAGE_TAG% ^
                            -n %K8S_NAMESPACE%

                        if %ERRORLEVEL% NEQ 0 (
                            echo Failed to update Kubernetes deployment image.
                            exit /b 1
                        )

                        echo.
                        echo Waiting for rollout...

                        kubectl rollout status ^
                            deployment/%K8S_DEPLOYMENT% ^
                            -n %K8S_NAMESPACE% ^
                            --timeout=5m

                        if %ERRORLEVEL% NEQ 0 (
                            echo Kubernetes rollout failed.
                            exit /b 1
                        )

                        echo.
                        echo Kubernetes deployment completed successfully.

                        echo ==========================================
                    '''
                }
            }
        }

        // =========================================================
        // 10. KUBERNETES VERIFY
        // =========================================================
        stage('Kubernetes Verify') {
            when {
                expression {
                    return params.DEPLOY_TO_GKE
                }
            }

            steps {

                withCredentials([
                    file(
                        credentialsId: 'gcp-jenkins-cicd',
                        variable: 'GCP_KEY_FILE'
                    )
                ]) {

                    bat '''
                        echo ==========================================
                        echo KUBERNETES VERIFICATION
                        echo ==========================================

                        set CLOUDSDK_CONFIG=%WORKSPACE%\\.gcloud-%BUILD_NUMBER%
                        set KUBECONFIG=%WORKSPACE%\\.kubeconfig-%BUILD_NUMBER%

                        gcloud auth activate-service-account ^
                            --key-file="%GCP_KEY_FILE%" ^
                            --project="%GCP_PROJECT%"

                        gcloud container clusters get-credentials ^
                            %GKE_CLUSTER% ^
                            --location %GKE_LOCATION% ^
                            --project %GCP_PROJECT% ^
                            --verbosity=error

                        echo.
                        echo ==========================================
                        echo DEPLOYMENT
                        echo ==========================================

                        kubectl get deployment ^
                            %K8S_DEPLOYMENT% ^
                            -n %K8S_NAMESPACE%

                        echo.
                        echo ==========================================
                        echo PODS
                        echo ==========================================

                        kubectl get pods ^
                            -n %K8S_NAMESPACE% ^
                            -o wide

                        echo.
                        echo ==========================================
                        echo SERVICES
                        echo ==========================================

                        kubectl get svc ^
                            -n %K8S_NAMESPACE%

                        echo.
                        echo ==========================================
                        echo PVC
                        echo ==========================================

                        kubectl get pvc ^
                            -n %K8S_NAMESPACE%

                        echo.
                        echo ==========================================
                        echo DEPLOYMENT IMAGE
                        echo ==========================================

                        kubectl get deployment ^
                            %K8S_DEPLOYMENT% ^
                            -n %K8S_NAMESPACE% ^
                            -o jsonpath="{.spec.template.spec.containers[0].image}"

                        echo.

                        echo.
                        echo ==========================================
                        echo ROLLOUT STATUS
                        echo ==========================================

                        kubectl rollout status ^
                            deployment/%K8S_DEPLOYMENT% ^
                            -n %K8S_NAMESPACE% ^
                            --timeout=5m

                        echo.
                        echo ==========================================
                        echo KUBERNETES DEPLOYMENT VERIFIED
                        echo ==========================================
                    '''
                }
            }
        }

        // =========================================================
        // 11. PIPELINE SUMMARY
        // =========================================================
        stage('Pipeline Summary') {
            steps {
                bat '''
                    echo.
                    echo ==================================================
                    echo              PIPELINE SUMMARY
                    echo ==================================================

                    echo.
                    echo Application:
                    echo %APP_NAME%

                    echo.
                    echo Docker Image:
                    echo %DOCKER_IMAGE%:%FINAL_IMAGE_TAG%

                    echo.
                    echo GCP Project:
                    echo %GCP_PROJECT%

                    echo.
                    echo GKE Cluster:
                    echo %GKE_CLUSTER%

                    echo.
                    echo Kubernetes Namespace:
                    echo %K8S_NAMESPACE%

                    echo.
                    echo Kubernetes Deployment:
                    echo %K8S_DEPLOYMENT%

                    echo.
                    echo Build Number:
                    echo %BUILD_NUMBER%

                    echo.
                    echo Pipeline completed successfully.

                    echo ==================================================
                '''
            }
        }
    }

    // =============================================================
    // POST ACTIONS
    // =============================================================
    post {

        success {
            echo '=========================================='
            echo 'PIPELINE SUCCESSFUL'
            echo '=========================================='
            echo "Docker Image: ${env.DOCKER_IMAGE}:${env.FINAL_IMAGE_TAG}"
        }

        failure {
            echo '=========================================='
            echo 'PIPELINE FAILED'
            echo '=========================================='
            echo 'Please check the Jenkins console output.'
        }

        always {
            bat '''
                echo.
                echo Cleaning temporary authentication files...

                if exist "%WORKSPACE%\\.gcloud-%BUILD_NUMBER%" rmdir /s /q "%WORKSPACE%\\.gcloud-%BUILD_NUMBER%"

                if exist "%WORKSPACE%\\.docker-%BUILD_NUMBER%" rmdir /s /q "%WORKSPACE%\\.docker-%BUILD_NUMBER%"

                if exist "%WORKSPACE%\\.kubeconfig-%BUILD_NUMBER%" del /f /q "%WORKSPACE%\\.kubeconfig-%BUILD_NUMBER%"

                if exist "%WORKSPACE%\\.gcp-token-%BUILD_NUMBER%.txt" del /f /q "%WORKSPACE%\\.gcp-token-%BUILD_NUMBER%.txt"

                echo Temporary files cleaned.
            '''

            cleanWs()
        }
    }
}