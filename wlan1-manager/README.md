disables wlan1 (alpha adapater uses 150mA steady state)
when boat is away from LAT/LON in wlan1_manager.yaml
reads current location from /run/boat/current_position.json

sudo cp wlan1_manager.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wlan1_manager.service
sudo systemctl start wlan1_manager.service

journalctl -u wlan1_manager.service -f
