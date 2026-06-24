# Creates a minimal stub binary for local Tauri dev.
# In production the real PyInstaller binary is used.

$target = "x86_64-pc-windows-msvc"
$out = "src-tauri\binaries\job-hunter-backend-$target.exe"

if (Test-Path $out) { exit 0 }

Write-Host "[dev-stub] building stub sidecar at $out ..."

New-Item -ItemType Directory -Force "src-tauri\binaries" | Out-Null

$stub = "src-tauri\binaries\_stub_main.rs"
Set-Content $stub 'fn main() { eprintln!("dev-stub: start backend manually: cd backend && python run.py"); }'

rustc $stub -o $out 2>&1
$rc = $LASTEXITCODE
Remove-Item $stub -ErrorAction SilentlyContinue

if ($rc -ne 0) {
    Write-Error "[dev-stub] rustc failed."
    exit 1
}

Write-Host "[dev-stub] stub ready."
