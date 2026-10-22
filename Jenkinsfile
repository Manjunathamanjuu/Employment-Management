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
            name: 'DEPLOY_TO_EKS',
            defaultValue: true,
            description: 'Deploy application to AWS EKS'
        )
    }

    environment {

        // =========================================================
        // APPLICATION
        // =========================================================

        APP_NAME = 'employment-management'

        // =========================================================
        // AWS
        // =========================================================

        AWS_REGION = 'ap-south-1'

        EKS_CLUSTER = 'employment-management-eks'

        ECR_REPOSITORY = 'employment-management'

        // ECR registry
        ECR_REGISTRY = 'YOUR_AWS_ACCOUNT_ID.dkr.ecr.ap-south-1.amazonaws.com'

        // Complete ECR image
        ECR_IMAGE = "${ECR_REGISTRY}/${ECR_REPOSITORY}"

        // =========================================================
        // KUBERNETES
        // =========================================================

        K8S_NAMESPACE = 'stateful-demo'

        K8S_DEPLOYMENT = 'employment-management'

        // =========================================================
        // DOCKER DESKTOP
        // =========================================================

        DOCKER_HOST = 'npipe:////./pipe/dockerDesktopLinuxEngine'

        DOCKER_API_VERSION = '1.44'
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
                    echo AWS CLI Version:
                    aws --version

                    echo.
                    echo Helm Version:
                    helm version

                    echo.
                    echo Docker Host:
                    echo %DOCKER_HOST%

                    echo.
                    echo Docker API Version:
                    echo %DOCKER_API_VERSION%

                    echo.
                    echo AWS Region:
                    echo %AWS_REGION%

                    echo.
                    echo EKS Cluster:
                    echo %EKS_CLUSTER%

                    echo.
                    echo ECR Image:
                    echo %ECR_IMAGE%

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

                    branches: [[
                        name: "*/${params.BRANCH}"
                    ]],

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

                    echo.
                    echo Docker API Version:
                    echo %DOCKER_API_VERSION%

                    echo.
                    echo Docker Version:
                    docker version

                    echo.
                    echo Docker Info:
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

                    if %ERRORLEVEL% NEQ 0 (

                        echo.
                        echo ==========================================
                        echo MAVEN BUILD FAILED
                        echo ==========================================

                        exit /b 1
                    )

                    echo.
                    echo Maven build completed successfully.

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

                    echo.
                    echo Testcontainers Docker configuration:

                    if exist "src\\test\\resources\\docker-java.properties" (

                        type "src\\test\\resources\\docker-java.properties"

                    ) else (

                        echo WARNING: docker-java.properties not found.

                    )

                    echo.
                    echo Docker Host:
                    echo %DOCKER_HOST%

                    echo.
                    echo Docker API Version:
                    echo %DOCKER_API_VERSION%

                    echo.
                    echo Configuring Testcontainers Docker API...

                    set "DOCKER_API_VERSION=1.44"

                    set "MAVEN_OPTS=-Dapi.version=1.44"

                    echo.
                    echo DOCKER_API_VERSION:
                    echo %DOCKER_API_VERSION%

                    echo.
                    echo MAVEN_OPTS:
                    echo %MAVEN_OPTS%

                    echo.
                    echo Disabling Testcontainers Ryuk...

                    set "TESTCONTAINERS_RYUK_DISABLED=true"

                    echo.
                    echo TESTCONTAINERS_RYUK_DISABLED:
                    echo %TESTCONTAINERS_RYUK_DISABLED%

                    echo.
                    echo Running Maven tests...

                    mvn -B -ntp test

                    if %ERRORLEVEL% NEQ 0 (

                        echo.
                        echo ==========================================
                        echo MAVEN TEST FAILED
                        echo ==========================================

                        echo.
                        echo Docker containers:

                        docker ps -a

                        echo.
                        echo Testcontainers containers:

                        docker ps -a --filter "label=org.testcontainers=true"

                        exit /b 1
                    )

                    echo.
                    echo Maven tests completed successfully.

                    echo.
                    echo Cleaning Testcontainers...

                    for /f %%i in ('docker ps -aq --filter "label=org.testcontainers=true"') do (

                        docker rm -f %%i

                    )

                    echo.
                    echo ==========================================
                    echo MAVEN TEST SUCCESSFUL
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

                    echo.
                    echo Docker Image:
                    echo %ECR_IMAGE%:%FINAL_IMAGE_TAG%

                    echo.
                    echo Building Docker image...

                    docker build ^
                        -t %ECR_IMAGE%:%FINAL_IMAGE_TAG% ^
                        -t %ECR_IMAGE%:latest .

                    if %ERRORLEVEL% NEQ 0 (

                        echo Docker build failed.

                        exit /b 1

                    )

                    echo.
                    echo Docker image build successful.

                    echo.
                    echo Docker Images:

                    docker images %ECR_IMAGE%

                    echo ==========================================

                '''
            }
        }


        // =========================================================
        // 7. AWS ECR LOGIN + PUSH
        // =========================================================

        stage('AWS ECR Push') {

            steps {

                withCredentials([

                    [
                        $class: 'AmazonWebServicesCredentialsBinding',

                        credentialsId: 'aws-jenkins-cicd',

                        accessKeyVariable: 'AWS_ACCESS_KEY_ID',

                        secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'
                    ]

                ]) {

                    bat '''

                        echo ==========================================
                        echo AWS ECR LOGIN
                        echo ==========================================

                        echo.
                        echo AWS Region:
                        echo %AWS_REGION%

                        echo.
                        echo Logging into Amazon ECR...

                        aws ecr get-login-password ^
                            --region %AWS_REGION% ^
                            | docker login ^
                            --username AWS ^
                            --password-stdin %ECR_REGISTRY%

                        if %ERRORLEVEL% NEQ 0 (

                            echo AWS ECR login failed.

                            exit /b 1

                        )

                        echo.
                        echo ECR login successful.

                        echo.
                        echo ==========================================
                        echo PUSHING DOCKER IMAGE TO ECR
                        echo ==========================================

                        echo.
                        echo Pushing:
                        echo %ECR_IMAGE%:%FINAL_IMAGE_TAG%

                        docker push %ECR_IMAGE%:%FINAL_IMAGE_TAG%

                        if %ERRORLEVEL% NEQ 0 (

                            echo Docker image push failed.

                            exit /b 1

                        )

                        echo.
                        echo Pushing latest tag...

                        docker push %ECR_IMAGE%:latest

                        if %ERRORLEVEL% NEQ 0 (

                            echo Docker latest image push failed.

                            exit /b 1

                        )

                        echo.
                        echo Docker image pushed successfully to AWS ECR.

                        echo ==========================================

                    '''
                }
            }
        }


        // =========================================================
        // 8. AWS EKS AUTHENTICATION
        // =========================================================

        stage('EKS Authentication') {

            when {

                expression {

                    return params.DEPLOY_TO_EKS

                }
            }

            steps {

                withCredentials([

                    [
                        $class: 'AmazonWebServicesCredentialsBinding',

                        credentialsId: 'aws-jenkins-cicd',

                        accessKeyVariable: 'AWS_ACCESS_KEY_ID',

                        secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'
                    ]

                ]) {

                    bat '''

                        echo ==========================================
                        echo AWS EKS AUTHENTICATION
                        echo ==========================================

                        echo.
                        echo AWS Region:
                        echo %AWS_REGION%

                        echo.
                        echo EKS Cluster:
                        echo %EKS_CLUSTER%

                        echo.
                        echo Checking AWS identity...

                        aws sts get-caller-identity

                        if %ERRORLEVEL% NEQ 0 (

                            echo AWS authentication failed.

                            exit /b 1

                        )

                        echo.
                        echo Getting EKS credentials...

                        aws eks update-kubeconfig ^
                            --region %AWS_REGION% ^
                            --name %EKS_CLUSTER%

                        if %ERRORLEVEL% NEQ 0 (

                            echo EKS authentication failed.

                            exit /b 1

                        )

                        echo.
                        echo Kubernetes Nodes:

                        kubectl get nodes

                        if %ERRORLEVEL% NEQ 0 (

                            echo Kubernetes connection failed.

                            exit /b 1

                        )

                        echo.
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

                    return params.DEPLOY_TO_EKS

                }
            }

            steps {

                withCredentials([

                    [
                        $class: 'AmazonWebServicesCredentialsBinding',

                        credentialsId: 'aws-jenkins-cicd',

                        accessKeyVariable: 'AWS_ACCESS_KEY_ID',

                        secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'
                    ]

                ]) {

                    bat '''

                        echo ==========================================
                        echo KUBERNETES DEPLOYMENT
                        echo ==========================================

                        echo.
                        echo Getting EKS credentials...

                        aws eks update-kubeconfig ^
                            --region %AWS_REGION% ^
                            --name %EKS_CLUSTER%

                        if %ERRORLEVEL% NEQ 0 (

                            echo Failed to get EKS credentials.

                            exit /b 1

                        )


                        echo.
                        echo ==========================================
                        echo KUBERNETES NAMESPACE
                        echo ==========================================

                        kubectl apply ^
                            -f Kubernetes-manifests/namespace.yaml

                        if %ERRORLEVEL% NEQ 0 exit /b 1


                        echo.
                        echo ==========================================
                        echo SERVICE ACCOUNT
                        echo ==========================================

                        kubectl apply ^
                            -f Kubernetes-manifests/serviceaccount.yaml ^
                            -n %K8S_NAMESPACE%

                        if %ERRORLEVEL% NEQ 0 exit /b 1


                        echo.
                        echo ==========================================
                        echo ROLE
                        echo ==========================================

                        kubectl apply ^
                            -f Kubernetes-manifests/role.yaml ^
                            -n %K8S_NAMESPACE%

                        if %ERRORLEVEL% NEQ 0 exit /b 1


                        echo.
                        echo ==========================================
                        echo ROLE BINDING
                        echo ==========================================

                        kubectl apply ^
                            -f Kubernetes-manifests/rolebinding.yaml ^
                            -n %K8S_NAMESPACE%

                        if %ERRORLEVEL% NEQ 0 exit /b 1


                        echo.
                        echo ==========================================
                        echo CLUSTER ROLE BINDING
                        echo ==========================================

                        kubectl apply ^
                            -f Kubernetes-manifests/clusterrolebinding.yaml

                        if %ERRORLEVEL% NEQ 0 exit /b 1


                        echo.
                        echo ==========================================
                        echo POSTGRESQL CONFIGMAP
                        echo ==========================================

                        kubectl apply ^
                            -f Kubernetes-manifests/postgres-configmap.yaml ^
                            -n %K8S_NAMESPACE%

                        if %ERRORLEVEL% NEQ 0 exit /b 1


                        echo.
                        echo ==========================================
                        echo POSTGRESQL SECRET
                        echo ==========================================

                        kubectl apply ^
                            -f Kubernetes-manifests/postgres-secret.yaml ^
                            -n %K8S_NAMESPACE%

                        if %ERRORLEVEL% NEQ 0 exit /b 1


                        echo.
                        echo ==========================================
                        echo PERSISTENT VOLUME CLAIM
                        echo ==========================================

                        kubectl apply ^
                            -f Kubernetes-manifests/persistentvolumeclaim.yaml ^
                            -n %K8S_NAMESPACE%

                        if %ERRORLEVEL% NEQ 0 exit /b 1


                        echo.
                        echo ==========================================
                        echo POSTGRESQL STATEFULSET
                        echo ==========================================

                        kubectl apply ^
                            -f Kubernetes-manifests/statefulset.yaml ^
                            -n %K8S_NAMESPACE%

                        if %ERRORLEVEL% NEQ 0 exit /b 1


                        echo.
                        echo ==========================================
                        echo HEADLESS SERVICE
                        echo ==========================================

                        kubectl apply ^
                            -f Kubernetes-manifests/headless-service.yaml ^
                            -n %K8S_NAMESPACE%

                        if %ERRORLEVEL% NEQ 0 exit /b 1


                        echo.
                        echo ==========================================
                        echo APPLICATION DEPLOYMENT
                        echo ==========================================

                        kubectl apply ^
                            -f Kubernetes-manifests/deployment.yaml ^
                            -n %K8S_NAMESPACE%

                        if %ERRORLEVEL% NEQ 0 exit /b 1


                        echo.
                        echo ==========================================
                        echo APPLICATION SERVICE
                        echo ==========================================

                        kubectl apply ^
                            -f Kubernetes-manifests/service.yaml ^
                            -n %K8S_NAMESPACE%

                        if %ERRORLEVEL% NEQ 0 exit /b 1


                        echo.
                        echo ==========================================
                        echo UPDATING APPLICATION IMAGE
                        echo ==========================================

                        echo Docker Image:
                        echo %ECR_IMAGE%:%FINAL_IMAGE_TAG%

                        kubectl set image deployment/%K8S_DEPLOYMENT% ^
                            %APP_NAME%=%ECR_IMAGE%:%FINAL_IMAGE_TAG% ^
                            -n %K8S_NAMESPACE%

                        if %ERRORLEVEL% NEQ 0 (

                            echo Failed to update Kubernetes deployment image.

                            exit /b 1

                        )


                        echo.
                        echo ==========================================
                        echo WAITING FOR ROLLOUT
                        echo ==========================================

                        kubectl rollout status ^
                            deployment/%K8S_DEPLOYMENT% ^
                            -n %K8S_NAMESPACE% ^
                            --timeout=5m

                        if %ERRORLEVEL% NEQ 0 (

                            echo Kubernetes rollout failed.

                            echo.
                            echo Deployment status:

                            kubectl get deployment ^
                                %K8S_DEPLOYMENT% ^
                                -n %K8S_NAMESPACE%

                            echo.
                            echo Pods:

                            kubectl get pods ^
                                -n %K8S_NAMESPACE% ^
                                -o wide

                            echo.
                            echo Pod descriptions:

                            kubectl describe pods ^
                                -n %K8S_NAMESPACE%

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

                    return params.DEPLOY_TO_EKS

                }
            }

            steps {

                withCredentials([

                    [
                        $class: 'AmazonWebServicesCredentialsBinding',

                        credentialsId: 'aws-jenkins-cicd',

                        accessKeyVariable: 'AWS_ACCESS_KEY_ID',

                        secretKeyVariable: 'AWS_SECRET_ACCESS_KEY'
                    ]

                ]) {

                    bat '''

                        echo ==========================================
                        echo KUBERNETES VERIFICATION
                        echo ==========================================

                        echo.
                        echo Getting EKS credentials...

                        aws eks update-kubeconfig ^
                            --region %AWS_REGION% ^
                            --name %EKS_CLUSTER%

                        if %ERRORLEVEL% NEQ 0 exit /b 1


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

                        if %ERRORLEVEL% NEQ 0 (

                            echo Rollout verification failed.

                            exit /b 1

                        )


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
                    echo AWS Region:
                    echo %AWS_REGION%

                    echo.
                    echo ECR Image:
                    echo %ECR_IMAGE%:%FINAL_IMAGE_TAG%

                    echo.
                    echo EKS Cluster:
                    echo %EKS_CLUSTER%

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

            echo "ECR Image: ${env.ECR_IMAGE}:${env.FINAL_IMAGE_TAG}"

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
                echo Cleaning temporary files...

                if exist "%WORKSPACE%\\.kubeconfig-%BUILD_NUMBER%" del /f /q "%WORKSPACE%\\.kubeconfig-%BUILD_NUMBER%"

                echo Temporary files cleaned.

            '''

            cleanWs()
        }
    }
}