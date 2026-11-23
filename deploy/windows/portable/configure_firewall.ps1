# Allows the OFFLINE SHARE port ONLY from the approved LAN subnet. Run as Administrator.
param([int]$Port = 5000, [string]$Subnet = "192.168.50.0/24")
$name = "OFFLINE SHARE (TCP $Port, LAN only)"
Get-NetFirewallRule -DisplayName "OFFLINE SHARE*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port `
  -RemoteAddress $Subnet -Profile Any -Description "OFFLINE SHARE LAN data transfer server" | Out-Null
Write-Host "Firewall rule created: $name (remote $Subnet)"
