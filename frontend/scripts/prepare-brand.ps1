# Package the supplied logo unchanged into square app icons.
Add-Type -AssemblyName System.Drawing
$publicDirectory = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../public'))
$logo = [System.Drawing.Image]::FromFile((Join-Path $publicDirectory 'kun-global-logo.png'))
try {
    foreach ($size in @(192,512)) {
        $canvas = [System.Drawing.Bitmap]::new($size,$size)
        $drawing = [System.Drawing.Graphics]::FromImage($canvas)
        try {
            $drawing.Clear([System.Drawing.ColorTranslator]::FromHtml('#251c15'))
            $drawing.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            # Keep the complete original logo inside the central maskable safe area.
            $width = [int]($size * 0.88)
            $height = [int]($width * $logo.Height / $logo.Width)
            $drawing.DrawImage($logo,[int](($size-$width)/2),[int](($size-$height)/2),$width,$height)
            $canvas.Save((Join-Path $publicDirectory "icon-$size.png"),[System.Drawing.Imaging.ImageFormat]::Png)
        } finally { $drawing.Dispose(); $canvas.Dispose() }
    }
    $encoded = [Convert]::ToBase64String([System.IO.File]::ReadAllBytes((Join-Path $publicDirectory 'icon-512.png')))
    $svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><image width="512" height="512" href="data:image/png;base64,' + $encoded + '"/></svg>'
    [System.IO.File]::WriteAllText((Join-Path $publicDirectory 'icon.svg'),$svg)
} finally { $logo.Dispose() }
