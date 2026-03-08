output "public_ip" {
  value = aws_instance.app_server.public_ip
}

output "app_url" {
  value = "http://${aws_instance.app_server.public_ip}"
}

output "jenkins_reminder" {
  value = "REMINDER: Update Jenkins SSH Hostname to ${aws_instance.app_server.public_ip}"
}