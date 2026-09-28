pipeline {

    agent any

    tools {
        jdk 'JDK-17'
        maven 'Maven-3.9.16'
    }

    // ============================================================
    // GLOBAL OPTIONS
    // ============================================================
    options {
        // Never let a hung build run for hours
        timeout(time: 60, unit: 'MINUTES')

        // Prevents parallel builds (the "@2" workspace) fighting over Docker/ports
        disableConcurrentBuilds()

        buildDiscarder(logRotator(numToKeepStr: '20'))
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

        // ============================================================
        // GOOGLE CLOUD SDK
        // ============================================================
        GCLOUD_HOME = 'C:\\Users\\prajw_626z6xf\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk'

        CLOUDSDK_PYTHON = 'C:\\Users\\prajw_626z6xf\\AppData\\Local\\Google\\Cloud SDK\\google-cloud-sdk\\platform\\bundledpython\\python.exe'

        // ============================================================
        // DOCKER DESKTOP
        // ============================================================
        DOCKER_HOST = 'npipe:////./pipe/docker_engine'

        // ============================================================
        // GKE AUTH PLUGIN
        // ============================================================
        USE_GKE_GCLOUD_AUTH_PLUGIN = 'True'
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
                    echo DOCKER LOCATION:
                    where docker
                    if errorlevel 1 exit /b 1

                    echo.
                    echo DOCKER VERSION:
                    docker --version
                    if errorlevel 1 exit /b 1

                    echo.
                    echo KUBECTL LOCATION:
                    where kubectl
                    if errorlevel 1 exit /b 1

                    echo.
                    echo KUBECTL VERSION:
                    kubectl version --client
                    if errorlevel 1 exit /b 1

                    echo.
                    echo GCLOUD LOCATION:
                    where gcloud
                    if errorlevel 1 exit /b 1

                    echo.
                    echo GCLOUD VERSION:
                    call "%GCLOUD_HOME%\\bin\\gcloud.cmd" --version
                    if errorlevel 1 exit /b 1

                    echo.
                    echo GKE AUTH PLUGIN:
                    where gke-gcloud-auth-plugin
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
            options {
                timeout(time: 10, unit: 'MINUTES')
            }
            steps {

                // -B = batch mode, -ntp = no download progress spam in the log
                bat '''
                    echo ================================
                    echo MAVEN BUILD
                    echo ================================

                    mvn -B -ntp clean package -DskipTests
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
            options {
                // Normal run is ~40s. If it hangs, stop after 10 minutes.
                timeout(time: 10, unit: 'MINUTES')
            }
            environment {
                // Ryuk can keep the mvn process from exiting under the Jenkins
                // service on Windows. Disabled here; containers are removed in
                // the post block below instead.
                TESTCONTAINERS_RYUK_DISABLED = 'true'
            }
            steps {

                bat '''
                    echo ================================
                    echo RUNNING TESTS
                    echo ================================

                    mvn -B -ntp test
                    if errorlevel 1 exit /b 1

                    echo.
                    echo Tests completed successfully.
                '''
            }
            post {
                always {
                    // Remove leftover Testcontainers containers (Ryuk is disabled)
                    bat '''
                        echo CLEANING UP TESTCONTAINERS CONTAINERS
                        for /f %%i in ('docker ps -aq --filter "label=org.testcontainers=true"') do docker rm -f %%i
                        exit /b 0
                    '''
                }
            }
        }


        // ============================================================
        // DOCKER VERIFY
        // ============================================================
        stage('Docker Verify') {
            options {
                timeout(time: 5, unit: 'MINUTES')
            }
            steps {

                bat '''
                    echo ================================
                    echo DOCKER VERIFICATION
                    echo ================================

                    echo.
                    echo DOCKER HOST:
                    echo %DOCKER_HOST%

                    echo.
                    echo DOCKER LOCATION:
                    where docker
                    if errorlevel 1 exit /b 1

                    echo.
                    echo DOCKER VERSION:
                    docker --version
                    if errorlevel 1 exit /b 1

                    echo.
                    echo DOCKER CONTEXT:
                    docker context show
                    if errorlevel 1 exit /b 1

                    echo.
                    echo DOCKER SERVER:
                    docker version
                    if errorlevel 1 exit /b 1

                    echo.
                    echo DOCKER INFO:
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
            options {
                timeout(time: 20, unit: 'MINUTES')
            }
            steps {

                bat '''
                    echo ================================
                    echo DOCKER BUILD
                    echo ================================

                    echo.
                    echo DOCKER HOST:
                    echo %DOCKER_HOST%

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
            options {
                // Push normally takes under a minute. Fail fast instead of hanging.
                timeout(time: 15, unit: 'MINUTES')
            }
            steps {

                withCredentials([
                    file(
                        credentialsId: 'gcp-jenkins-cicd',
                        variable: 'GCP_KEY_FILE'
                    )
                ]) {

                    bat '''
                        echo ================================
                        echo DOCKER PUSH TO GAR
                        echo ================================

                        set CLOUDSDK_CONFIG=%TEMP%\\jenkins-gcloud-%BUILD_NUMBER%
                        set DOCKER_CONFIG=%TEMP%\\jenkins-docker-%BUILD_NUMBER%
                        set ACCESS_TOKEN_FILE=%TEMP%\\jenkins-gcp-token-%BUILD_NUMBER%.txt

                        if not exist "%CLOUDSDK_CONFIG%" mkdir "%CLOUDSDK_CONFIG%"
                        if not exist "%DOCKER_CONFIG%" mkdir "%DOCKER_CONFIG%"

                        echo.
                        echo ================================
                        echo DOCKER HOST
                        echo ================================

                        echo %DOCKER_HOST%


                        echo.
                        echo ================================
                        echo GCLOUD VERSION
                        echo ================================

                        call "%GCLOUD_HOME%\\bin\\gcloud.cmd" --version
                        if errorlevel 1 exit /b 1


                        echo.
                        echo ================================
                        echo AUTHENTICATING JENKINS SERVICE ACCOUNT
                        echo ================================

                        call "%GCLOUD_HOME%\\bin\\gcloud.cmd" auth activate-service-account --key-file="%GCP_KEY_FILE%" --project="%GCP_PROJECT%"
                        if errorlevel 1 exit /b 1


                        echo.
                        echo ================================
                        echo ACTIVE GOOGLE ACCOUNT
                        echo ================================

                        call "%GCLOUD_HOME%\\bin\\gcloud.cmd" auth list
                        if errorlevel 1 exit /b 1


                        echo.
                        echo ================================
                        echo GENERATING SHORT-LIVED ACCESS TOKEN
                        echo ================================

                        call "%GCLOUD_HOME%\\bin\\gcloud.cmd" auth print-access-token > "%ACCESS_TOKEN_FILE%"
                        if errorlevel 1 exit /b 1


                        echo.
                        echo ================================
                        echo DOCKER LOGIN TO ARTIFACT REGISTRY
                        echo ================================

                        docker login %GCP_REGION%-docker.pkg.dev -u oauth2accesstoken --password-stdin < "%ACCESS_TOKEN_FILE%"
                        if errorlevel 1 (
                            del /q "%ACCESS_TOKEN_FILE%"
                            exit /b 1
                        )


                        echo.
                        echo ================================
                        echo REMOVING ACCESS TOKEN FILE
                        echo ================================

                        del /q "%ACCESS_TOKEN_FILE%"


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
        }


        // ============================================================
        // KUBERNETES DEPLOY
        // ============================================================
        stage('Kubernetes Deploy') {
            options {
                timeout(time: 10, unit: 'MINUTES')
            }
            steps {

                withCredentials([
                    file(
                        credentialsId: 'gcp-jenkins-cicd',
                        variable: 'GCP_KEY_FILE'
                    )
                ]) {

                    bat '''
                        echo ================================
                        echo GKE AUTHENTICATION
                        echo ================================

                        set CLOUDSDK_CONFIG=%TEMP%\\jenkins-gcloud-%BUILD_NUMBER%
                        set KUBECONFIG=%TEMP%\\jenkins-kubeconfig-%BUILD_NUMBER%

                        if not exist "%CLOUDSDK_CONFIG%" mkdir "%CLOUDSDK_CONFIG%"


                        echo.
                        echo ================================
                        echo AUTHENTICATING JENKINS SERVICE ACCOUNT
                        echo ================================

                        call "%GCLOUD_HOME%\\bin\\gcloud.cmd" auth activate-service-account --key-file="%GCP_KEY_FILE%" --project="%GCP_PROJECT%"
                        if errorlevel 1 exit /b 1


                        echo.
                        echo ================================
                        echo ACTIVE GOOGLE ACCOUNT
                        echo ================================

                        call "%GCLOUD_HOME%\\bin\\gcloud.cmd" auth list
                        if errorlevel 1 exit /b 1


                        echo.
                        echo ================================
                        echo GCP PROJECT
                        echo ================================

                        call "%GCLOUD_HOME%\\bin\\gcloud.cmd" config get-value project
                        if errorlevel 1 exit /b 1


                        echo.
                        echo ================================
                        echo GETTING GKE CREDENTIALS
                        echo ================================

                        call "%GCLOUD_HOME%\\bin\\gcloud.cmd" container clusters get-credentials %GKE_CLUSTER% --region %GCP_REGION% --project %GCP_PROJECT%
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
                        echo UPDATING DEPLOYMENT IMAGE TO BUILD %IMAGE_TAG%
                        echo ================================

                        kubectl set image deployment/%K8S_DEPLOYMENT% %K8S_DEPLOYMENT%=%IMAGE_NAME%:%IMAGE_TAG% -n %K8S_NAMESPACE%
                        if errorlevel 1 exit /b 1


                        echo.
                        echo ================================
                        echo KUBERNETES DEPLOYMENT APPLIED
                        echo ================================
                    '''
                }
            }
        }


        // ============================================================
        // VERIFY DEPLOYMENT
        // ============================================================
        stage('Verify Deployment') {
            options {
                timeout(time: 10, unit: 'MINUTES')
            }
            steps {

                bat '''
                    echo ================================
                    echo VERIFY KUBERNETES DEPLOYMENT
                    echo ================================

                    rem Same paths as the Kubernetes Deploy stage. CLOUDSDK_CONFIG is needed
                    rem so gke-gcloud-auth-plugin can find the service account login.
                    set CLOUDSDK_CONFIG=%TEMP%\\jenkins-gcloud-%BUILD_NUMBER%
                    set KUBECONFIG=%TEMP%\\jenkins-kubeconfig-%BUILD_NUMBER%

                    echo.
                    echo KUBECONFIG:
                    echo %KUBECONFIG%


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
            echo 'Build -> Test -> Docker Build -> Docker Push -> Kubernetes Deploy -> Verify'
        }

        failure {
            echo '================================'
            echo 'CI/CD PIPELINE FAILED'
            echo '================================'
            echo 'Check the console output for the failed stage.'
        }

        always {
            echo 'Pipeline execution completed.'

            // Remove temporary credentials/config created during this build
            bat '''
                set DOCKER_CONFIG=%TEMP%\\jenkins-docker-%BUILD_NUMBER%
                docker logout %GCP_REGION%-docker.pkg.dev
                if exist "%TEMP%\\jenkins-gcloud-%BUILD_NUMBER%" rmdir /s /q "%TEMP%\\jenkins-gcloud-%BUILD_NUMBER%"
                if exist "%TEMP%\\jenkins-docker-%BUILD_NUMBER%" rmdir /s /q "%TEMP%\\jenkins-docker-%BUILD_NUMBER%"
                if exist "%TEMP%\\jenkins-kubeconfig-%BUILD_NUMBER%" del /q "%TEMP%\\jenkins-kubeconfig-%BUILD_NUMBER%"
                if exist "%TEMP%\\jenkins-gcp-token-%BUILD_NUMBER%.txt" del /q "%TEMP%\\jenkins-gcp-token-%BUILD_NUMBER%.txt"
                exit /b 0
            '''
        }
    }
}