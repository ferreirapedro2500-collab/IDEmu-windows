# Ativa caminhos longos (> 260 caracteres) no Windows 10/11. Rode no PowerShell como administrador, uma vez.
# Os arquivos do QNX extraídos dos pacotes SWFL têm caminhos profundos; sem isto a compilação do ambiente pode falhar.
New-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name 'LongPathsEnabled' -Value 1 -PropertyType DWORD -Force | Out-Null
Write-Host 'LongPathsEnabled = 1. Feche e reabra o IDEmu.'
