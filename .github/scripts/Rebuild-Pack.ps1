<#
.SYNOPSIS
Rebuilds a pack from its source/ with the Custom NPC Models tools, and checks it matches what the
branch ships.

.DESCRIPTION
Works on a copy of source/, so nothing in the pack is changed. First each source/<name>.retarget.json
is run through retargetGltf, from source/<name>.glb into source/<name>-retargeted.glb. Then
generateAssets -PpackOut builds bundle.dat and pack.json.

The bundles are compared decompressed. Deflate output can differ between zlib builds, but what the
plugin reads can't. pack.json is compared as JSON.

.PARAMETER Pack
The pack branch's checked-out files.

.PARAMETER Tools
A Custom NPC Models checkout, whose Gradle tasks do the building.

.PARAMETER CacheDir
A live Old School cache (the folder holding main_file_cache.dat2), for the sequences' frame timings.
#>
param(
	[Parameter(Mandatory)] [string] $Pack,
	[Parameter(Mandatory)] [string] $Tools,
	[Parameter(Mandatory)] [string] $CacheDir
)

$ErrorActionPreference = 'Stop'
$problems = [System.Collections.Generic.List[string]]::new()
$root = (Resolve-Path -LiteralPath $Pack).Path
$tools = (Resolve-Path -LiteralPath $Tools).Path
$cache = (Resolve-Path -LiteralPath $CacheDir).Path
$gradle = Join-Path $tools $(if ($IsWindows) { 'gradlew.bat' } else { 'gradlew' })

$work = Join-Path ([System.IO.Path]::GetTempPath()) ("pack-rebuild-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
Copy-Item -Recurse -LiteralPath (Join-Path $root 'source') -Destination $work
$source = Join-Path $work 'source'
$out = Join-Path $work 'out'

function Invoke-Gradle([string[]] $arguments)
{
	Push-Location $tools
	try
	{
		& $gradle -q --console=plain @arguments "-PcacheDir=$cache"
		if ($LASTEXITCODE -ne 0)
		{
			throw "gradlew $($arguments[0]) failed with exit code $LASTEXITCODE"
		}
	}
	finally
	{
		Pop-Location
	}
}

function Expand-Gzip([string] $path)
{
	$in = [System.IO.File]::OpenRead($path)
	try
	{
		$gzip = [System.IO.Compression.GZipStream]::new($in, [System.IO.Compression.CompressionMode]::Decompress)
		$buffer = [System.IO.MemoryStream]::new()
		$gzip.CopyTo($buffer)
		$gzip.Dispose()
		, $buffer.ToArray()
	}
	finally
	{
		$in.Dispose()
	}
}

try
{
	Get-ChildItem -LiteralPath $source -Filter '*.retarget.json' -File | ForEach-Object {
		$name = $_.Name.Substring(0, $_.Name.Length - '.retarget.json'.Length)
		$glb = Join-Path $source "$name.glb"
		$output = Join-Path $source "$name-retargeted.glb"
		if (-not (Test-Path -LiteralPath $glb))
		{
			$problems.Add("``source/$($_.Name)`` has no ``source/$name.glb`` beside it to retarget.")
			return
		}
		Write-Host "Retargeting source/$name.glb"
		Invoke-Gradle @('retargetGltf', "-Pglb=$glb", "-Pmap=$($_.FullName)", "-Pout=$output")

		$committed = Join-Path $root "source/$name-retargeted.glb"
		if ((Test-Path -LiteralPath $committed) -and
			(Get-FileHash -LiteralPath $committed).Hash -ne (Get-FileHash -LiteralPath $output).Hash)
		{
			$problems.Add("``source/$name-retargeted.glb`` isn't what retargetGltf makes from ``source/$name.glb`` and ``source/$($_.Name)``. Run it again and commit the result.")
		}
	}

	Write-Host 'Building the pack'
	Invoke-Gradle @('generateAssets', "-PassetsDir=$source", "-PpackOut=$out")

	$shipped = Join-Path $root 'bundle.dat'
	$built = Join-Path $out 'bundle.dat'
	if (-not [System.Linq.Enumerable]::SequenceEqual([byte[]](Expand-Gzip $shipped), [byte[]](Expand-Gzip $built)))
	{
		$problems.Add('bundle.dat isn''t what source/ builds. Rebuild it with generateAssets -PpackOut against the current game cache, and commit the result.')
	}
	elseif ((Get-FileHash -LiteralPath $shipped).Hash -ne (Get-FileHash -LiteralPath $built).Hash)
	{
		Write-Host 'bundle.dat matches once decompressed; only the compression differs.'
	}

	$shippedInfo = Get-Content -Raw -LiteralPath (Join-Path $root 'pack.json') | ConvertFrom-Json -Depth 20 | ConvertTo-Json -Depth 20 -Compress
	$builtInfo = Get-Content -Raw -LiteralPath (Join-Path $out 'pack.json') | ConvertFrom-Json -Depth 20 | ConvertTo-Json -Depth 20 -Compress
	if ($shippedInfo -cne $builtInfo)
	{
		$problems.Add('pack.json isn''t what source/models.json builds. Rebuild it with generateAssets -PpackOut, and commit the result.')
	}
}
catch
{
	$problems.Add("The rebuild failed: $($_.Exception.Message). The Gradle output above says why.")
}
finally
{
	Remove-Item -Recurse -Force -LiteralPath $work -ErrorAction SilentlyContinue
}

$summary = [System.Text.StringBuilder]::new()
[void]$summary.AppendLine('### Rebuild from source/')
if ($problems.Count -eq 0)
{
	[void]$summary.AppendLine('bundle.dat and pack.json match what source/ builds.')
}
else
{
	$problems | ForEach-Object { [void]$summary.AppendLine("- $_") }
}
Write-Host $summary.ToString()
if ($env:GITHUB_STEP_SUMMARY)
{
	Add-Content -LiteralPath $env:GITHUB_STEP_SUMMARY -Value $summary.ToString()
}
if ($problems.Count -gt 0)
{
	exit 1
}
