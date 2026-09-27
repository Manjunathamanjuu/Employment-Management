pipeline {

    agent any

    tools {
        jdk 'JDK-17'
        maven 'Maven-3.9.16'
    }

    options {
        skipDefaultCheckout(true)
    }

    stages {

        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Verify Environment') {
            steps {
                bat 'java -version'
                bat 'mvn -version'
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


