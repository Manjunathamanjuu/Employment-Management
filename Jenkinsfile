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
        timeout(time: 60, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    environment {

        // ============================================================
        // APPLICATION
        // ============================================================
        APP_NAME = 'employment-management'

        IMAGE_NAME = 'us-central1-docker.pkg.dev/project-7e1069a7-5b78-49e8-9b8/quickstart-docker-repo/employment-management'
        IMAGE_TAG = "${BUILD_NUMBER}"

        // ============================================================
        // GCP
        // ============================================================
        GCP_PROJECT = 'project-7e1069a7-5b78-49e8-9b8'
        GCP_REGION = 'us-central1'

        // ============================================================
        // GKE
        // ============================================================
        GKE_CLUSTER = 'employee-managment-cluster-1'
        GKE_LOCATION = 'us-central1'

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
        DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'

        // ============================================================
        // GKE AUTH PLUGIN
        // ============================================================
        USE_GKE_GCLOUD_AUTH_PLUGIN = 'True'
    }

    stages {

        // ============================================================
        // 1. CHECKOUT
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
        // 2. VERIFY ENVIRONMENT
        // ============================================================
        stage('Verify Environment') {

            steps {

                bat '''
                    echo ================================
                    echo VERIFY ENVIRONMENT
                    echo ================================

                    set PATH=%GCLOUD_HOME%\\bin;%PATH%

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
                    where gke-gcloud-auth-plugin.exe
                    if errorlevel 1 exit /b 1

                    echo.
                    echo GKE AUTH PLUGIN VERSION:
                    "%GCLOUD_HOME%\\bin\\gke-gcloud-auth-plugin.exe" --version
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
        // 3. DOCKER VERIFY
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
                    echo DOCKER CONTEXT LIST:
                    docker context ls
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
                    echo DOCKER CONTAINERS:
                    docker ps
                    if errorlevel 1 exit /b 1

                    echo.
                    echo DOCKER HELLO WORLD TEST:
                    docker run --rm hello-world
                    if errorlevel 1 exit /b 1

                    echo.
                    echo ================================
                    echo DOCKER CONNECTION SUCCESSFUL
                    echo ================================
                '''
            }
        }

        // ============================================================
        // 4. BUILD
        // ============================================================
        stage('Build') {

            options {
                timeout(time: 10, unit: 'MINUTES')
            }

            steps {

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
        // 5. TEST
        // ============================================================
        stage('Test') {

            options {
                timeout(time: 10, unit: 'MINUTES')
            }

            environment {
                TESTCONTAINERS_RYUK_DISABLED = 'true'
            }

            steps {

                bat '''
                    echo ================================
                    echo TESTCONTAINERS DOCKER CHECK
                    echo ================================

                    echo.
                    echo DOCKER HOST:
                    echo %DOCKER_HOST%

                    echo.
                    echo DOCKER VERSION:
                    docker version
                    if errorlevel 1 exit /b 1

                    echo.
                    echo DOCKER INFO:
                    docker info
                    if errorlevel 1 exit /b 1

                    echo.
                    echo DOCKER CONTAINERS:
                    docker ps
                    if errorlevel 1 exit /b 1

                    echo.
                    echo ================================
                    echo RUNNING MAVEN TESTS
                    echo ================================

                    mvn -B -ntp test
                    if errorlevel 1 exit /b 1

                    echo.
                    echo Tests completed successfully.
                '''
            }

            post {

                always {

                    bat '''
                        echo ================================
                        echo CLEANING TESTCONTAINERS
                        echo ================================

                        for /f %%i in ('docker ps -aq --filter "label=org.testcontainers=true"') do docker rm -f %%i

                        exit /b 0
                    '''
                }
            }
        }

        // ============================================================
        // 6. DOCKER BUILD
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

                    echo.
                    echo DOCKER CONTEXT:
                    docker context show
                    if errorlevel 1 exit /b 1

                    echo.
                    echo DOCKER VERSION:
                    docker --version
                    if errorlevel 1 exit /b 1

                    echo.
                    echo BUILDING IMAGE:
                    echo %IMAGE_NAME%:%IMAGE_TAG%

                    echo.
                    echo STARTING DOCKER BUILD:

                    docker build -t %IMAGE_NAME%:%IMAGE_TAG% .
                    if errorlevel 1 exit /b 1

                    echo.
                    echo ================================
                    echo DOCKER IMAGE CREATED
                    echo ================================

                    echo.
                    echo IMAGE DETAILS:
                    docker images %IMAGE_NAME%:%IMAGE_TAG%

                    echo.
                    echo EMPLOYMENT MANAGEMENT IMAGES:
                    docker images | findstr employment-management

                    echo.
                    echo ================================
                    echo DOCKER BUILD SUCCESSFUL
                    echo ================================
                '''
            }
        }

        // ============================================================
        // 7. DOCKER PUSH
        // ============================================================
        stage('Docker Push') {

            options {
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

                        set CLOUDSDK_CONFIG=%WORKSPACE%\\.gcloud-%BUILD_NUMBER%
                        set DOCKER_CONFIG=%WORKSPACE%\\.docker-%BUILD_NUMBER%
                        set ACCESS_TOKEN_FILE=%WORKSPACE%\\.gcp-token-%BUILD_NUMBER%.txt

                        if not exist "%CLOUDSDK_CONFIG%" mkdir "%CLOUDSDK_CONFIG%"
                        if not exist "%DOCKER_CONFIG%" mkdir "%DOCKER_CONFIG%"

                        set PATH=%GCLOUD_HOME%\\bin;%PATH%

                        echo.
                        echo ================================
                        echo DOCKER HOST
                        echo ================================

                        echo %DOCKER_HOST%

                        echo.
                        echo ================================
                        echo DOCKER VERSION
                        echo ================================

                        docker version
                        if errorlevel 1 exit /b 1

                        echo.
                        echo ================================
                        echo DOCKER INFO
                        echo ================================

                        docker info
                        if errorlevel 1 exit /b 1

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
                        if errorlevel 1 (
                            if exist "%ACCESS_TOKEN_FILE%" del /q "%ACCESS_TOKEN_FILE%"
                            exit /b 1
                        )

                        echo.
                        echo ================================
                        echo DOCKER LOGIN TO ARTIFACT REGISTRY
                        echo ================================

                        docker login %GCP_REGION%-docker.pkg.dev -u oauth2accesstoken --password-stdin < "%ACCESS_TOKEN_FILE%"
                        if errorlevel 1 (
                            if exist "%ACCESS_TOKEN_FILE%" del /q "%ACCESS_TOKEN_FILE%"
                            exit /b 1
                        )

                        echo.
                        echo ================================
                        echo REMOVING ACCESS TOKEN FILE
                        echo ================================

                        if exist "%ACCESS_TOKEN_FILE%" del /q "%ACCESS_TOKEN_FILE%"

                        echo.
                        echo ================================
                        echo LOCAL IMAGE
                        echo ================================

                        docker images %IMAGE_NAME%:%IMAGE_TAG%

                        echo.
                        echo ================================
                        echo PUSHING BUILD TAG
                        echo ================================

                        echo IMAGE:
                        echo %IMAGE_NAME%:%IMAGE_TAG%

                        docker push %IMAGE_NAME%:%IMAGE_TAG%
                        if errorlevel 1 exit /b 1

                        echo.
                        echo ================================
                        echo VERIFYING IMAGE IN GAR
                        echo ================================

                        call "%GCLOUD_HOME%\\bin\\gcloud.cmd" artifacts docker images list "%IMAGE_NAME%" --include-tags --project="%GCP_PROJECT%" --format="table(package,version,tags)"
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
        // 8. KUBERNETES DEPLOY
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

                        set PATH=%GCLOUD_HOME%\\bin;%PATH%

                        set CLOUDSDK_CONFIG=%WORKSPACE%\\.gcloud-%BUILD_NUMBER%
                        set KUBECONFIG=%WORKSPACE%\\.kubeconfig-%BUILD_NUMBER%

                        if not exist "%CLOUDSDK_CONFIG%" mkdir "%CLOUDSDK_CONFIG%"

                        echo.
                        echo ================================
                        echo CLOUDSDK CONFIG
                        echo ================================

                        echo %CLOUDSDK_CONFIG%

                        echo.
                        echo ================================
                        echo KUBECONFIG
                        echo ================================

                        echo %KUBECONFIG%

                        echo.
                        echo ================================
                        echo GKE CLUSTER
                        echo ================================

                        echo %GKE_CLUSTER%

                        echo.
                        echo ================================
                        echo GKE LOCATION
                        echo ================================

                        echo %GKE_LOCATION%

                        echo.
                        echo ================================
                        echo GKE AUTH PLUGIN
                        echo ================================

                        where gke-gcloud-auth-plugin.exe
                        if errorlevel 1 exit /b 1

                        "%GCLOUD_HOME%\\bin\\gke-gcloud-auth-plugin.exe" --version
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
                        echo GCP PROJECT
                        echo ================================

                        call "%GCLOUD_HOME%\\bin\\gcloud.cmd" config get-value project
                        if errorlevel 1 exit /b 1

                        echo.
                        echo ================================
                        echo GETTING GKE CREDENTIALS
                        echo ================================

                        call "%GCLOUD_HOME%\\bin\\gcloud.cmd" container clusters get-credentials %GKE_CLUSTER% --location %GKE_LOCATION% --project %GCP_PROJECT% --verbosity=info
                        if errorlevel 1 exit /b 1

                        echo.
                        echo ================================
                        echo KUBECONFIG CREATED
                        echo ================================

                        if not exist "%KUBECONFIG%" (
                            echo ERROR: Kubeconfig file was not created.
                            exit /b 1
                        )

                        echo Kubeconfig file created successfully.

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
                        echo UPDATING DEPLOYMENT IMAGE
                        echo ================================

                        echo IMAGE:
                        echo %IMAGE_NAME%:%IMAGE_TAG%

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
        // 9. VERIFY DEPLOYMENT
        // ============================================================
        stage('Verify Deployment') {

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
                        echo VERIFY KUBERNETES DEPLOYMENT
                        echo ================================

                        set PATH=%GCLOUD_HOME%\\bin;%PATH%

                        set CLOUDSDK_CONFIG=%WORKSPACE%\\.gcloud-%BUILD_NUMBER%
                        set KUBECONFIG=%WORKSPACE%\\.kubeconfig-%BUILD_NUMBER%

                        echo.
                        echo CLOUDSDK CONFIG:
                        echo %CLOUDSDK_CONFIG%

                        echo.
                        echo KUBECONFIG:
                        echo %KUBECONFIG%

                        if not exist "%KUBECONFIG%" (
                            echo ERROR: Kubeconfig file does not exist.
                            exit /b 1
                        )

                        echo.
                        echo ================================
                        echo PODS
                        echo ================================

                        kubectl get pods -n %K8S_NAMESPACE%
                        if errorlevel 1 exit /b 1

                        echo.
                        echo ================================
                        echo SERVICES
                        echo ================================

                        kubectl get svc -n %K8S_NAMESPACE%
                        if errorlevel 1 exit /b 1

                        echo.
                        echo ================================
                        echo DEPLOYMENT
                        echo ================================

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

            bat '''
                echo.
                echo ================================
                echo CLEANING JENKINS TEMP CONFIG
                echo ================================

                docker logout %GCP_REGION%-docker.pkg.dev

                if exist "%WORKSPACE%\\.gcloud-%BUILD_NUMBER%" rmdir /s /q "%WORKSPACE%\\.gcloud-%BUILD_NUMBER%"
                if exist "%WORKSPACE%\\.docker-%BUILD_NUMBER%" rmdir /s /q "%WORKSPACE%\\.docker-%BUILD_NUMBER%"
                if exist "%WORKSPACE%\\.kubeconfig-%BUILD_NUMBER%" del /q "%WORKSPACE%\\.kubeconfig-%BUILD_NUMBER%"
                if exist "%WORKSPACE%\\.gcp-token-%BUILD_NUMBER%.txt" del /q "%WORKSPACE%\\.gcp-token-%BUILD_NUMBER%.txt"

                exit /b 0
            '''
        }
    }
}