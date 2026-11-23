# Prints "<ip> <network>/<prefix>" for this PC's main IPv4 address (used as installer defaults).
$a = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
  Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.PrefixOrigin -ne 'WellKnown' } |
  Sort-Object -Property @{Expression={ if (Get-NetRoute -InterfaceIndex $_.InterfaceIndex -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue) {0} else {1} }}, InterfaceMetric |
  Select-Object -First 1
if (-not $a) { Write-Output "192.168.50.10 192.168.50.0/24"; exit }
$ip = [System.Net.IPAddress]::Parse($a.IPAddress).GetAddressBytes(); [Array]::Reverse($ip)
$ipInt = [uint32][BitConverter]::ToUInt32($ip, 0)
$mask = if ($a.PrefixLength -eq 0) { 0 } else { [uint32]([math]::Pow(2,32) - [math]::Pow(2, 32 - $a.PrefixLength)) }
$net = [BitConverter]::GetBytes([uint32]($ipInt -band $mask)); [Array]::Reverse($net)
Write-Output ("{0} {1}/{2}" -f $a.IPAddress, ([System.Net.IPAddress]::new($net)).ToString(), $a.PrefixLength)
