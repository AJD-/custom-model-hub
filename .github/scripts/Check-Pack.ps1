<#
.SYNOPSIS
Checks a pack branch's files against the hub's layout rules, without building anything.

.DESCRIPTION
Every problem is listed, not just the first. Files that look like exports from the game cache are
noted, not refused: the hub accepts Jagex-derived packs, but their README must say what they were
made from, and the reviewer checks that. When GITHUB_STEP_SUMMARY is set, the result is also written
there as Markdown.

.PARAMETER Pack
The pack branch's checked-out files.

.PARAMETER Branch
The branch the pack is on, which must be pack-<id>.
#>
param(
	[Parameter(Mandatory)] [string] $Pack,
	[Parameter(Mandatory)] [string] $Branch
)

$ErrorActionPreference = 'Stop'
$problems = [System.Collections.Generic.List[string]]::new()
$notes = [System.Collections.Generic.List[string]]::new()

$MaxBundle = 16MB
$MaxIcon = 256KB
$MaxIconSide = 512
$Allowed = '^(\.gitattributes|pack\.json|bundle\.dat|icon\.png|README\.md|LICENSE|source/.+|notes/.+|\.github/.+)$'

function Test-FolderName([string] $name)
{
	# The plugin's own rules: DirectoryPackSource.isValidFolderName and HubEntry's id pattern
	($name -cmatch '^[a-z0-9-]{1,64}$') -and ($name -notmatch '^(con|prn|aux|nul|com[0-9]|lpt[0-9])$') -and
		-not $name.StartsWith('dl-')
}

function Read-Json([string] $path, [string] $what)
{
	try
	{
		Get-Content -Raw -LiteralPath $path | ConvertFrom-Json -Depth 20
	}
	catch
	{
		$problems.Add("$what isn't valid JSON: $($_.Exception.Message)")
		$null
	}
}

function Test-Text($value)
{
	$value -is [string] -and $value.Trim().Length -gt 0
}

$root = (Resolve-Path -LiteralPath $Pack).Path

