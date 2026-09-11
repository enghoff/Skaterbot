@echo off
rem Bring the OCP CAD Viewer up and keep it showing the current CAD, finished.
rem
rem   watch.cmd                     the whole robot, redrawn every time you save
rem   watch.cmd pelvis-shell        one printed piece, on its own
rem   watch.cmd torso-packing-check a check scene, with its groups named
rem   watch.cmd --raw               as modelled, sharp arrises, which is faster
rem   watch.cmd --size 2            an exaggerated chamfer, to SEE it is there
rem   watch.cmd --list              what can be shown
rem
rem IT SHOWS THE FINISHED DESIGN unless you ask for --raw. The parts leave
rem cad/ with sharp arrises and the 0.5 mm chamfer is a separate pass in
rem cad/finish.py, so what the viewer drew until now was the part as modelled
rem rather than the part as printed. This adds --finished for you.
rem
rem What that costs, and what to do about it. Every printed piece goes through
rem the chamfer on every redraw, which is about a minute for the whole robot and
rem a fraction of a second for one piece -- so name the piece you are working on
rem while you are working on edges, or pass --raw when the shape rather than the
rem finish is the question. And at 0.5 mm the chamfer is about three pixels wide
rem at a zoom that fits a whole limb: --size 2 exaggerates it, at the price of a
rem few edges OCCT then refuses to cut at all.
rem
rem Everything you pass goes through to tools/view.py, which is what draws. The
rem work is all in tools/watch.py --serve: it starts the standalone viewer if
rem nothing is already listening on port 3939, redraws on every save, and stops
rem the viewer again when you stop watching with ctrl-c. An open OCP CAD Viewer
rem panel in VS Code counts as listening, so this uses that panel when it is
rem there and opens a browser tab when it is not.
rem
rem Free and offline, like everything else here: the geometry is tessellated on
rem this machine and pushed to the viewer over a socket.
setlocal
pushd "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
    echo uv is not on PATH. It is what runs everything in this repository:
    echo   https://docs.astral.sh/uv/
    popd
    exit /b 1
)

rem --raw is this script's own flag and view.py knows nothing about it, so it is
rem taken out of the arguments rather than passed on. Everything else goes
rem through untouched, quoting and all, which is why this is a shift loop and
rem not a for over %* -- that one splits on commas and expands wildcards.
set "FINISH=--finished"
set "ARGS="
:parse
if "%~1"=="" goto run
if /I "%~1"=="--raw" (
    set "FINISH="
) else (
    set "ARGS=%ARGS% %1"
)
shift
goto parse

:run
uv run tools/watch.py --serve %FINISH%%ARGS%
set WATCH_EXIT=%ERRORLEVEL%
popd
exit /b %WATCH_EXIT%
