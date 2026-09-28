```groovy
pipeline {

    agent any

    tools {
        jdk 'JDK-17'
        maven 'Maven-3.9.16'
    }

    environment {
        DOCKER_HOST = 'npipe:////./pipe/docker_engine'
    }

    options {
        skipDefaultCheckout(true)
    }

    stages {

        stage('Checkout') {
            steps {
                bat '''
                    if exist .git rmdir /s /q .git
                    git init
                    git remote add origin https://github.com/Manjunathamanjuu/Employment-Management.git
                    git fetch --depth=1 origin feature/Employment-Management
                    git checkout -f FETCH_HEAD
                '''
            }
        }

        stage('Verify Environment') {
            steps {
                bat 'java -version'
                bat 'mvn -version'
                bat 'docker version'
            }
        }

        stage('Build') {
            steps {
                bat 'mvn clean package -DskipTests'
            }
        }

        stage('Test') {
            steps {
                bat 'mvn test -e'
            }
        }

        stage('Docker Verify') {
            steps {
                bat 'docker version'
                bat 'docker info'
            }
        }
    }

    post {

        success {
            echo 'CI Pipeline completed successfully!'
        }

        failure {
            echo 'CI Pipeline failed. Check the console output.'
        }

        always {
            echo 'Pipeline execution completed.'
        }
    }
}
```
