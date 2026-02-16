output "public_ip" {
  value = aws_instance.web.public_ip
}

output "jenkins_reminder" {
  value = "REMINDER: Update Jenkins SSH Hostname to ${aws_instance.web.public_ip}"
}