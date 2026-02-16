pipeline {
    agent any

    stages {
        stage('Deploy to AWS') {
            steps {
                script {
                    echo 'Deploying to AWS EC2...'
                    sshPublisher(
                        publishers: [
                            sshPublisherDesc(
                                configName: 'AWS-EC2', // MUST match the name in Manage Jenkins -> System
                                transfers: [
                                    sshTransfer(
                                        cleanRemote: false,
                                        remoteDirectory: '',
                                        execCommand: '''
                                            # 1. Stop existing container
                                            echo "Stopping old container..."
                                            sudo docker stop $(sudo docker ps -q --filter ancestor=transvalidate:v1) || true
                                            
                                            # 2. Remove stopped container
                                            echo "Removing old container..."
                                            sudo docker rm $(sudo docker ps -aq --filter ancestor=transvalidate:v1) || true
                                            
                                            # 3. Remove old image to free space
                                            echo "Removing old image..."
                                            sudo docker rmi transvalidate:v1 || true
                                            
                                            # 4. Remove old code folder
                                            rm -rf TransValidate
                                            
                                            # 5. Clone fresh code
                                            echo "Cloning new code..."
                                            git clone https://github.com/akashgupta-git/TransValidate.git
                                            cd TransValidate
                                            
                                            # 6. Build new image
                                            echo "Building Docker image..."
                                            sudo docker build -t transvalidate:v1 .
                                            
                                            # 7. Run new container
                                            echo "Starting new container..."
                                            sudo docker run -d -p 80:5002 transvalidate:v1
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