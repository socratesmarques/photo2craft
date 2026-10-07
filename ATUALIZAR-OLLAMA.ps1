# Run with Windows PowerShell 5.1+ from the existing photo2craft project.
[CmdletBinding()]
param([ValidatePattern('^[a-z0-9][a-z0-9_-]*$')][string]$ProjectName = 'photo2craft')
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$projectRoot = $PSScriptRoot
$composeFile = Join-Path $projectRoot 'docker-compose.yml'
$envFile = Join-Path $projectRoot '.env'
$expectedRelease = 'ollama-local-0.5.0'
$composeArgs = @('compose', '--project-directory', $projectRoot, '-p', $ProjectName, '-f', $composeFile, '--env-file', $envFile)

function Invoke-PhotoDocker {
    param([string[]]$DockerArguments)
    & docker @composeArgs @DockerArguments
    if ($LASTEXITCODE -ne 0) { throw "Docker falhou. Leia o erro acima; a atualizacao foi interrompida." }
}

try {
    Get-Command docker -ErrorAction Stop | Out-Null
    foreach ($relativePath in @('RELEASE.txt', 'apps\api\app\release.py', 'apps\web\src\App.tsx')) {
        $path = Join-Path $projectRoot $relativePath
        if (!(Test-Path -LiteralPath $path) -or !(Select-String -LiteralPath $path -SimpleMatch $expectedRelease -Quiet)) {
            throw "Arquivos antigos ou extracao incompleta: $relativePath. Copie o conteudo completo do ZIP novo para esta pasta."
        }
    }
    if (!(Test-Path -LiteralPath $composeFile)) { throw 'docker-compose.yml nao encontrado.' }
    & docker info --format '{{.ServerVersion}}'
    if ($LASTEXITCODE -ne 0) { throw 'Abra o Docker Desktop antes de continuar.' }

    if (Test-Path -LiteralPath $envFile) {
        $backupPath = Join-Path $projectRoot ('.env.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
        Copy-Item -LiteralPath $envFile -Destination $backupPath -ErrorAction Stop
        Write-Host "Backup da configuracao: $backupPath"
    } else {
        Copy-Item -LiteralPath (Join-Path $projectRoot '.env.example') -Destination $envFile
    }
    $envText = [System.IO.File]::ReadAllText($envFile)
    $localSettings = [ordered]@{
        AI_PROVIDER = 'ollama'
        OLLAMA_URL = 'http://host.docker.internal:11434'
        OLLAMA_MODEL = 'qwen3-vl:8b'
        AI_TIMEOUT_SECONDS = '900'
        AI_MAX_OUTPUT_TOKENS = '24000'
        AI_CONTEXT_TOKENS = '32768'
    }
    foreach ($key in $localSettings.Keys) {
        $pattern = '(?m)^\s*' + [regex]::Escape($key) + '\s*=[^\r\n]*'
        if (-not [regex]::IsMatch($envText, $pattern)) {
            $envText = $envText.TrimEnd() + "`r`n$key=$($localSettings[$key])`r`n"
        }
    }
    [System.IO.File]::WriteAllText($envFile, $envText, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Projeto Docker: $ProjectName | Pasta: $projectRoot"
    Write-Host 'Portas e dados existentes preservados. Recriando API e site...'
    Invoke-PhotoDocker -DockerArguments @('build', 'api', 'web')
    Invoke-PhotoDocker -DockerArguments @('up', '-d', '--force-recreate', '--wait', '--wait-timeout', '120', 'api', 'web')
    Invoke-PhotoDocker -DockerArguments @('exec', '-T', 'api', 'python', '-m', 'app.verify_installation')

    $portOutput = Invoke-PhotoDocker -DockerArguments @('port', 'web', '80')
    $published = [string](@($portOutput)[0])
    if ($published -notmatch ':(\d+)\s*$') { throw 'Nao foi possivel identificar a porta do site.' }
    $siteUrl = 'http://localhost:' + $Matches[1]
    $capabilities = Invoke-RestMethod -Uri ($siteUrl + '/api/capabilities') -TimeoutSec 10
    if ($capabilities.release -ne $expectedRelease -or $capabilities.aiProvider -ne 'ollama' -or !$capabilities.generationJobs) {
        throw 'O endereco publicado respondeu com outra versao. Confira conflitos de porta ou proxy.'
    }
    Write-Host "CONFIRMADO: Photo2Craft 0.5.0 / Ollama (modelo preservado do .env)"
    Write-Host "Abra $siteUrl e pressione Ctrl+F5."
    Write-Host 'IMPORTANTE: as novas cores exigem recompilar e instalar o mod 0.3.0. Veja ATUALIZAR-IA.md.'
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
