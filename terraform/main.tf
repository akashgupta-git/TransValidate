provider "aws" {
  region = "ap-south-1"
}

# This automatically fetches the latest Ubuntu 22.04 AMI ID for Mumbai
data "aws_ami" "ubuntu" {
  most_recent = true

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }

  owners = ["099720109477"] # Canonical (Owners of Ubuntu)
}

# 1. Create a VPC
resource "aws_vpc" "main_vpc" {
  cidr_block = "10.0.0.0/16"
  tags = {
    Name = "TransValidate-VPC"
  }
}

# 2. Create a Subnet
resource "aws_subnet" "main_subnet" {
  vpc_id            = aws_vpc.main_vpc.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "ap-south-1a"
  map_public_ip_on_launch = true

  tags = {
    Name = "TransValidate-Subnet"
  }
}

# 3. Internet Gateway
resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main_vpc.id
}

# 4. Route Table
resource "aws_route_table" "rt" {
  vpc_id = aws_vpc.main_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }
}

resource "aws_route_table_association" "a" {
  subnet_id      = aws_subnet.main_subnet.id
  route_table_id = aws_route_table.rt.id
}

# 5. Security Group
resource "aws_security_group" "allow_web" {
  name        = "allow_web_traffic"
  description = "Allow Web and SSH inbound traffic"
  vpc_id      = aws_vpc.main_vpc.id

  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH from anywhere"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  ingress {
    description = "Flask App Custom Port"
    from_port   = 5002
    to_port     = 5002
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 6. The Server (EC2 Instance)
resource "aws_instance" "app_server" {
  ami           = data.aws_ami.ubuntu.id 
  instance_type = "t2.micro"
  subnet_id     = aws_subnet.main_subnet.id
  vpc_security_group_ids = [aws_security_group.allow_web.id]
  key_name = "transvalidate-key"

  user_data = <<-EOF
              #!/bin/bash
              sudo apt update -y
              sudo apt install docker.io git -y
              sudo systemctl start docker
              sudo systemctl enable docker
              
              # Clone your code
              git clone https://github.com/akashgupta-git/TransValidate.git /home/ubuntu/app
              cd /home/ubuntu/app
              
              # Build the image on the server
              sudo docker build -t transvalidate:v1 .
              
              # Run it (Mapping Port 80 on server -> Port 5002 in container)
              sudo docker run -d -p 80:5002 transvalidate:v1
              EOF

  tags = {
    Name = "TransValidate-Server"
  }
}