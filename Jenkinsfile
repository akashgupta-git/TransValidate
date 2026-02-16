pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Deploy to AWS') {
            steps {
                script {
                    echo 'Deploying to AWS EC2...'
                    sshPublisher(
                        publishers: [
                            sshPublisherDesc(
                                configName: 'AWS-EC2',
                                transfers: [
                                    sshTransfer(
                                        cleanRemote: false,
                                        remoteDirectory: '',
                                        execCommand: '''
                                            # 1. NUKE OPTION: Stop and Remove ALL containers to free Port 80
                                            echo "Clearing all running containers..."
                                            sudo docker stop $(sudo docker ps -aq) || true
                                            sudo docker rm -f $(sudo docker ps -aq) || true
                                            
                                            # 2. Remove old images to save space
                                            sudo docker rmi transvalidate:v1 || true
                                            sudo docker system prune -f || true
                                            
                                            # 3. Clean old code
                                            rm -rf TransValidate
                                            
                                            # 4. Clone fresh code
                                            echo "Cloning new code..."
                                            git clone https://github.com/akashgupta-git/TransValidate.git
                                            cd TransValidate
                                            
                                            # 5. Build
                                            echo "Building Docker image..."
                                            sudo docker build -t transvalidate:v1 .
                                            
                                            # 6. Run with Static Name
                                            echo "Starting new container..."
                                            sudo docker run -d --name transvalidate-app -p 80:5002 transvalidate:v1
                                        '''
                                    )
                                ],
                                usePromotionTimestamp: false,
                                useWorkspaceInPromotion: false,
                                verbose: true
                            )
                        ]
                    )
                }
            }
        }
    }
}