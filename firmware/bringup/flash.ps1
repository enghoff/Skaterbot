# Builds the bring-up firmware and writes it to the WeAct board over USB DFU,
# then starts it. Needs STM32CubeProgrammer, which also installs the DFU driver.
#
# If the bring-up firmware is already running, this asks it to reboot into the
# bootloader by opening its port at 1200 baud. Otherwise put the board in its
# bootloader by hand first: hold BOOT0, tap NRST, release BOOT0.
$ErrorActionPreference = 'Stop'
$cargo = "$env:USERPROFILE\.cargo\bin\cargo.exe"
$cli = 'C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe'

function Test-Bootloader {
    [bool](Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -match 'VID_0483&PID_DF11' -and $_.Status -eq 'OK' })
}

Push-Location $PSScriptRoot
try {
    & $cargo build --release
    if ($LASTEXITCODE) { exit $LASTEXITCODE }

    if (-not (Test-Bootloader)) {
        $port = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
            Where-Object { $_.InstanceId -match 'VID_1209&PID_0001&MI_00' } |
            ForEach-Object { if ($_.FriendlyName -match '\((COM\d+)\)') { $Matches[1] } } |
            Select-Object -First 1
        if (-not $port) {
            throw 'No board found. Hold BOOT0, tap NRST, release BOOT0, and run this again.'
        }
        Write-Host "Asking the firmware on $port to reboot into the bootloader"
        $serial = New-Object System.IO.Ports.SerialPort $port, 1200
        # The board drops off the bus mid-open, which can surface as an error.
        try { $serial.Open(); $serial.Close() } catch {}
        $deadline = (Get-Date).AddSeconds(10)
        while (-not (Test-Bootloader)) {
            if ((Get-Date) -gt $deadline) {
                throw 'The board did not come back as the bootloader. Use BOOT0 and NRST.'
            }
            Start-Sleep -Milliseconds 250
        }
    }

    # The programmer picks the file format from the extension, and cargo's ELF
    # has none.
    $elf = 'target\thumbv7em-none-eabihf\release\bringup'
    Copy-Item $elf "$elf.elf" -Force
    & $cli -c port=USB1 -w "$elf.elf" -v -s 0x08000000
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
