# Reproduce the original HomeCast raster mark. No external image or broadcaster logo.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$assets = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../iptv_lan/static/assets'))
[System.IO.Directory]::CreateDirectory($assets) | Out-Null
$bitmap = [System.Drawing.Bitmap]::new(160, 160)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.Clear([System.Drawing.Color]::Transparent)
$background = [System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#087f5b'))
$white = [System.Drawing.Pen]::new([System.Drawing.Color]::White, 7)
$white.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
$white.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
$frame = [System.Drawing.Drawing2D.GraphicsPath]::new()
$frame.AddArc(4, 4, 32, 32, 180, 90)
$frame.AddArc(124, 4, 32, 32, 270, 90)
$frame.AddArc(124, 124, 32, 32, 0, 90)
$frame.AddArc(4, 124, 32, 32, 90, 90)
$frame.CloseFigure()
$graphics.FillPath($background, $frame)
$screen = [System.Drawing.Drawing2D.GraphicsPath]::new()
$screen.AddArc(35, 57, 14, 14, 180, 90)
$screen.AddArc(111, 57, 14, 14, 270, 90)
$screen.AddArc(111, 105, 14, 14, 0, 90)
$screen.AddArc(35, 105, 14, 14, 90, 90)
$screen.CloseFigure()
$graphics.DrawPath($white, $screen)
$graphics.DrawLine($white, 60, 36, 80, 54)
$graphics.DrawLine($white, 100, 36, 80, 54)
$graphics.DrawLine($white, 65, 132, 95, 132)
$graphics.DrawLine($white, 80, 120, 80, 130)
$bitmap.Save((Join-Path $assets 'homecast.png'), [System.Drawing.Imaging.ImageFormat]::Png)
$screen.Dispose()
$frame.Dispose()
$white.Dispose()
$background.Dispose()
$graphics.Dispose()
$bitmap.Dispose()
