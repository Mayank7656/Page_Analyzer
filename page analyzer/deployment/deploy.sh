#!/bin/bash

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install required packages
sudo apt-get install -y python3-pip python3-venv nginx apache2-utils

# Create application directory
sudo mkdir -p /var/www/ai_analytics
sudo chown -R www-data:www-data /var/www/ai_analytics

# Create and activate virtual environment
python3 -m venv /var/www/ai_analytics/venv
source /var/www/ai_analytics/venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
pip install gunicorn

# Copy application files
sudo cp -r * /var/www/ai_analytics/
sudo chown -R www-data:www-data /var/www/ai_analytics

# Setup systemd service
sudo cp ai_analytics.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start ai_analytics
sudo systemctl enable ai_analytics

# Setup Nginx
sudo cp nginx.conf /etc/nginx/sites-available/ai_analytics
sudo ln -s /etc/nginx/sites-available/ai_analytics /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo systemctl restart nginx

# Setup Apache
sudo a2enmod rewrite headers
sudo cp .htaccess /var/www/ai_analytics/
sudo systemctl restart apache2

# Create uploads directory
sudo mkdir -p /var/www/ai_analytics/uploads
sudo chown -R www-data:www-data /var/www/ai_analytics/uploads

echo "Deployment completed successfully!" 