#!/bin/bash

# Configuration variables
AP_INTERFACE="wlan0"  # Change to "wlan1" if using ALFA adapter
INET_INTERFACE="wlan1"  # Change to "eth0" if using a wired connection

source "$(dirname "$0")/ap_secrets.env"

# FLAG: Set to 1 to tell devices (e.g., iPhones) that this AP has no internet.
# This makes phones automatically switch to cellular for internet.
# Set to 0 to ENABLE internet sharing from wlan1 or eth0.
NO_INTERNET=1

echo "Setting up Access Point on $AP_INTERFACE..."

# Stop services before making changes
sudo systemctl stop hostapd dnsmasq

# Set static IP for AP interface
echo "Configuring static IP for $AP_INTERFACE..."
sudo tee /etc/dhcpcd.conf > /dev/null <<EOF
interface $AP_INTERFACE
static ip_address=192.168.4.1/24
nohook wpa_supplicant
denyinterfaces wlan1  # Prevent dhcpcd from interfering with wlan1 (internet)
EOF

# Restart DHCP client to apply static IP
sudo systemctl restart dhcpcd

# Configure dnsmasq (DHCP server) for client connectivity
echo "Configuring DHCP settings..."
if [ "$NO_INTERNET" -eq 1 ]; then
    echo "NO_INTERNET mode: Clients will not use this AP for internet."
    sudo tee /etc/dnsmasq.conf > /dev/null <<EOF
interface=$AP_INTERFACE
dhcp-range=192.168.4.10,192.168.4.100,255.255.255.0,24h
dhcp-option=3,192.168.4.1  # Allows clients to route to the Pi but NOT to the internet
dhcp-option=6,192.168.4.1  # Uses the Pi as a DNS resolver (no external DNS)
# address=/#/192.168.4.1  # Redirect all DNS queries to the Pi CAPTIVE PORTAL, CAREFUL CAUSES PROBLEMS
EOF
else
    echo "Internet-sharing mode: Clients will use this AP for internet."
    sudo tee /etc/dnsmasq.conf > /dev/null <<EOF
interface=$AP_INTERFACE
dhcp-range=192.168.4.10,192.168.4.100,255.255.255.0,24h
dhcp-option=3,192.168.4.1  # Sets the Pi as the default gateway
dhcp-option=6,8.8.8.8,8.8.4.4  # Use Google's public DNS for external internet access
EOF
fi

# Restart dnsmasq to apply DHCP settings
sudo systemctl restart dnsmasq

# Configure hostapd (WiFi AP) for broadcasting the SSID
echo "Configuring hostapd (WiFi AP)..."
sudo tee /etc/hostapd/hostapd.conf > /dev/null <<EOF
interface=$AP_INTERFACE
ssid=$SSID
hw_mode=g
channel=6
wmm_enabled=0
auth_algs=1
wpa=2
wpa_passphrase=$PASSWORD
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF

# Ensure hostapd uses the correct configuration file
sudo sed -i "s|#DAEMON_CONF=\"\"|DAEMON_CONF=\"/etc/hostapd/hostapd.conf\"|g" /etc/default/hostapd

# Start and enable AP services
echo "Starting AP services..."
sudo systemctl unmask hostapd
sudo systemctl enable hostapd dnsmasq
sudo systemctl restart hostapd dnsmasq

# Disable power saving for stable AP performance
echo "Disabling power saving on $AP_INTERFACE..."
sudo iw dev $AP_INTERFACE set power_save off

# Enable internet sharing if NO_INTERNET=0
if [ "$NO_INTERNET" -eq 0 ]; then
    echo "Enabling internet sharing..."
    sudo sysctl -w net.ipv4.ip_forward=1
    sudo iptables -t nat -A POSTROUTING -o $INET_INTERFACE -j MASQUERADE
    sudo iptables -A FORWARD -i $INET_INTERFACE -o $AP_INTERFACE -m state --state RELATED,ESTABLISHED -j ACCEPT
    sudo iptables -A FORWARD -i $AP_INTERFACE -o $INET_INTERFACE -j ACCEPT

    # Make routing changes permanent
    sudo sh -c "echo 'net.ipv4.ip_forward=1' >> /etc/sysctl.conf"
    sudo sh -c "iptables-save > /etc/iptables/rules.v4"
fi

# Allow inbound HTTP & FastAPI traffic from `wlan0`
sudo iptables -A INPUT -i wlan0 -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -i wlan0 -p tcp --dport 8080 -j ACCEPT

# Save iptables rules permanently
sudo netfilter-persistent save

echo "Access Point setup complete on $AP_INTERFACE. SSID: $SSID"