# Only the files the layout names
Get-ChildItem -LiteralPath $root -Recurse -File -Force | ForEach-Object {
	$relative = [System.IO.Path]::GetRelativePath($root, $_.FullName).Replace('\', '/')
	if ($relative -notmatch '^\.git/' -and $relative -cnotmatch $Allowed)
	{
		$problems.Add("``$relative`` isn't part of a pack. A pack holds pack.json, bundle.dat, README.md, LICENSE, source/, and optionally icon.png and notes/.")
	}
}

foreach ($required in 'pack.json', 'bundle.dat', 'README.md', 'LICENSE', 'source/models.json')
{
	if (-not (Test-Path -LiteralPath (Join-Path $root $required) -PathType Leaf))
	{
		$problems.Add("``$required`` is missing.")
	}
}

# pack.json
$info = $null
if (Test-Path -LiteralPath (Join-Path $root 'pack.json'))
{
	$info = Read-Json (Join-Path $root 'pack.json') 'pack.json'
}
if ($info)
{
	if (-not (Test-FolderName $info.id))
	{
		$problems.Add("pack.json's id '$($info.id)' must be 1 to 64 lowercase letters, digits and hyphens, not start with dl-, and not be a name Windows reserves.")
	}
	elseif ($Branch -cne "pack-$($info.id)")
	{
		$problems.Add("The branch is '$Branch', but a pack with id '$($info.id)' belongs on 'pack-$($info.id)'.")
	}
	foreach ($field in 'name', 'author', 'version', 'license')
	{
		if (-not (Test-Text $info.$field))
		{
			$problems.Add("pack.json has no $field.")
		}
	}
	if ($null -ne $info.tags -and -not ($info.tags -is [array] -and @($info.tags | Where-Object { $_ -isnot [string] }).Count -eq 0))
	{
		$problems.Add('pack.json''s tags must be a list of strings.')
	}
	if (-not ($info.models -is [array]) -or $info.models.Count -eq 0)
	{
		$problems.Add('pack.json lists no models. Build it with generateAssets -PpackOut, which fills them in.')
	}
	else
	{
		foreach ($model in $info.models)
		{
			if ($model.key -isnot [long] -and $model.key -isnot [int] -or -not (Test-Text $model.name) -or
				-not ($model.npcIds -is [array]) -or $model.npcIds.Count -eq 0)
			{
				$problems.Add("pack.json has a model without a key, name and npcIds: $($model | ConvertTo-Json -Compress)")
			}
		}
	}
}

# source/models.json must describe the same pack
$sourcePath = Join-Path $root 'source/models.json'
if ($info -and (Test-Path -LiteralPath $sourcePath))
{
	$manifest = Read-Json $sourcePath 'source/models.json'
	if ($manifest -and $manifest.pack.id -cne $info.id)
	{
		$problems.Add("source/models.json's pack id is '$($manifest.pack.id)', but pack.json's is '$($info.id)'.")
	}
}

# bundle.dat
$bundlePath = Join-Path $root 'bundle.dat'
if (Test-Path -LiteralPath $bundlePath)
{
	$size = (Get-Item -LiteralPath $bundlePath).Length
	if ($size -le 0 -or $size -gt $MaxBundle)
	{
		$problems.Add("bundle.dat is $size bytes; it must be 1 byte to 16 MiB.")
	}
	else
	{
		$bytes = [System.IO.File]::ReadAllBytes($bundlePath)
		if ($bytes.Length -lt 2 -or $bytes[0] -ne 0x1f -or $bytes[1] -ne 0x8b)
		{
			$problems.Add('bundle.dat isn''t a Custom NPC Models bundle (not gzip).')
		}
	}
}

# icon.png, when there is one
$iconPath = Join-Path $root 'icon.png'
if (Test-Path -LiteralPath $iconPath)
{
	$icon = [System.IO.File]::ReadAllBytes($iconPath)
	$signature = [byte[]](0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A)
	if ($icon.Length -lt 24 -or -not [System.Linq.Enumerable]::SequenceEqual([byte[]]$icon[0..7], $signature))
	{
		$problems.Add('icon.png isn''t a PNG.')
	}
	else
	{
		$width = [System.Buffers.Binary.BinaryPrimitives]::ReadInt32BigEndian([byte[]]$icon[16..19])
		$height = [System.Buffers.Binary.BinaryPrimitives]::ReadInt32BigEndian([byte[]]$icon[20..23])
		if ($icon.Length -gt $MaxIcon -or $width -gt $MaxIconSide -or $height -gt $MaxIconSide)
		{
			$problems.Add("icon.png is ${width}x${height} and $($icon.Length) bytes; it must be at most ${MaxIconSide}px a side and 256 KiB, or the plugin won't show it.")
		}
	}
}

# Game-derived sources are allowed, and noted for the reviewer
$markers = '_RS_VERTEX', '_RS_HSL', '"group_', 'part_', 'Custom NPC Models authoring pipeline'
Get-ChildItem -LiteralPath (Join-Path $root 'source') -Filter '*.glb' -File -ErrorAction SilentlyContinue | ForEach-Object {
	$text = [System.Text.Encoding]::Latin1.GetString([System.IO.File]::ReadAllBytes($_.FullName))
	$found = @($markers | Where-Object { $text.Contains($_) })
	if ($found.Count -gt 0)
	{
		$notes.Add("``source/$($_.Name)`` looks like an export from the game cache ($($found -join ', ')). That's allowed; check that README.md says what it was made from.")
	}
}

$summary = [System.Text.StringBuilder]::new()
[void]$summary.AppendLine("### Pack check: $Branch")
if ($problems.Count -eq 0)
{
	[void]$summary.AppendLine('The layout is fine.')
}
else
{
	[void]$summary.AppendLine('Problems:')
	$problems | ForEach-Object { [void]$summary.AppendLine("- $_") }
}
if ($notes.Count -gt 0)
{
	[void]$summary.AppendLine()
	[void]$summary.AppendLine('For the reviewer:')
	$notes | ForEach-Object { [void]$summary.AppendLine("- $_") }
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
