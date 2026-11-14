param(
    [Parameter(Mandatory=$true)][string]$Username,
    [ValidateSet('admin','user')][string]$Role='user'
)
$accountPassword = Read-Host 'Mật khẩu (ít nhất 12 ký tự)' -AsSecureString
$plainPassword = [System.Net.NetworkCredential]::new('', $accountPassword).Password
$projectDirectory = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Push-Location -LiteralPath $projectDirectory
try {
    @{username=$Username;password=$plainPassword;role=$Role} | ConvertTo-Json -Compress |
        docker compose exec -T backend python -m app.manage_users
} finally {
    $plainPassword = $null
    Pop-Location
}
