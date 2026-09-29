<#
.SYNOPSIS
Finds the newest Old School live cache in the OpenRS2 archive, whose frame timings packs are built
against.

.DESCRIPTION
Prints the cache's id, and writes it as the step output "id" when GITHUB_OUTPUT is set. Its files
are at https://archive.openrs2.org/caches/runescape/<id>/disk.zip, under cache/.
#>
$ErrorActionPreference = 'Stop'

$caches = Invoke-RestMethod -Uri 'https://archive.openrs2.org/caches.json'
$newest = $caches |
	Where-Object { $_.scope -eq 'runescape' -and $_.game -eq 'oldschool' -and $_.environment -eq 'live' -and
		$_.disk_store_valid -and $_.timestamp } |
	Sort-Object { [datetime]$_.timestamp } |
	Select-Object -Last 1
if (-not $newest)
{
	throw 'The OpenRS2 archive lists no Old School live cache'
}

Write-Host "Newest Old School live cache: $($newest.id), from $($newest.timestamp)"
if ($env:GITHUB_OUTPUT)
{
	Add-Content -LiteralPath $env:GITHUB_OUTPUT -Value "id=$($newest.id)"
}
