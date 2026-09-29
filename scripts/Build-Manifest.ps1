<#
.SYNOPSIS
Builds the hub's manifest.json from every pack branch, in the format the Custom NPC Models plugin
reads (HubEntry).

.DESCRIPTION
Each pack-<id> branch but pack-empty becomes one entry, listed at the branch's current commit. The
plugin fetches that commit's bundle.dat and icon.png, and checks the download against the size and
SHA-256 listed here. A branch whose pack.json can't be read, whose id doesn't match its branch, or
that has no readable bundle.dat is left out with a warning, so one bad branch never hides the rest.

.PARAMETER Out
Where to write manifest.json.

.PARAMETER RepoUrl
The hub's page on GitHub. Each entry links its branch's page beneath it.

.PARAMETER RefPrefix
Where the pack branches are: refs/remotes/origin/ in a CI checkout, refs/heads/ locally.
#>
param(
	[Parameter(Mandatory)] [string] $Out,
	[string] $RepoUrl = 'https://github.com/AJD-/custom-model-hub',
	[string] $RefPrefix = 'refs/remotes/origin/'
)

$ErrorActionPreference = 'Stop'

# The bundle header, as AssetCodec writes it inside the gzip stream
$BundleMagic = 0x434E5043

# git's output as bytes. PowerShell would decode a native command's output as text, which corrupts
# a binary blob.
function Get-Blob([string] $spec)
{
	$start = [System.Diagnostics.ProcessStartInfo]::new('git')
	foreach ($argument in 'cat-file', 'blob', $spec)
	{
		$start.ArgumentList.Add($argument)
	}
	$start.RedirectStandardOutput = $true
	$start.RedirectStandardError = $true
	$process = [System.Diagnostics.Process]::Start($start)
	$buffer = [System.IO.MemoryStream]::new()
	$process.StandardOutput.BaseStream.CopyTo($buffer)
	$process.WaitForExit()
	if ($process.ExitCode -ne 0)
	{
		return $null
	}
	, $buffer.ToArray()
}

function Get-FormatVersion([byte[]] $bundle)
{
	$gzip = [System.IO.Compression.GZipStream]::new([System.IO.MemoryStream]::new($bundle),
		[System.IO.Compression.CompressionMode]::Decompress)
	try
	{
		$header = [byte[]]::new(8)
		$read = 0
		while ($read -lt 8)
		{
			$n = $gzip.Read($header, $read, 8 - $read)
			if ($n -le 0)
			{
				throw 'bundle.dat ends before its header'
			}
			$read += $n
		}
		$magic = [System.Buffers.Binary.BinaryPrimitives]::ReadInt32BigEndian([byte[]]$header[0..3])
		if ($magic -ne $BundleMagic)
		{
			throw 'bundle.dat isn''t a Custom NPC Models bundle'
		}
		[System.Buffers.Binary.BinaryPrimitives]::ReadInt32BigEndian([byte[]]$header[4..7])
	}
	finally
	{
		$gzip.Dispose()
	}
}

$entries = [System.Collections.Generic.List[object]]::new()
$refs = git for-each-ref --format='%(refname) %(objectname)' "${RefPrefix}pack-*"
foreach ($line in $refs)
{
	$ref, $commit = $line -split ' ', 2
	$branch = $ref.Substring($RefPrefix.Length)
	if ($branch -eq 'pack-empty')
	{
		continue
	}
	$id = $branch.Substring('pack-'.Length)

	try
	{
		$infoBytes = Get-Blob "${commit}:pack.json"
		if ($null -eq $infoBytes)
		{
			throw 'it has no pack.json'
		}
		$info = [System.Text.Encoding]::UTF8.GetString($infoBytes) | ConvertFrom-Json -Depth 20
		if ($info.id -cne $id)
		{
			throw "its pack.json id is '$($info.id)'"
		}

		$bundle = Get-Blob "${commit}:bundle.dat"
		if ($null -eq $bundle)
		{
			throw 'it has no bundle.dat'
		}
		$sha256 = [System.Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData($bundle)).ToLowerInvariant()
		git cat-file -e "${commit}:icon.png" 2>$null
		$hasIcon = $LASTEXITCODE -eq 0

		$entries.Add([ordered]@{
			id = $id
			name = $info.name
			author = $info.author
			description = $info.description
			version = $info.version
			license = $info.license
			tags = @($info.tags | Where-Object { $null -ne $_ })
			formatVersion = Get-FormatVersion $bundle
			commit = $commit
			size = $bundle.Length
			sha256 = $sha256
			hasIcon = $hasIcon
			repo = "$RepoUrl/tree/$branch"
			models = @($info.models)
		})
		Write-Host "Listed $id at $commit"
	}
	catch
	{
		Write-Warning "Left out $branch at ${commit}: $($_.Exception.Message)"
	}
}

$sorted = @($entries | Sort-Object { $_.id })
$json = ConvertTo-Json -InputObject $sorted -Depth 20
[System.IO.File]::WriteAllText($Out, $json + "`n", [System.Text.UTF8Encoding]::new($false))
Write-Host "Wrote $($sorted.Count) pack(s) to $Out"
