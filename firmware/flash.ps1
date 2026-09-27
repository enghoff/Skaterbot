# Builds one of the firmware images and writes it to the WeAct board over USB
# DFU, then starts it. Needs STM32CubeProgrammer, which also installs the DFU
# driver.
#
#   .\flash.ps1               the bring-up firmware
#   .\flash.ps1 policy        the policy firmware
#   .\flash.ps1 -Start        start what is already on the board, from its bootloader
#
# If a firmware from this workspace is running, this asks it to reboot into the
# bootloader by opening its port at 1200 baud, and one that has crashed is in
# the bootloader already. Otherwise put the board in its bootloader by hand
# first: hold BOOT0, tap NRST, release BOOT0.
param(
    [ValidateSet('bringup', 'policy')]
    [string]$Image = 'bringup',
    [switch]$Start
)
$ErrorActionPreference = 'Stop'
$cargo = "$env:USERPROFILE\.cargo\bin\cargo.exe"
$cli = 'C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe'

function Test-Bootloader {
    [bool](Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -match 'VID_0483&PID_DF11' -and $_.Status -eq 'OK' })
}

function Get-FirmwarePort {
    Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -match 'VID_1209&PID_0001&MI_00' -and $_.Status -eq 'OK' } |
        ForEach-Object { if ($_.FriendlyName -match '\((COM\d+)\)') { $Matches[1] } } |
        Select-Object -First 1
}

Push-Location $PSScriptRoot
try {
    if (-not $Start) {
        & $cargo build --release -p $Image
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
    }

    if (-not (Test-Bootloader)) {
        $port = Get-FirmwarePort
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

    if ($Start) {
        & $cli -c port=USB1 -s 0x08000000
    }
    else {
        # The programmer picks the file format from the extension, and cargo's
        # ELF has none.
        $elf = "target\thumbv7em-none-eabihf\release\$Image"
        Copy-Item $elf "$elf.elf" -Force
        & $cli -c port=USB1 -w "$elf.elf" -v -s 0x08000000
    }
    if ($LASTEXITCODE) { exit $LASTEXITCODE }

    # Whether it came up: its serial port, or -- if it died starting -- the
    # bootloader again.
    $deadline = (Get-Date).AddSeconds(15)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 500
        $port = Get-FirmwarePort
        if ($port) {
            Write-Host "Running, on $port"
            exit 0
        }
    }
    if (Test-Bootloader) {
        throw 'The firmware went back to the bootloader: it crashed, or USB did not come up.'
    }
    throw 'Neither the firmware nor the bootloader came back.'
}
finally {
    Pop-Location
}
