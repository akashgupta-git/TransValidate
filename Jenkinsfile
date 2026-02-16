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
                                            # 1. Force remove the old container by name (if it exists)
                                            echo "Removing old container..."
                                            sudo docker rm -f transvalidate-app || true
                                            
                                            # 2. Remove old image (optional, saves space)
                                            sudo docker rmi transvalidate:v1 || true
                                            
                                            # 3. Clean up old code
                                            rm -rf TransValidate
                                            
                                            # 4. Clone fresh code
                                            echo "Cloning new code..."
                                            git clone https://github.com/akashgupta-git/TransValidate.git
                                            cd TransValidate
                                            
                                            # 5. Build new image
                                            echo "Building Docker image..."
                                            sudo docker build -t transvalidate:v1 .
                                            
                                            # 6. Run new container with a FIXED NAME
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