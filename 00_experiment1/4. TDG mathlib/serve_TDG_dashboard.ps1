$root = "E:\LEAN-experiments\00_experiment1\4. TDG mathlib"
Set-Location $root

Write-Host "Serving TDG dashboard at http://localhost:8000/TDG.html"
Write-Host "Press Ctrl+C to stop."

python -m http.server 8000
